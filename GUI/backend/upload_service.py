"""
SFTP upload service for sending extracted frames to the remote server.

UploadWorker is a QThread that reads a segment_frames.csv to determine
which frame images to upload, then transfers them via SFTP.

Follows the WholeVideoExtractor pattern: pyqtSignal for progress,
threading.Event for cooperative shutdown.
"""
from __future__ import annotations

import csv
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    paramiko = None
    PARAMIKO_AVAILABLE = False


def _ensure_remote_dir(sftp, remote_path: str):
    """Recursively create remote directories (like mkdir -p)."""
    parts = remote_path.replace("\\", "/").split("/")
    current = ""
    for part in parts:
        if not part:
            current = "/"
            continue
        current = f"{current}/{part}" if current != "/" else f"/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


class UploadWorker(QThread):
    """Upload segment frames to the remote server via SFTP.

    Signals:
        progress(int)          -- 0-100 percentage
        status(str)            -- human-readable status message
        finished(bool, str)    -- (success, remote_job_path_or_error)
    """

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        ssh_client,
        segment_csv_path: str,
        frames_dir: str,
        remote_workdir: str,
        job_name: str,
    ):
        super().__init__()
        self._client = ssh_client
        self._segment_csv = segment_csv_path
        self._frames_dir = frames_dir
        self._remote_workdir = remote_workdir
        self._job_name = job_name
        self._stop_event = threading.Event()

    def request_stop(self):
        """Signal the worker to shut down cooperatively."""
        self._stop_event.set()

    def run(self):
        if not PARAMIKO_AVAILABLE:
            self.finished.emit(False, "paramiko is not installed.")
            return

        try:
            # 1. Parse segment_frames.csv to get frame filenames
            frame_names = self._parse_segment_csv()
            if not frame_names:
                self.finished.emit(False, "No frames found in segment CSV.")
                return

            total = len(frame_names) + 1  # +1 for the CSV itself

            # 2. Open SFTP
            sftp = self._client.open_sftp()

            # 3. Create remote job directory
            remote_job = f"{self._remote_workdir}/{self._job_name}"
            remote_images = f"{remote_job}/images"
            self.status.emit(f"Creating remote directory: {remote_images}")
            _ensure_remote_dir(sftp, remote_images)

            # 4. Upload frame images
            uploaded = 0
            for frame_name in frame_names:
                if self._stop_event.is_set():
                    self.status.emit("Upload cancelled.")
                    self.finished.emit(False, "Upload cancelled by user.")
                    sftp.close()
                    return

                local_path = str(Path(self._frames_dir) / frame_name)
                remote_path = f"{remote_images}/{frame_name}"
                self.status.emit(f"Uploading {frame_name}...")
                sftp.put(local_path, remote_path)

                uploaded += 1
                pct = int(uploaded / total * 100)
                self.progress.emit(pct)

            # 5. Upload the segment CSV for reference
            if not self._stop_event.is_set():
                csv_name = Path(self._segment_csv).name
                remote_csv = f"{remote_job}/{csv_name}"
                self.status.emit(f"Uploading {csv_name}...")
                sftp.put(self._segment_csv, remote_csv)
                self.progress.emit(100)

            sftp.close()
            self.status.emit(f"Upload complete: {uploaded} frames")
            self.finished.emit(True, remote_job)

        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _parse_segment_csv(self) -> list[str]:
        """Read segment_frames.csv and extract frame_name column."""
        frame_names = []
        try:
            with open(self._segment_csv, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("frame_name", "").strip()
                    if name:
                        frame_names.append(name)
        except Exception:
            pass
        return frame_names
