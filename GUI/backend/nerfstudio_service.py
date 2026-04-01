"""
Nerfstudio training pipeline service.

NerfstudioTrainWorker is a QThread that runs ns-process-data followed by
ns-train on the remote server via SSH.  It streams stdout/stderr back to
the GUI as log lines and emits progress signals.

Follows the NerfstudioViewerWorker pattern from ssh_service.py: PTY-based
remote execution, line-by-line parsing, cooperative shutdown.
"""
from __future__ import annotations

import re
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    paramiko = None
    PARAMIKO_AVAILABLE = False

from shared.constants import (
    NERFSTUDIO_CONDA_ENV,
    NERFSTUDIO_VIEWER_PORT,
    NERFSTUDIO_WORKING_DIR,
)

# Regex patterns for parsing nerfstudio output
_URL_RE = re.compile(r"https?://[\w.-]+:\d+")
# Match various nerfstudio progress formats:
#   "Step: 100/2000"  "Step 100/2000"  "100/30000"  "4500/30000 ["  (tqdm-style)
#   Also handles percentage-based: "15%|" (tqdm bar)
_ITER_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
_PCT_RE = re.compile(r"(\d+)%\|")
# Strip ANSI escape sequences for clean parsing
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07")


class NerfstudioTrainWorker(QThread):
    """Run ns-process-data + ns-train on the remote server.

    Signals:
        stage_changed(str)      -- "processing" | "training" | "complete" | "error"
        log_line(str)           -- individual log line from server
        training_progress(int)  -- 0-100 training iteration progress
        viewer_ready(str)       -- emitted when viewer URL detected (localhost URL)
        finished(bool, str)     -- (success, error_message_or_empty)
    """

    stage_changed = pyqtSignal(str)
    log_line = pyqtSignal(str)
    training_progress = pyqtSignal(int)
    viewer_ready = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        ssh_client,
        remote_job_path: str,
        nerfstudio_method: str = "nerfacto",
        viewer_port: int = NERFSTUDIO_VIEWER_PORT,
        conda_env: str = NERFSTUDIO_CONDA_ENV,
        local_port: int = 7007,
    ):
        super().__init__()
        self._client = ssh_client
        self._job_path = remote_job_path
        self._method = nerfstudio_method
        self._viewer_port = viewer_port
        self._conda_env = conda_env
        self._local_port = local_port
        self._stop_event = threading.Event()
        self._channel = None

    def request_stop(self):
        """Signal the worker to shut down cooperatively."""
        self._stop_event.set()
        self._kill_remote_process()

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self):
        if not PARAMIKO_AVAILABLE:
            self.finished.emit(False, "paramiko is not installed.")
            return

        try:
            # ns-train
            self.stage_changed.emit("training")
            success = self._run_training()
            if not success:
                return

            self.stage_changed.emit("complete")
            self.finished.emit(True, "")

        except Exception as exc:
            self.stage_changed.emit("error")
            self.finished.emit(False, str(exc))
        finally:
            self._cleanup_channel()

    # ------------------------------------------------------------------
    # ns-train
    # ------------------------------------------------------------------

    def _run_training(self) -> bool:
        cmd = (
            f'bash -lc "'
            f"cd {NERFSTUDIO_WORKING_DIR} && "
            f"conda activate {self._conda_env} && "
            f"export CUDA_VISIBLE_DEVICES=6,7 && "
            f"ns-train {self._method} "
            f"--data data/nerfstudio/Cylinder "
            f"--viewer.websocket-port {self._viewer_port}"
            f'"'
        )
        self.log_line.emit(f"[train] Running: {cmd}")

        viewer_detected = False
        last_pct = -1

        transport = self._client.get_transport()
        if transport is None:
            self.finished.emit(False, "SSH transport is not active.")
            return False

        self._channel = transport.open_session()
        self._channel.get_pty()
        self._channel.exec_command(cmd)

        buf = ""
        try:
            while not self._stop_event.is_set():
                # Check if remote process exited
                if self._channel.exit_status_ready():
                    # Drain remaining output
                    while self._channel.recv_ready():
                        chunk = self._channel.recv(4096).decode("utf-8", errors="replace")
                        for line in chunk.splitlines():
                            clean = _ANSI_RE.sub("", line).strip()
                            if clean:
                                self.log_line.emit(f"[train] {clean}")
                                pct = self._extract_progress(clean)
                                if pct is not None and pct != last_pct:
                                    last_pct = pct
                                    self.training_progress.emit(pct)

                    code = self._channel.recv_exit_status()
                    if code != 0 and not self._stop_event.is_set():
                        msg = f"ns-train exited with code {code}"
                        self.log_line.emit(f"[train] {msg}")
                        self.stage_changed.emit("error")
                        self.finished.emit(False, msg)
                        return False
                    return True

                # Read available stdout
                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode("utf-8", errors="replace")
                    buf += chunk
                    # Split on both \n and \r to capture tqdm-style progress updates
                    while "\n" in buf or "\r" in buf:
                        # Find the earliest delimiter
                        idx_n = buf.find("\n")
                        idx_r = buf.find("\r")
                        if idx_n == -1:
                            idx = idx_r
                        elif idx_r == -1:
                            idx = idx_n
                        else:
                            idx = min(idx_n, idx_r)
                        line = buf[:idx]
                        buf = buf[idx + 1:]
                        # Strip ANSI escape codes and whitespace
                        clean = _ANSI_RE.sub("", line).strip()
                        if not clean:
                            continue

                        self.log_line.emit(f"[train] {clean}")

                        # Detect viewer URL
                        if not viewer_detected:
                            match = _URL_RE.search(clean)
                            if match:
                                viewer_detected = True
                                local_url = f"http://localhost:{self._local_port}"
                                self.log_line.emit(
                                    f"[train] Viewer detected! Forwarding to {local_url}"
                                )
                                self.viewer_ready.emit(local_url)

                        # Parse training progress
                        pct = self._extract_progress(clean)
                        if pct is not None and pct != last_pct:
                            last_pct = pct
                            self.training_progress.emit(pct)

                time.sleep(0.05)

        except Exception as exc:
            self.stage_changed.emit("error")
            self.finished.emit(False, f"Error during training: {exc}")
            return False

        if self._stop_event.is_set():
            self.finished.emit(False, "Cancelled by user.")
            return False

        return True

    def _extract_progress(self, line: str) -> int | None:
        """Extract training progress percentage from a line.

        Handles nerfstudio output formats like:
          "15%|████    | 4500/30000"   -> 15
          "Step 100/2000"              -> 5
          "4500/30000 [00:45<03:00]"   -> 15
        Returns None if no progress detected.
        """
        # Try percentage first (tqdm-style "15%|")
        pct_match = _PCT_RE.search(line)
        if pct_match:
            return min(int(pct_match.group(1)), 100)
        # Fall back to iteration fraction (current/total)
        iter_match = _ITER_RE.search(line)
        if iter_match:
            current = int(iter_match.group(1))
            total = int(iter_match.group(2))
            if total > 0:
                return min(int(current / total * 100), 100)
        return None

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _exec_and_stream(self, cmd: str, stage: str = "") -> int:
        """Execute a command via SSH PTY and stream output. Returns exit code."""
        transport = self._client.get_transport()
        if transport is None:
            self.stage_changed.emit("error")
            self.finished.emit(False, "SSH transport is not active.")
            return -1

        self._channel = transport.open_session()
        self._channel.get_pty()
        self._channel.exec_command(cmd)

        buf = ""
        try:
            while not self._stop_event.is_set():
                if self._channel.exit_status_ready():
                    # Drain
                    while self._channel.recv_ready():
                        chunk = self._channel.recv(4096).decode("utf-8", errors="replace")
                        for line in chunk.splitlines():
                            prefix = f"[{stage}] " if stage else ""
                            self.log_line.emit(f"{prefix}{line}")
                    return self._channel.recv_exit_status()

                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode("utf-8", errors="replace")
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.rstrip("\r")
                        prefix = f"[{stage}] " if stage else ""
                        self.log_line.emit(f"{prefix}{line}")

                time.sleep(0.05)

        except Exception as exc:
            self.log_line.emit(f"[{stage}] Error: {exc}")
            return -1
        finally:
            self._cleanup_channel()

        return -1  # stopped

    def _kill_remote_process(self):
        """Attempt to kill the remote nerfstudio process."""
        if self._channel and not self._channel.closed:
            try:
                self._channel.send("\x03")  # Ctrl-C
            except Exception:
                pass

        # Also try pkill as a fallback
        try:
            if self._client and self._client.get_transport():
                self._client.exec_command(
                    f"pkill -f 'ns-train.*{self._job_path}'"
                )
        except Exception:
            pass

    def _cleanup_channel(self):
        """Close the current SSH channel."""
        if self._channel is not None:
            try:
                if not self._channel.closed:
                    self._channel.close()
            except Exception:
                pass
            self._channel = None
