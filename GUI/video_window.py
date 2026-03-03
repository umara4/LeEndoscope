"""
Video capture window: select camera, start live preview+recording, stop, export frames.
"""
from typing import List
from pathlib import Path
import cv2
from datetime import datetime
from typing import List
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox
)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "Data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Legacy/simple recorder UI writes to Data/ as well.
RECORDINGS_DIR = DATA_DIR

def probe_cameras(max_probe=6, timeout_ms=200):
    available = []
    for i in range(max_probe):
        # Use DirectShow backend on Windows for better compatibility
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue
        ret, _ = cap.read()
        if ret:
            available.append(i)
        cap.release()
    return available

class VideoWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Capture")
        self.capture = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.recording = False
        self.writer = None
        self.current_frame = None

        self.camera_combo = QComboBox()
        self._refresh_cameras()

        self.refresh_btn = QPushButton("Refresh Cameras")
        self.refresh_btn.clicked.connect(self._refresh_cameras)

        self.start_btn = QPushButton("Start Video Capture")
        self.start_btn.clicked.connect(self.start_capture)

        self.stop_btn = QPushButton("Stop Recording")
        self.stop_btn.clicked.connect(self.stop_capture)
        self.stop_btn.setEnabled(False)

        self.export_frames_btn = QPushButton("Export Frames")
        self.export_frames_btn.clicked.connect(self.export_frames)
        self.export_frames_btn.setEnabled(False)

        self.segment_btn = QPushButton("Run Segmentation (placeholder)")
        self.segment_btn.clicked.connect(self.run_segmentation)
        self.segment_btn.setEnabled(False)

        self.video_label = QLabel("No camera running")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 480)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.camera_combo)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(self.start_btn)
        top_layout.addWidget(self.stop_btn)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.export_frames_btn)
        bottom_layout.addWidget(self.segment_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.video_label)
        layout.addLayout(bottom_layout)

    def _refresh_cameras(self):
        self.camera_combo.clear()
        cams = probe_cameras()
        if not cams:
            self.camera_combo.addItem("No cameras found", -1)
        else:
            for c in cams:
                self.camera_combo.addItem(f"Camera {c}", c)

    def start_capture(self):
        idx = self.camera_combo.currentData()
        if idx is None or idx == -1:
            QMessageBox.warning(self, "No camera", "Please select a valid camera.")
            return

        self.capture = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not self.capture.isOpened():
            QMessageBox.critical(self, "Error", f"Cannot open camera {idx}")
            return

        # prepare writer (start recording immediately)
        out_path = DATA_DIR / "Recording.mp4"
        ret, frame = self.capture.read()
        if not ret:
            QMessageBox.critical(self, "Error", "Failed to read from camera.")
            self.capture.release()
            self.capture = None
            return

        h, w = frame.shape[:2]
        # Get actual FPS from camera
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        if not fps or fps < 1:
            fps = 30.0

        # Create data directory if it doesn't exist
        recordings_dir = DATA_DIR
        recordings_dir.mkdir(parents=True, exist_ok=True)

        # Create output file
        out_path = recordings_dir / "Recording.mp4"

        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.recording_writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
        if not self.recording_writer.isOpened():
            self.recording_writer = None
            QMessageBox.warning(self, "Warning", "VideoWriter could not be opened; recording disabled.")
            self.capture.release()
            return

        self.recording = True
        self.stop_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        self.export_frames_btn.setEnabled(False)
        self.segment_btn.setEnabled(False)

        self.current_frame = frame
        self._show_frame(frame)
        self.timer.start(int(1000 / max(1, fps)))

    def _update_frame(self):
        if self.capture is None:
            return
        ret, frame = self.capture.read()
        if not ret:
            return
        self.current_frame = frame
        if self.recording and self.writer is not None:
            try:
                self.writer.write(frame)
            except Exception:
                pass
        self._show_frame(frame)

    def _show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qt_img).scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.video_label.setPixmap(pix)

    def stop_capture(self):
        self.timer.stop()
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        if self.writer is not None:
            self.writer.release()
            self.writer = None
        self.recording = False
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        self.export_frames_btn.setEnabled(True)
        self.segment_btn.setEnabled(True)
        QMessageBox.information(self, "Stopped", "Recording stopped and saved to Data/")

    def export_frames(self):
        rec_file, _ = QFileDialog.getOpenFileName(self, "Select recording to export frames", str(DATA_DIR), "Video Files (*.mp4 *.avi)")
        if not rec_file:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Choose output folder for frames", str(DATA_DIR))
        if not out_dir:
            return
        self._extract_frames(str(rec_file), Path(out_dir))
        QMessageBox.information(self, "Exported", f"Frames exported to {out_dir}")

    def _extract_frames(self, video_path, out_dir: Path, step=1):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(video_path)
        video_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        idx = 0
        saved = 0

        # Match requested structure: Data/FrameTimestamp.csv (outside Segments)
        try:
            out_dir.relative_to(DATA_DIR)
            timestamps_path = DATA_DIR / "FrameTimestamp.csv"
        except Exception:
            timestamps_path = out_dir / "frame_timestamps.csv"

        csv_fp = open(timestamps_path, "w", encoding="utf-8", newline="")
        csv_writer = csv.writer(csv_fp)
        csv_writer.writerow([
            "segment_name",
            "frame_name",
            "video_frame_index",
            "timestamp_ms",
            "timestamp_s",
        ])
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                frame_name = f"frame_{idx:06d}.png"
                fname = out_dir / frame_name
                cv2.imwrite(str(fname), frame)

                pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                if (not pos_msec or pos_msec <= 0) and video_fps > 0:
                    pos_msec = (idx * 1000.0) / video_fps
                timestamp_s = (pos_msec / 1000.0) if pos_msec is not None else ""
                csv_writer.writerow([
                    "",
                    frame_name,
                    idx,
                    f"{pos_msec:.3f}" if pos_msec is not None else "",
                    f"{timestamp_s:.6f}" if timestamp_s != "" else "",
                ])

                saved += 1
            idx += 1
        cap.release()
        try:
            csv_fp.close()
        except Exception:
            pass
        return saved

    def run_segmentation(self):
        QMessageBox.information(self, "Segmentation", "Segmentation routine placeholder. Implement your model here.")

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = VideoWindow()
    w.show()
    sys.exit(app.exec())
import os
import cv2
import numpy as np
import time
import threading
import csv
import shutil
import json
import subprocess
from collections import deque
from typing import Optional
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFrame, QFileDialog,
    QProgressBar, QMessageBox, QTimeEdit, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QInputDialog, QTextEdit,
    QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QTime, QEvent
from PyQt6.QtGui import QImage, QPixmap, QIcon, QTextCursor
from geometry_store import load_geometry, save_geometry, get_start_size


class ArduinoFlasher(QThread):
    """Async Arduino flashing in a separate thread to keep UI responsive."""
    output_line = pyqtSignal(str)  # Emits output lines
    finished = pyqtSignal(int, str)  # (return_code, final_message)

    def __init__(self, cmd, timeout_s=180.0):
        super().__init__()
        self.cmd = cmd
        self.timeout_s = timeout_s

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
        except Exception as e:
            self.finished.emit(1, f"Failed to start command: {e}")
            return

        collected = []
        start_t = time.time()
        try:
            while True:
                if proc.stdout is not None:
                    try:
                        line = proc.stdout.readline()
                    except Exception:
                        break
                else:
                    line = ""

                if line:
                    collected.append(line)
                    self.output_line.emit(line.rstrip("\r\n"))

                ret = proc.poll()
                if ret is not None:
                    break

                if (time.time() - start_t) > float(self.timeout_s):
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    self.finished.emit(1, "Command timed out")
                    return

                time.sleep(0.01)

            # Read any remaining output
            try:
                if proc.stdout is not None:
                    remaining = proc.stdout.read() or ""
                    if remaining:
                        collected.append(remaining)
                        for remaining_line in remaining.split("\n"):
                            if remaining_line:
                                self.output_line.emit(remaining_line.rstrip("\r\n"))
            except Exception:
                pass

            output_text = "".join(collected).strip()
            self.finished.emit(int(proc.returncode or 0), output_text)
        finally:
            try:
                if proc.stdout is not None:
                    proc.stdout.close()
            except Exception:
                pass


class SegmentExtractor(QThread):
    progress = pyqtSignal(tuple)  # (segment_name, progress_value)
    finished_parsing = pyqtSignal(str)  # emits segment name when done

    def __init__(
        self,
        video_path,
        frames_output_folder,
        start_frame,
        end_frame,
        fps=2,
        name="",
        session_dir=None,
    ):
        super().__init__()
        self.video_path = video_path
        self.output_folder = frames_output_folder
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.fps = fps
        self.name = name
        self.session_dir = session_dir

    def calculate_SNR(self,frame):
        gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean = np.mean(gray_scale)
        std = np.std(gray_scale)
        if std ==0:
            return 0
        snr = 10 * np.log10((mean**2) / (std**2))
        return snr
    
    def calculate_sharpness(self,frame):
        gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lapacian_variance = cv2.Laplacian(gray_scale, cv2.CV_64F).var()
        return lapacian_variance
    
    def eval_frames(self):
        selected_frames = []
        rejected_frames = []

        for filename in os.listdir(self.output_folder):

            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.svg', '.webp', '.raw')):

                frame_path = os.path.join(self.output_folder, filename)
                frame = cv2.imread(frame_path)

                snr = self.calculate_SNR(frame)
                sharpness = self.calculate_sharpness(frame)

                if snr >= 25 and sharpness >= 100:
                    selected_frames.append((filename, snr, sharpness))

                else:
                    rejected_frames.append((filename, snr, sharpness))

        return selected_frames, rejected_frames

    def run(self):
        os.makedirs(self.output_folder, exist_ok=True)

        # Load recording-wide frame timestamps from Raw-Data
        recording_frame_ts = self._load_recording_frame_timestamps()
        # Load recording-wide IMU data from Raw-Data
        recording_imu_data = self._load_recording_imu_data()

        # Prepare averaged IMU CSV in Output-Data
        output_data_dir = None
        imu_output_fp = None
        imu_output_writer = None
        if self.session_dir and recording_imu_data:
            try:
                output_data_dir = Path(self.session_dir) / "Output-Data" / self.name
                output_data_dir.mkdir(parents=True, exist_ok=True)
                imu_output_path = output_data_dir / "averaged_imu.csv"
                imu_output_fp = open(imu_output_path, "w", encoding="utf-8", newline="")
                imu_output_writer = csv.writer(imu_output_fp)
                imu_output_writer.writerow([
                    "frame_name", "frame_timestamp_ms", 
                    "avg_QW", "avg_QX", "avg_QY", "avg_QZ",
                    "avg_WX", "avg_WY", "avg_WZ"
                ])
            except Exception:
                imu_output_fp = None
                imu_output_writer = None

        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

        video_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        interval = max(1, int(video_fps // self.fps)) if self.fps > 0 and video_fps > 0 else 1
        frame_count, saved_count = self.start_frame, 0

        try:
            while frame_count < self.end_frame:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % interval == 0:
                    frame_name = f"Frame{saved_count + 1}.png"
                    filename = os.path.join(self.output_folder, frame_name)
                    cv2.imwrite(filename, frame)

                    pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if (not pos_msec or pos_msec <= 0) and video_fps > 0:
                        pos_msec = (frame_count * 1000.0) / video_fps

                    # Get timestamp from recording FrameTimestamp.csv for this frame_count
                    recording_ts_ms = recording_frame_ts.get(frame_count, pos_msec)
                    
                    # Find 10 closest IMU samples and average them
                    if imu_output_writer and recording_imu_data:
                        try:
                            avg_imu = self._get_averaged_imu(recording_ts_ms, recording_imu_data, k=10)
                            if avg_imu:
                                imu_output_writer.writerow([
                                    frame_name, f"{recording_ts_ms:.3f}",
                                    f"{avg_imu[0]:.6f}", f"{avg_imu[1]:.6f}", f"{avg_imu[2]:.6f}", f"{avg_imu[3]:.6f}",
                                    f"{avg_imu[4]:.6f}", f"{avg_imu[5]:.6f}", f"{avg_imu[6]:.6f}"
                                ])
                        except Exception:
                            pass

                    saved_count += 1

                progress_val = int(((frame_count - self.start_frame) / (self.end_frame - self.start_frame)) * 100)
                self.progress.emit((self.name, progress_val))

                frame_count += 1
        finally:
            try:
                if imu_output_fp is not None:
                    imu_output_fp.close()
            except Exception:
                pass

        cap.release()
        selected, rejected = self.eval_frames()
        self.finished_parsing.emit(self.name)

    def _load_recording_frame_timestamps(self):
        """Load frame timestamps from Raw-Data/FrameTimestamp.csv, keyed by frame index."""
        frame_ts = {}
        if not self.session_dir:
            return frame_ts
        try:
            raw_data_dir = Path(self.session_dir) / "Raw-Data"
            ts_path = raw_data_dir / "FrameTimestamp.csv"
            if not ts_path.exists():
                return frame_ts
            with open(ts_path, "r", encoding="utf-8") as fp:
                reader = csv.reader(fp)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            frame_idx = int(row[0])
                            ts_ms = float(row[1])
                            frame_ts[frame_idx] = ts_ms
                        except Exception:
                            pass
        except Exception:
            pass
        return frame_ts

    def _load_recording_imu_data(self):
        """Load IMU data from Raw-Data/IMUTimeStamp.csv as list of (timestamp_ms, [qw, qx, qy, qz, wx, wy, wz])."""
        imu_data = []
        if not self.session_dir:
            return imu_data
        try:
            raw_data_dir = Path(self.session_dir) / "Raw-Data"
            imu_path = raw_data_dir / "IMUTimeStamp.csv"
            if not imu_path.exists():
                return imu_data
            with open(imu_path, "r", encoding="utf-8") as fp:
                reader = csv.reader(fp)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 8:
                        try:
                            ts_ms = float(row[0].strip())
                            qw = float(row[1].strip())
                            qx = float(row[2].strip())
                            qy = float(row[3].strip())
                            qz = float(row[4].strip())
                            wx = float(row[5].strip())
                            wy = float(row[6].strip())
                            wz = float(row[7].strip())
                            imu_data.append((ts_ms, [qw, qx, qy, qz, wx, wy, wz]))
                        except Exception:
                            pass
        except Exception:
            pass
        return imu_data

    def _get_averaged_imu(self, target_ts_ms, imu_data, k=10):
        """Find k closest IMU samples by timestamp and return their average.
        Returns [avg_qw, avg_qx, avg_qy, avg_qz, avg_wx, avg_wy, avg_wz] or None.
        """
        if not imu_data:
            return None
        # Compute distances and sort
        distances = [(abs(ts - target_ts_ms), idx) for idx, (ts, _) in enumerate(imu_data)]
        distances.sort()
        # Take k closest
        closest_indices = [idx for _, idx in distances[:k]]
        if not closest_indices:
            return None
        # Average the IMU values
        sums = [0.0] * 7
        for idx in closest_indices:
            _, vals = imu_data[idx]
            for i in range(7):
                sums[i] += vals[i]
        count = len(closest_indices)
        return [s / count for s in sums]


def _sanitize_filename_component(value: str) -> str:
    # Windows-safe-ish filename component; keep it minimal.
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value).strip(" _")


class SerialPortReader:
    """Single shared serial reader.

    - Always reads lines into a buffer for UI consumption.
    - Optionally logs CSV-like lines to a file when enabled.
    """

    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.5) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ser = None

        self._buffer = deque(maxlen=5000)
        self._buf_lock = threading.Lock()

        self._log_fp = None
        self._log_lock = threading.Lock()

        # Time sync (Arduino micros -> host perf_counter micros -> recording-relative ms)
        self._sync_offset_us: Optional[float] = None
        self._record_start_host_us: Optional[float] = None
        self._imu_first_logged_ms: Optional[float] = None
        self._last_logged_ms: Optional[float] = None
        self._logged_rows: int = 0

    def set_time_sync(self, sync_offset_us: Optional[float], record_start_host_us: Optional[float]) -> None:
        # sync_offset_us maps: host_us ~= arduino_us + sync_offset_us
        self._sync_offset_us = sync_offset_us
        self._record_start_host_us = record_start_host_us
        self._imu_first_logged_ms = None
        self._last_logged_ms = None
        self._logged_rows = 0

    def flush_input(self) -> None:
        # Clear both pyserial RX buffer and in-memory buffer.
        try:
            if self._ser is not None:
                self._ser.reset_input_buffer()
        except Exception:
            pass
        with self._buf_lock:
            self._buffer.clear()

    def send_line(self, text: str) -> None:
        try:
            if self._ser is None:
                return
            payload = (text.rstrip("\r\n") + "\n").encode("utf-8", errors="ignore")
            self._ser.write(payload)
            self._ser.flush()
        except Exception:
            pass

    def start(self) -> None:
        if serial is None:
            raise RuntimeError("pyserial is not installed")
        if self._thread and self._thread.is_alive():
            return
        # Open serial WITHOUT toggling DTR/RTS to prevent ESP32 auto-reset
        # (CP2102 boards reset the MCU when DTR transitions, which reinitialises
        # the BNO055 and causes it to output zeros during NDOF warmup).
        ser = serial.Serial()
        ser.port = self.port
        ser.baudrate = self.baud
        ser.timeout = self.timeout
        ser.dtr = False
        ser.rts = False
        ser.open()
        self._ser = ser
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.disable_logging()
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        try:
            if self._ser is not None and getattr(self._ser, "is_open", False):
                self._ser.close()
        except Exception:
            pass
        self._ser = None

    def enable_logging(self, csv_path: Path, header: str) -> None:
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_lock:
            self._log_fp = open(csv_path, "w", encoding="utf-8", newline="\n")
            self._log_fp.write(header.rstrip("\n") + "\n")
            self._log_fp.flush()
        self._imu_first_logged_ms = None
        self._last_logged_ms = None
        self._logged_rows = 0

    def disable_logging(self) -> None:
        with self._log_lock:
            try:
                if self._log_fp is not None:
                    self._log_fp.close()
            except Exception:
                pass
            self._log_fp = None

    def pop_lines(self) -> List[str]:
        with self._buf_lock:
            if not self._buffer:
                return []
            lines = list(self._buffer)
            self._buffer.clear()
            return lines

    def get_logging_stats(self) -> tuple[int, Optional[float]]:
        return int(self._logged_rows), self._last_logged_ms

    def _maybe_log_line(self, line: str) -> None:
        if not line:
            return
        low = line.strip().lower()
        if low.startswith("timestamp") or low.startswith("t_us"):
            return
        if "," not in line:
            return
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 8:
            return

        # Convert Arduino timestamp (micros) -> recording-relative timestamp (ms).
        try:
            arduino_us = float(parts[0])
            if self._sync_offset_us is not None and self._record_start_host_us is not None:
                host_us = arduino_us + float(self._sync_offset_us)
                rel_ms = (host_us - float(self._record_start_host_us)) / 1000.0
            else:
                # Fallback: no host sync available, keep Arduino-relative timing in ms.
                rel_ms = arduino_us / 1000.0

            if self._imu_first_logged_ms is None:
                self._imu_first_logged_ms = rel_ms

            rel_ms = rel_ms - float(self._imu_first_logged_ms)
            if rel_ms < 0:
                rel_ms = 0.0

            parts[0] = str(int(round(rel_ms)))
            self._last_logged_ms = float(rel_ms)
            self._logged_rows += 1
        except Exception:
            pass

        with self._log_lock:
            if self._log_fp is None:
                return
            try:
                self._log_fp.write(",".join(parts[:8]) + "\n")
                self._log_fp.flush()
            except Exception:
                pass

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                raw = self._ser.readline() if self._ser is not None else b""
            except Exception:
                continue
            if not raw:
                continue

            try:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            except Exception:
                line = str(raw).rstrip("\r\n")

            with self._buf_lock:
                self._buffer.append(line)

            self._maybe_log_line(line)

class VideoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Surgical Imaging Interface")
        self.resize(1000, 600)

        # Data session (Data/<Session>/...)
        self.session_name: str = ""
        self.session_base_name: str = ""  # Base name without timestamp
        self.session_dir: Optional[Path] = None
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #404040;
            }
            QWidget {
                background-color: #404040;
                color: #ffffff;
            }
            QFrame {
                background-color: #606060;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                color: #000000;
            }
            QPushButton[objectName="play_pause_button"],
            QPushButton[objectName="back_button"],
            QPushButton[objectName="forward_button"] {
                font-size: 20px;
                font-weight: 900;
                padding: 12px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
            QLabel {
                color: #ffffff;
                background-color: transparent;
                border: none;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #606060;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #c0c0c0;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QListWidget {
                background-color: #505050;
                border: 1px solid #606060;
                border-radius: 4px;
                color: #ffffff;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #606060;
            }
            QListWidget::item:selected {
                background-color: #708090;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                padding: 4px;
                color: #000000;
            }
        """)

        # restore persisted geometry if available (best-effort)
        g = load_geometry()
        if g:
            try:
                self.setGeometry(*g)
            except Exception:
                pass

        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # --- Side Panel ---
        side_panel = QFrame()
        side_panel.setStyleSheet("""
            QFrame {
                background-color: #606060;
                border: 0.5px solid #000000;
                border-radius: 8px;
            }
        """)
        side_layout = QVBoxLayout(side_panel)

        self.load_button = QPushButton("Load Video")
        self.load_button.clicked.connect(self.load_video_file)
        side_layout.addWidget(self.load_button)

        # Collapsible Setup System section
        self.setup_system_collapsed = True
        self.setup_system_button = QPushButton("Setup System")
        self.setup_system_button.setFixedHeight(40)
        self.setup_system_button.clicked.connect(self.toggle_setup_system)
        side_layout.addWidget(self.setup_system_button)

        # Setup System content (hidden by default)
        self.setup_system_content = QWidget()
        setup_layout = QVBoxLayout(self.setup_system_content)
        setup_layout.setContentsMargins(5, 5, 5, 5)
        setup_layout.setSpacing(6)

        # Camera dropdown
        camera_label = QLabel("Select Camera:")
        camera_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        self.setup_camera_combo = QComboBox()
        setup_layout.addWidget(camera_label)
        setup_layout.addWidget(self.setup_camera_combo)

        # COM port dropdown
        com_label = QLabel("Select COM Port:")
        com_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        self.setup_comport_combo = QComboBox()
        setup_layout.addWidget(com_label)
        setup_layout.addWidget(self.setup_comport_combo)

        # Refresh and Save buttons
        button_layout = QHBoxLayout()
        self.setup_refresh_button = QPushButton("Refresh")
        self.setup_refresh_button.clicked.connect(self.refresh_setup_dropdowns)
        self.setup_save_button = QPushButton("Save Setup")
        self.setup_save_button.clicked.connect(self.save_setup_and_start_camera)
        button_layout.addWidget(self.setup_refresh_button)
        button_layout.addWidget(self.setup_save_button)
        setup_layout.addLayout(button_layout)

        self.setup_system_content.setVisible(False)
        side_layout.addWidget(self.setup_system_content)

        # Serial Monitor toggle button (above Recording)
        self.serial_monitor_button = QPushButton("Serial Monitor")
        self.serial_monitor_button.setFixedHeight(40)
        self.serial_monitor_button.clicked.connect(self.toggle_serial_monitor_panel)
        side_layout.addWidget(self.serial_monitor_button)

        # Collapsible Recording section
        self.recording_collapsed = True
        self.recording_button = QPushButton("Recording")
        self.recording_button.setFixedHeight(40)
        self.recording_button.clicked.connect(self.toggle_recording_panel)
        side_layout.addWidget(self.recording_button)

        # Recording content (hidden by default)
        self.recording_content = QWidget()
        recording_layout = QVBoxLayout(self.recording_content)
        recording_layout.setContentsMargins(5, 5, 5, 5)
        recording_layout.setSpacing(6)

        # Recording controls
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Session Name:"))
        self.session_name_input = QLineEdit()
        self.session_name_input.setPlaceholderText("e.g., WhiteCylinder")
        session_row.addWidget(self.session_name_input)
        recording_layout.addLayout(session_row)

        btn_layout = QHBoxLayout()
        self.start_record_btn = QPushButton("Start Recording")
        self.start_record_btn.clicked.connect(self.start_recording)
        self.start_record_btn.setEnabled(True)

        self.stop_record_btn = QPushButton("End Recording")
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.stop_record_btn.setEnabled(False)

        btn_layout.addWidget(self.start_record_btn)
        btn_layout.addWidget(self.stop_record_btn)
        recording_layout.addLayout(btn_layout)

        self.recording_content.setVisible(False)
        side_layout.addWidget(self.recording_content)

        # Collapsible Segments section
        self.segments_collapsed = True
        self.segments_button = QPushButton("Segments")
        self.segments_button.setFixedHeight(40)  # Same height as other buttons
        self.segments_button.clicked.connect(self.toggle_segments)
        side_layout.addWidget(self.segments_button)
        
        self.segment_list = QListWidget()
        self.segment_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.segment_list.customContextMenuRequested.connect(self.show_segment_menu)
        self.segment_list.setVisible(False)  # Start collapsed
        side_layout.addWidget(self.segment_list)

        # Collapsible Extract Frames section
        self.extract_collapsed = True
        self.extract_button = QPushButton("Extract Frames")
        self.extract_button.setFixedHeight(40)
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self.toggle_extract)
        self.update_extract_button_state(False)
        side_layout.addWidget(self.extract_button)
        
        # Extract frames content (progress bar and cancel button)
        self.extract_content = QWidget()
        extract_layout = QVBoxLayout(self.extract_content)
        extract_layout.setContentsMargins(5, 5, 5, 5)
        extract_layout.setSpacing(5)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        extract_layout.addWidget(self.progress)
        
        self.cancel_button = QPushButton("Cancel Extraction")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_extraction)
        extract_layout.addWidget(self.cancel_button)
        
        self.extract_content.setVisible(False)  # Start collapsed
        side_layout.addWidget(self.extract_content)

        self.view_frames_button = QPushButton("View Extracted Frames")
        self.view_frames_button.setEnabled(False)
        self.view_frames_button.clicked.connect(self.open_frame_browser)
        self.update_view_frames_button_state(False)
        side_layout.addWidget(self.view_frames_button)

        self.reconstruct_button = QPushButton("Start 3D Reconstruction")
        self.reconstruct_button.setEnabled(False)
        self.reconstruct_button.clicked.connect(self.start_reconstruction)
        self.update_reconstruct_button_state(False)
        side_layout.addWidget(self.reconstruct_button)

        # Add spacer to push terminal to bottom
        side_layout.addStretch(1)
        
        # Terminal section at bottom - fixed position
        terminal_label = QLabel("Terminal")
        terminal_label.setStyleSheet("""
            QLabel {
                background-color: #c0c0c0;
                color: #000000;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
            }
        """)
        side_layout.addWidget(terminal_label)
        
        self.terminal_display = QTextEdit()
        self.terminal_display.setReadOnly(True)
        self.terminal_display.setFixedHeight(120)
        self.terminal_display.setStyleSheet("""
            QTextEdit {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #606060;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
        """)
        side_layout.addWidget(self.terminal_display)

        # --- Central Viewer ---
        self.video_layout = QVBoxLayout()
        self.viewer_label = QLabel("Video Preview")
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_label.setMinimumSize(400, 300)
        self.viewer_label.setScaledContents(False)
        self.viewer_label.setStyleSheet("""
            QLabel {
                background-color: #404040;
                border: 0.5px solid #000000;
                border-radius: 4px;
                color: #c0c0c0;
                font-size: 14px;
            }
        """)
        self.video_layout.addWidget(self.viewer_label, 4)

        timebar_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00:00")
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setEnabled(False)
        self.timeline_slider.sliderReleased.connect(self.scrub_video)
        self.total_time_label = QLabel("00:00:00")

        timebar_layout.addWidget(self.current_time_label)
        timebar_layout.addWidget(self.timeline_slider, 1)
        timebar_layout.addWidget(self.total_time_label)
        self.video_layout.addLayout(timebar_layout)

        controls_layout = QHBoxLayout()
        self.back_button = QPushButton("<<")
        self.back_button.setObjectName("back_button")
        self.back_button.setFixedSize(60, 40)
        
        self.play_pause_button = QPushButton("▶")
        self.play_pause_button.setObjectName("play_pause_button")
        self.play_pause_button.setFixedSize(60, 40)
        
        self.forward_button = QPushButton(">>")
        self.forward_button.setObjectName("forward_button")
        self.forward_button.setFixedSize(60, 40)

        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.back_button.clicked.connect(lambda: self.skip_frames(-self.fps))
        self.forward_button.clicked.connect(lambda: self.skip_frames(self.fps))

        controls_layout.addWidget(self.back_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.forward_button)
        self.video_layout.addLayout(controls_layout)

        # --- Segment Controls ---
        segment_controls = QHBoxLayout()
        self.segment_name_input = QLineEdit()
        self.segment_name_input.setPlaceholderText("Segment name")
        self.start_time_input = QTimeEdit()
        self.start_time_input.setDisplayFormat("HH:mm:ss")
        self.end_time_input = QTimeEdit()
        self.end_time_input.setDisplayFormat("HH:mm:ss")
        self.add_segment_btn = QPushButton("Add Segment")
        self.add_segment_btn.clicked.connect(self.add_segment)

        segment_controls.addWidget(self.segment_name_input)
        segment_controls.addWidget(QLabel("Start"))
        segment_controls.addWidget(self.start_time_input)
        segment_controls.addWidget(QLabel("End"))
        segment_controls.addWidget(self.end_time_input)
        segment_controls.addWidget(self.add_segment_btn)
        self.video_layout.addLayout(segment_controls)

        main_layout.addWidget(side_panel, 1)
        main_layout.addLayout(self.video_layout, 4)

        # Serial Monitor panel on the right (hidden by default)
        self.serial_monitor_panel = QFrame()
        self.serial_monitor_panel.setStyleSheet("""
            QFrame {
                background-color: #303030;
                border: 0.5px solid #000000;
                border-radius: 8px;
            }
            QLabel {
                font-weight: bold;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #111111;
                color: #00ff66;
                border: 1px solid #2a2a2a;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        sm_layout = QVBoxLayout(self.serial_monitor_panel)
        sm_layout.setContentsMargins(8, 8, 8, 8)
        sm_layout.setSpacing(6)
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Serial Monitor"))
        header_row.addStretch(1)

        self.serial_monitor_clear_btn = QPushButton("Clear")
        self.serial_monitor_clear_btn.setFixedHeight(28)
        self.serial_monitor_clear_btn.clicked.connect(lambda: self.serial_monitor_text.clear())
        header_row.addWidget(self.serial_monitor_clear_btn)

        self.serial_monitor_autoscroll_btn = QPushButton("Auto-scroll: On")
        self.serial_monitor_autoscroll_btn.setFixedHeight(28)
        self.serial_monitor_autoscroll_btn.clicked.connect(self.toggle_serial_monitor_autoscroll)
        header_row.addWidget(self.serial_monitor_autoscroll_btn)

        sm_layout.addLayout(header_row)
        self.serial_monitor_text = QTextEdit()
        self.serial_monitor_text.setReadOnly(True)
        sm_layout.addWidget(self.serial_monitor_text, 1)
        self.serial_monitor_panel.setVisible(False)
        main_layout.addWidget(self.serial_monitor_panel, 2)

        self._serial_monitor_timer = QTimer(self)
        self._serial_monitor_timer.timeout.connect(self._serial_monitor_tick)
        self.setCentralWidget(central_widget)

        # State
        self.video_path = None
        self.cap = None
        self.fps = 30
        self.total_frames = 0
        self.current_frame = 0
        self.segments = []
        self.worker_threads = []
        self.segment_progress = {}
        self.completed_segments = 0
        self.current_video_id = None
        self.selected_frames = {}
        
        # Setup System state
        self.selected_camera_idx = None
        self.selected_com_port = None

        # Recording state
        self.is_recording = False
        self.recording_writer = None
        self.recording_file_path = None
        self.frame_csv_path: Optional[str] = None
        self._frame_ts_fp = None
        self._frame_ts_writer = None
        self._record_frame_index = 0
        self._record_last_frame_ts_ms = 0.0
        self._record_start_perf = None

        # Serial capture (shared between monitor + CSV logging)
        self.serial_monitor_visible = False
        self.serial_monitor_autoscroll = True
        self._serial_reader: Optional[SerialPortReader] = None
        self.serial_csv_path: Optional[str] = None
        self._is_flashing_arduino = False
        
        # Flash async attributes
        self._flash_pending_start_camera = False
        self._flash_pending_camera_idx = None
        self._flash_compile_cmd = []
        self._flash_upload_cmd = []
        self._flash_com_port = None
        self._flash_compile_ok = False
        self._flash_upload_ok = False
        self._flashing_stage = None
        self.flash_thread = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.slider_base_style = """
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #606060;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #c0c0c0;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
        """
        self.timeline_slider.setStyleSheet(self.slider_base_style)

        # Disable recording and segments on startup
        self.set_recording_enabled(False)
        self.set_segments_enabled(False)

    def pause_video(self):
        if self.timer.isActive():
            self.timer.stop()

    def closeEvent(self, event):
        # Ensure serial thread/file handles are stopped
        try:
            self._stop_serial_capture(stop_reader=True)
        except Exception:
            pass
        try:
            geo = self.geometry()
            save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        except Exception:
            pass
        super().closeEvent(event)

    def resizeEvent(self, event):
        try:
            geo = self.geometry()
            save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        except Exception:
            pass
        super().resizeEvent(event)

    def moveEvent(self, event):
        try:
            geo = self.geometry()
            save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        except Exception:
            pass
        super().moveEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            try:
                geo = self.geometry()
                save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
            except Exception:
                pass
        super().changeEvent(event)

    def update_segment_progress(self, data):
        name, value = data
        self.segment_progress[name] = value
        avg = sum(self.segment_progress.values()) / len(self.segment_progress)
        self.progress.setValue(int(avg))

    def on_finished_parsing(self, name):
        self.completed_segments += 1
        if self.completed_segments == len(self.segments):
            self.progress.setVisible(False)
            self.cancel_button.setVisible(False)
            self.load_button.setEnabled(True)
            self.update_view_frames_button_state(True)  # Enable view frames button
            self.update_extract_button_state(False)  # Disable extract button after completion
            # Keep reconstruction button enabled
            # Collapse the extract widget
            self.extract_collapsed = True
            self.extract_content.setVisible(False)
            self.extract_button.setText("Extract Frames")
            self.log_message("Frame extraction finished")
            QMessageBox.information(self, "Done", "All segments have been extracted.")
    
    def log_frame_selection_change(self, segment_name, selected_count, total_count):
        """Log changes to frame selection"""
        self.log_message(f"Frame selection updated for {segment_name}: {selected_count}/{total_count} frames selected")

    def _segment_frames_output_dir(self, seg: dict) -> str:
        """Return folder path where extracted frames for a segment are stored."""
        session_dir = self._get_session_dir()
        # Use clean segment name for Output-Data folder
        name = str(seg.get("name", "segment")).strip() or "segment"
        safe_name = _sanitize_filename_component(name.replace(" ", "_")) or "segment"
        frames_dir = session_dir / "Output-Data" / safe_name
        frames_dir.mkdir(parents=True, exist_ok=True)
        return str(frames_dir)

    def _segment_folder_name(self, seg: dict) -> str:
        name = str(seg.get("name", "segment")).strip() or "segment"
        safe_name = _sanitize_filename_component(name.replace(" ", "_")) or "segment"
        try:
            start_str = seg["start"].toString("HH-mm-ss")
            end_str = seg["end"].toString("HH-mm-ss")
        except Exception:
            start_str = "00-00-00"
            end_str = "00-00-00"
        return f"{safe_name}__{start_str}__{end_str}"

    def _get_session_dir(self) -> Path:
        # Read from UI if available
        try:
            name = self.session_name_input.text().strip()
        except Exception:
            name = ""

        # Normalize empty name to "Session"
        if not name:
            name = "Session"

        # If we already have a session directory AND the base name matches, reuse it
        current_base = getattr(self, "session_base_name", "")
        if (getattr(self, "session_dir", None) is not None and 
            current_base and 
            name == current_base):
            try:
                return Path(self.session_dir)
            except Exception:
                pass

        # Create new session with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = _sanitize_filename_component(name) or "Session"
        safe = _sanitize_filename_component(f"{base}_{timestamp}") or f"Session_{timestamp}"
        
        self.session_base_name = name  # Store the base name for future comparisons
        self.session_name = safe
        self.session_dir = DATA_DIR / safe
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir

    def open_frame_browser(self):
        from frame_browser import FrameBrowser
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Load a video before viewing frames.")
            return

        segments = [(seg["name"], self._segment_frames_output_dir(seg)) for seg in self.segments]

        initial_selection = {folder: images.copy() for folder, images in self.selected_frames.items()}
        # Filtering hook: if you add a filter/scoring routine, populate initial_selection
        # with any frames you wish to auto-uncheck before opening the browser.
        # Example (disabled):
        # for seg in self.segments:
        #     folder_path = self._segment_frames_output_dir(seg)
        #     results = run_filter(folder_path)
        #     initial_selection[folder_path] = results

        browser = FrameBrowser(
            segments,
            video_id=self.current_video_id or self.video_path,
            parent=self,
            initial_selection=initial_selection
        )
        browser.exec()

        chosen = browser.selected_frames
        self.selected_frames = chosen


    def start_extraction(self):
        if not self.segments:
            QMessageBox.warning(self, "No Segments", "Please define at least one segment before extracting.")
            return

        self.pause_video()
        self.log_message("Frame extraction started")
        self.load_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.progress.setVisible(True)
        # Enable reconstruction button when extraction starts
        self.update_reconstruct_button_state(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.segment_progress.clear()
        self.completed_segments = 0
        self.worker_threads = []

        for seg in self.segments:
            name = seg["name"]
            start_sec = QTime(0, 0).secsTo(seg["start"])
            end_sec = QTime(0, 0).secsTo(seg["end"])
            start_frame = int(start_sec * self.fps)
            end_frame = int(end_sec * self.fps)
            frames_folder = self._segment_frames_output_dir(seg)

            worker = SegmentExtractor(
                self.video_path,
                frames_folder,
                start_frame,
                end_frame,
                fps=2,
                name=name,
                session_dir=getattr(self, 'session_dir', None),
            )
            worker.progress.connect(self.update_segment_progress)
            worker.finished_parsing.connect(self.on_finished_parsing)
            self.worker_threads.append(worker)
            worker.start()

    def load_video_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        if file_name:
            self.load_video_from_path(file_name)

    def load_video_from_path(self, file_name):
        # Load a video file path into the player (shared by file dialog and auto-load)
        self.video_path = file_name
        self.current_video_id = os.path.abspath(file_name)
        self.cap = cv2.VideoCapture(file_name)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        if not fps or fps < 1:
            fps = 30.0
        self.fps = fps
        self.current_frame = 0
        # Reset any previous frame selections when a new video is loaded
        self.selected_frames = {}

        self.timeline_slider.setMaximum(max(0, self.total_frames - 1))
        self.timeline_slider.setEnabled(True)

        self.segment_list.clear()
        self.segments = []

        duration_seconds = int(self.total_frames / max(1.0, self.fps))
        self.total_time_label.setText(self.seconds_to_time(duration_seconds))
        self.refresh_timeline_highlight()

        # Require user-defined segments before extraction
        self.update_extract_button_state(False)
        self.update_view_frames_button_state(False)  # Disabled until frames extracted
        self.update_reconstruct_button_state(False)  # Disabled until extraction starts
        self.log_message("Video loaded")

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = self.cap.read()
        if ret:
            self.update_preview(frame)
            self.current_time_label.setText("00:00:00")

        # Segments should be usable after loading a video
        self.set_segments_enabled(True)

        # Ensure video is paused at the beginning; user presses Play
        if self.timer.isActive():
            self.timer.stop()
        try:
            self.play_pause_button.setText("▶")
        except Exception:
            pass

    def add_segment(self):
        name = self.segment_name_input.text().strip() or f"Segment {len(self.segments)+1}"
        start = self.start_time_input.time()
        end = self.end_time_input.time()
        if start >= end:
            QMessageBox.warning(self, "Invalid Segment", "Start time must be before end time.")
            return
        self.segments.append({"name": name, "start": start, "end": end})
        item = QListWidgetItem(f"{name}: {start.toString('HH:mm:ss')} → {end.toString('HH:mm:ss')}")
        self.segment_list.addItem(item)
        self.segment_name_input.clear()
        self.update_extract_button_state(True)  # Re-enable extract button when segments change
        # Update height if widget is expanded
        if not self.segments_collapsed:
            self.update_segment_list_height()
        self.log_message(f"{name} added")
        self.refresh_timeline_highlight()

    def update_extract_button_state(self, enabled):
        """Update extract button state and styling"""
        self.extract_button.setEnabled(enabled)
        if enabled:
            # Normal button styling - black text
            self.extract_button.setStyleSheet("""
                QPushButton {
                    background-color: #c0c0c0;
                    color: #000000;
                    border: 1px solid #a0a0a0;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)
        else:
            # Disabled styling - darker grey text
            self.extract_button.setStyleSheet("""
                QPushButton {
                    background-color: #c0c0c0;
                    color: #808080;
                    border: 1px solid #a0a0a0;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)
    
    def update_view_frames_button_state(self, enabled):
        """Update view frames button state and styling"""
        self.view_frames_button.setEnabled(enabled)
        if enabled:
            # Normal button styling - black text
            self.view_frames_button.setStyleSheet("""
                QPushButton {
                    background-color: #c0c0c0;
                    color: #000000;
                    border: 1px solid #a0a0a0;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QPushButton:pressed {
                    background-color: #b0b0b0;
                }
            """)
        else:
            # Disabled styling - darker grey text
            self.view_frames_button.setStyleSheet("""
                QPushButton {
                    background-color: #c0c0c0;
                    color: #808080;
                    border: 1px solid #a0a0a0;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)
    
    def update_reconstruct_button_state(self, enabled):
        """Update reconstruction button state and styling"""
        self.reconstruct_button.setEnabled(enabled)
        if enabled:
            # Normal button styling - black text
            self.reconstruct_button.setStyleSheet("""
                QPushButton {
                    background-color: #c0c0c0;
                    color: #000000;
                    border: 1px solid #a0a0a0;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QPushButton:pressed {
                    background-color: #b0b0b0;
                }
            """)
        else:
            # Disabled styling - darker grey text
            self.reconstruct_button.setStyleSheet("""
                QPushButton {
                    background-color: #c0c0c0;
                    color: #808080;
                    border: 1px solid #a0a0a0;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)
    
    def log_message(self, message):
        """Add timestamped message to terminal"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        self.terminal_display.append(full_message)
        # Auto-scroll to bottom
        cursor = self.terminal_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.terminal_display.setTextCursor(cursor)
    
    def toggle_extract(self):
        """Toggle the extract frames section or start extraction"""
        if not self.segments:
            QMessageBox.warning(self, "No Segments", "Please define at least one segment before extracting.")
            return
        if self.extract_button.isEnabled():
            # If button is enabled and collapsed, expand and start extraction
            if self.extract_collapsed:
                self.extract_collapsed = False
                self.extract_content.setVisible(True)
                self.extract_button.setText("Extract Frames ▼")
                self.start_extraction()
            else:
                # If already expanded, just collapse
                self.extract_collapsed = True
                self.extract_content.setVisible(False)
                self.extract_button.setText("Extract Frames")
    
    def update_segment_list_height(self):
        """Adjust segment list height based on number of items"""
        count = self.segment_list.count()
        if count == 0:
            # Minimum height for at least 1 item
            item_height = 40
        else:
            # Calculate height based on actual items
            item_height = self.segment_list.sizeHintForRow(0) if count > 0 else 40
        
        # Set height: spacing + border + (item_height * count), with minimum of 1 item
        total_height = max(item_height * max(count, 1) + 10, 50)
        # Cap at reasonable maximum (e.g., 5 items)
        max_height = item_height * 5 + 10
        self.segment_list.setFixedHeight(min(total_height, max_height))

    def refresh_timeline_highlight(self):
        """Highlight slider regions for defined segments."""
        if not self.total_frames:
            self.timeline_slider.setStyleSheet(self.slider_base_style)
            return

        total = max(1, self.total_frames - 1)
        stops = [(0.0, "#606060")]
        epsilon = 1.0 / max(10_000, total)  # tiny, stays within [0,1]
        for seg in self.segments:
            start_sec = QTime(0, 0).secsTo(seg["start"])
            end_sec = QTime(0, 0).secsTo(seg["end"])
            start_frame = max(0, int(start_sec * self.fps))
            end_frame = max(start_frame + 1, int(end_sec * self.fps))
            start_ratio = max(0.0, min(1.0, start_frame / total))
            end_ratio = max(start_ratio + epsilon, min(1.0, end_frame / total))
            stops.extend([
                (start_ratio, "#606060"),
                (min(1.0, start_ratio + epsilon), "#80c080"),
                (end_ratio, "#80c080"),
                (min(1.0, end_ratio + epsilon), "#606060"),
            ])
        stops.append((1.0, "#606060"))
        stops = sorted({(pos, color) for pos, color in stops}, key=lambda x: x[0])
        stop_str = ",\n        ".join(f"stop:{pos:.4f} {color}" for pos, color in stops)
        style = f"""
            QSlider::groove:horizontal {{
                border: 1px solid #999999;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    {stop_str});
                margin: 2px 0;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: #c0c0c0;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }}
        """
        self.timeline_slider.setStyleSheet(style)
    
    def toggle_segments(self):
        """Toggle the visibility of the segments list"""
        self.segments_collapsed = not self.segments_collapsed
        self.segment_list.setVisible(not self.segments_collapsed)
        
        if self.segments_collapsed:
            self.segments_button.setText("Segments")
        else:
            self.segments_button.setText("Segments ▼")
            # Adjust height based on number of segments
            self.update_segment_list_height()
    
    def show_segment_menu(self, pos):
        item = self.segment_list.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.segment_list.mapToGlobal(pos))
        index = self.segment_list.row(item)
        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Rename Segment", "New name:")
            if ok and new_name:
                self.segments[index]["name"] = new_name
                item.setText(f"{new_name}: {self.segments[index]['start'].toString('HH:mm:ss')} → {self.segments[index]['end'].toString('HH:mm:ss')}")
        elif action == delete_action:
            self.segments.pop(index)
            self.segment_list.takeItem(index)
            self.refresh_timeline_highlight()

    def cancel_extraction(self):
        for worker in self.worker_threads:
            if worker.isRunning():
                worker.terminate()
                worker.wait()
        # Extraction cancelled
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self.load_button.setEnabled(True)
        # Collapse the extract widget
        self.extract_collapsed = True
        self.extract_content.setVisible(False)
        self.extract_button.setText("Extract Frames")
        self.log_message("Frame extraction cancelled")
        self.cancel_button.setVisible(False)

    def start_reconstruction(self):
        # Save current geometry before transitioning
        geo = self.geometry()
        save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        
        # Open the reconstruction window (separate UI) without checking selected frames.
        try:
            from reconstruction_window import ReconstructionWindow
        except Exception as e:
            QMessageBox.warning(self, "Cannot Open Reconstruction", f"Failed to import reconstruction UI: {e}")
            return

        # Directly show the reconstruction UI and hide this window.
        self.recon_window = ReconstructionWindow(parent=self)
        self.recon_window.show()
        # Keep the video window open to reduce perceived lag and allow easy return.

    def update_preview(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(self.viewer_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.viewer_label.setPixmap(pixmap)

    # --- Setup System methods (collapsible panel) ---
    def toggle_setup_system(self):
        """Toggle the Setup System section visibility"""
        self.setup_system_collapsed = not self.setup_system_collapsed
        self.setup_system_content.setVisible(not self.setup_system_collapsed)
        if self.setup_system_collapsed:
            self.setup_system_button.setText("Setup System")
        else:
            self.setup_system_button.setText("Setup System ▼")

    def get_available_cameras(self):
        """Get list of available cameras"""
        cams = []
        try:
            cams = probe_cameras()
        except Exception:
            pass
        return cams

    def get_available_comports(self):
        """Get list of available COM ports"""
        if serial is None:
            return []
        
        try:
            ports = list(serial.tools.list_ports.comports())
            return [(p.device, p.description) for p in ports]
        except Exception:
            return []

    def refresh_setup_dropdowns(self):
        """Refresh both camera and COM port dropdowns"""
        # Refresh cameras
        self.setup_camera_combo.clear()
        cams = self.get_available_cameras()
        if not cams:
            self.setup_camera_combo.addItem("No cameras found", -1)
        else:
            for c in cams:
                self.setup_camera_combo.addItem(f"Camera {c}", c)

        # Refresh COM ports
        self.setup_comport_combo.clear()
        ports = self.get_available_comports()
        if not ports:
            self.setup_comport_combo.addItem("No COM ports found", None)
        else:
            for port, desc in ports:
                display_text = f"{port} - {desc}" if desc else port
                self.setup_comport_combo.addItem(display_text, port)

    def _find_arduino_cli_executable(self) -> Optional[str]:
        candidates = [
            "arduino-cli",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Arduino CLI", "arduino-cli.exe"),
            r"C:\Program Files\Arduino CLI\arduino-cli.exe",
            r"C:\Program Files (x86)\Arduino CLI\arduino-cli.exe",
        ]
        for candidate in candidates:
            try:
                if candidate == "arduino-cli":
                    resolved = shutil.which(candidate)
                    if resolved:
                        return resolved
                else:
                    if Path(candidate).exists():
                        return candidate
            except Exception:
                pass
        return None

    # Known USB VID/PID combos that map to specific FQBNs.
    _VID_PID_FQBN_MAP = {
        ("0x10C4", "0xEA60"): "esp32:esp32:esp32",   # Silicon Labs CP2102 -> ESP32
        ("0x1A86", "0x7523"): "esp32:esp32:esp32",   # CH340 -> common ESP32 clone
    }

    def _detect_fqbn_for_port(self, cli_path: str, com_port: str) -> str:
        default_fqbn = "esp32:esp32:esp32"
        try:
            proc = subprocess.run(
                [cli_path, "board", "list", "--format", "json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=12,
            )
            payload = proc.stdout or ""
            parsed = json.loads(payload) if payload.strip() else {}
            detected_ports = parsed.get("detected_ports", [])
            for entry in detected_ports:
                address = str(entry.get("port", {}).get("address", "")).strip()
                if address.upper() != str(com_port).strip().upper():
                    continue
                # First try matching_boards (auto-detected by arduino-cli)
                for board in entry.get("matching_boards", []) or []:
                    fqbn = str(board.get("fqbn", "")).strip()
                    if fqbn:
                        return fqbn
                # Fallback: match by USB VID/PID
                props = entry.get("port", {}).get("properties", {})
                vid = str(props.get("vid", "")).strip().upper()
                pid = str(props.get("pid", "")).strip().upper()
                # Normalise to 0xHHHH form
                vid_norm = vid if vid.startswith("0X") else f"0X{vid}"
                pid_norm = pid if pid.startswith("0X") else f"0X{pid}"
                for (map_vid, map_pid), fqbn in self._VID_PID_FQBN_MAP.items():
                    if vid_norm == map_vid.upper() and pid_norm == map_pid.upper():
                        return fqbn
        except Exception:
            pass
        return default_fqbn

    def _append_serial_monitor_text(self, text: str) -> None:
        if not text:
            return
        try:
            autoscroll = getattr(self, 'serial_monitor_autoscroll', True)
            vbar = self.serial_monitor_text.verticalScrollBar()
            prev_scroll = vbar.value()
            self.serial_monitor_text.append(str(text).rstrip("\r\n"))
            if autoscroll:
                self.serial_monitor_text.moveCursor(QTextCursor.MoveOperation.End)
            else:
                vbar.setValue(prev_scroll)
        except Exception:
            pass

    def _run_flash_async(self, compile_cmd: list[str], upload_cmd: list[str], com_port: str) -> None:
        """Start async Arduino flash process with compile and upload."""
        self._is_flashing_arduino = True
        self._flash_compile_cmd = compile_cmd
        self._flash_upload_cmd = upload_cmd
        self._flash_com_port = com_port
        self._flash_compile_ok = False
        self._flash_upload_ok = False

        # Start compile
        self._flashing_stage = "compile"
        self._append_serial_monitor_text(f"[FLASH] Running: {' '.join(compile_cmd)}")
        self.flash_thread = ArduinoFlasher(compile_cmd, timeout_s=180.0)
        self.flash_thread.output_line.connect(self._append_serial_monitor_text)
        self.flash_thread.finished.connect(self._on_flash_compile_finished)
        self.flash_thread.start()

    def _on_flash_compile_finished(self, rc: int, output: str) -> None:
        """Handle compile completion."""
        if rc == 0:
            self._flash_compile_ok = True
            self._append_serial_monitor_text("[FLASH] Compile successful, starting upload...")
            # Start upload
            self._flashing_stage = "upload"
            self._append_serial_monitor_text(f"[FLASH] Running: {' '.join(self._flash_upload_cmd)}")
            self.flash_thread = ArduinoFlasher(self._flash_upload_cmd, timeout_s=180.0)
            self.flash_thread.output_line.connect(self._append_serial_monitor_text)
            self.flash_thread.finished.connect(self._on_flash_upload_finished)
            self.flash_thread.start()
        else:
            self._is_flashing_arduino = False
            self._append_serial_monitor_text(f"[FLASH] Compile failed: {output}")
            self._show_flash_result(False, "Compile failed")

    def _on_flash_upload_finished(self, rc: int, output: str) -> None:
        """Handle upload completion."""
        self._is_flashing_arduino = False
        if rc == 0:
            self._flash_upload_ok = True
            self._append_serial_monitor_text("[FLASH] Upload successful")
            self._show_flash_result(True, f"Uploaded to {self._flash_com_port}")
        else:
            self._append_serial_monitor_text(f"[FLASH] Upload failed: {output}")
            self._show_flash_result(False, "Upload failed")

    def _show_flash_result(self, success: bool, msg: str) -> None:
        """Show flash result and continue setup if needed."""
        if success:
            if self._flash_pending_start_camera:
                self.log_message("Arduino flash finished successfully!")
                self._append_serial_monitor_text("[FLASH] Resetting BNO055 sensor...")
                self.log_message("Resetting BNO055 sensor...")
                # Start the BNO055 reset sequence before enabling camera/IMU
                self._reset_bno055_after_flash()
        else:
            self.log_message(f"Arduino flash failed: {msg}")
            self.setup_save_button.setEnabled(True)
            QMessageBox.critical(self, "Flash Failed", msg)

    def _reset_bno055_after_flash(self) -> None:
        """Open serial, send RESET_BNO command, and wait for BNO055_READY."""
        com_port = self._flash_com_port
        # Give the ESP32 time to boot after flash
        import time as _time
        _time.sleep(2.0)

        try:
            self._ensure_serial_reader_running()
        except Exception as e:
            self._append_serial_monitor_text(f"[ERROR] Cannot open serial after flash: {e}")
            self._finish_bno_reset(success=False)
            return

        if self._serial_reader is None:
            self._append_serial_monitor_text("[ERROR] Serial reader not available for BNO055 reset")
            self._finish_bno_reset(success=False)
            return

        # Start monitoring serial output for BNO055_READY
        self._serial_monitor_timer.start(50)
        self._bno_reset_attempts = 0
        self._bno_reset_max_attempts = 3
        self._send_bno_reset_command()

    def _send_bno_reset_command(self) -> None:
        """Send the RESET_BNO command and start a timer to check for response."""
        if self._serial_reader is not None:
            self._serial_reader.flush_input()
            self._serial_reader.send_line("RESET_BNO")
            self._append_serial_monitor_text("[BNO055] Sent RESET_BNO command")

        # Poll for response with a timeout timer
        self._bno_reset_start_time = time.time()
        self._bno_reset_timer = QTimer(self)
        self._bno_reset_timer.timeout.connect(self._check_bno_reset_response)
        self._bno_reset_timer.start(100)  # check every 100ms

    def _check_bno_reset_response(self) -> None:
        """Check serial buffer for BNO055_READY response."""
        elapsed = time.time() - self._bno_reset_start_time

        # Check lines from serial reader
        if self._serial_reader is not None:
            lines = self._serial_reader.pop_lines()
            for line in lines:
                self._append_serial_monitor_text(line)
                if "BNO055_READY" in line:
                    self._bno_reset_timer.stop()
                    self._append_serial_monitor_text("[BNO055] Sensor reset successful")
                    self.log_message("BNO055 sensor reset successful")
                    self._finish_bno_reset(success=True)
                    return
                if "BNO055_ERROR" in line:
                    self._bno_reset_timer.stop()
                    self._bno_reset_attempts += 1
                    if self._bno_reset_attempts < self._bno_reset_max_attempts:
                        self._append_serial_monitor_text(f"[BNO055] Reset failed, retrying ({self._bno_reset_attempts}/{self._bno_reset_max_attempts})...")
                        self._send_bno_reset_command()
                    else:
                        self._append_serial_monitor_text("[BNO055] Reset failed after all retries")
                        self._finish_bno_reset(success=False)
                    return

        # Timeout after 8 seconds per attempt
        if elapsed > 8.0:
            self._bno_reset_timer.stop()
            self._bno_reset_attempts += 1
            if self._bno_reset_attempts < self._bno_reset_max_attempts:
                self._append_serial_monitor_text(f"[BNO055] Reset timed out, retrying ({self._bno_reset_attempts}/{self._bno_reset_max_attempts})...")
                self._send_bno_reset_command()
            else:
                self._append_serial_monitor_text("[BNO055] Reset timed out after all retries -- proceeding anyway")
                self._finish_bno_reset(success=True)  # proceed anyway so user isn't stuck

    def _finish_bno_reset(self, success: bool) -> None:
        """Complete the post-flash setup after BNO055 reset."""
        try:
            if hasattr(self, '_bno_reset_timer') and self._bno_reset_timer.isActive():
                self._bno_reset_timer.stop()
        except Exception:
            pass

        if success:
            self.log_message("IMU data streaming started")
            # Continue with setup
            self._finish_setup_after_flash()
            self.log_message("Camera live preview started")
        else:
            self.log_message("BNO055 reset failed -- starting camera anyway")
            self._finish_setup_after_flash()

        self._flash_pending_start_camera = False

    def _flash_latest_arduino_code(self, com_port: str, continue_setup: bool = False) -> bool:
        """Start async Arduino flashing. Continues setup after flash if continue_setup=True."""
        sketch_dir = PROJECT_ROOT / "ArduinoCode" / "sensorOutput"
        sketch_file = sketch_dir / "sensorOutput.ino"

        if not sketch_dir.exists() or not sketch_file.exists():
            self._append_serial_monitor_text(f"[ERROR] Sketch not found at {sketch_file}")
            return False

        cli_path = self._find_arduino_cli_executable()
        if not cli_path:
            self._append_serial_monitor_text("[ERROR] arduino-cli not found. Install Arduino CLI and ensure it is on PATH.")
            return False

        fqbn = self._detect_fqbn_for_port(cli_path, com_port)
        self._append_serial_monitor_text(f"[FLASH] Detected FQBN: {fqbn}")

        compile_cmd = [cli_path, "compile", "--fqbn", fqbn, str(sketch_dir)]
        upload_cmd = [cli_path, "upload", "-p", str(com_port), "--fqbn", fqbn, str(sketch_dir)]
        
        self._flash_pending_start_camera = continue_setup
        self._run_flash_async(compile_cmd, upload_cmd, com_port)
        return True

    def save_setup_and_start_camera(self):
        """Save the selected setup and start flashing Arduino asynchronously"""
        # Get selected camera
        camera_idx = self.setup_camera_combo.currentData()
        if camera_idx is None or camera_idx == -1:
            QMessageBox.warning(self, "No Camera Selected", "Please select a valid camera.")
            return

        # Get selected COM port
        com_port = self.setup_comport_combo.currentData()
        if com_port is None:
            QMessageBox.warning(self, "No COM Port Selected", "Please select a valid COM port.")
            return

        # Store the setup
        self.selected_camera_idx = camera_idx
        self.selected_com_port = com_port

        # Log the selection
        self.log_message(f"Setup Saved: Camera {camera_idx} and COM PORT {com_port}")

        # Flash latest Arduino sketch on the selected COM port (async).
        self.setup_save_button.setEnabled(False)
        self._flash_pending_camera_idx = camera_idx

        # Stop serial monitor timer so it doesn't try to read during flash
        try:
            self._serial_monitor_timer.stop()
        except Exception:
            pass

        # Fully release the COM port before flashing
        try:
            if self._serial_reader is not None:
                self._serial_reader.stop()
                self._serial_reader = None
        except Exception:
            pass

        # Windows needs a moment for the OS to release the port handle
        import time as _time
        _time.sleep(0.5)

        self.log_message("Flashing Arduino with latest sketch...")
        self._append_serial_monitor_text("[FLASH] Flashing Arduino with latest sketch...")
        QApplication.processEvents()
        
        # Start async flash
        self._flash_latest_arduino_code(str(com_port), continue_setup=True)

    def _finish_setup_after_flash(self):
        """Complete setup after Arduino flash finishes successfully."""
        camera_idx = self._flash_pending_camera_idx
        
        # Enable Recording widget
        self.set_recording_enabled(True)

        # Start live camera preview
        self.start_live_preview(camera_idx)
        
        self.setup_save_button.setEnabled(True)

    def start_live_preview(self, camera_idx):
        """Start live camera preview and display in video viewer"""
        try:
            # Release previous capture if any
            if self.cap:
                self.cap.release()

            # Open the selected camera
            self.cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                QMessageBox.critical(self, "Camera Error", f"Cannot open camera {camera_idx}")
                return

            # Set camera properties for better quality
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            # Update viewer label
            self.viewer_label.setText("Live Camera Preview")

            # Start a timer to continuously update the preview
            if not hasattr(self, '_live_preview_timer'):
                self._live_preview_timer = QTimer()
                self._live_preview_timer.timeout.connect(self._update_live_preview)
            
            self._live_preview_timer.start(30)  # Update every 30ms (~33 FPS)
            self.log_message(f"Started live preview from camera {camera_idx}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start live preview: {str(e)}")
            self.log_message(f"Error starting live preview: {str(e)}")

    def _update_live_preview(self):
        """Update the live preview frame"""
        if not hasattr(self, 'cap') or self.cap is None or not self.cap.isOpened():
            if hasattr(self, '_live_preview_timer'):
                self._live_preview_timer.stop()
            return

        ret, frame = self.cap.read()
        if ret:
            self.update_preview(frame)
        else:
            if hasattr(self, '_live_preview_timer'):
                self._live_preview_timer.stop()

    # --- Recording methods (collapsible panel) ---
    def toggle_recording_panel(self):
        """Toggle the Recording section visibility"""
        self.recording_collapsed = not self.recording_collapsed
        self.recording_content.setVisible(not self.recording_collapsed)
        if self.recording_collapsed:
            self.recording_button.setText("Recording")
        else:
            self.recording_button.setText("Recording ▼")

    def toggle_serial_monitor_panel(self):
        self.serial_monitor_visible = not getattr(self, 'serial_monitor_visible', False)
        self.serial_monitor_panel.setVisible(self.serial_monitor_visible)
        self.serial_monitor_button.setText("Serial Monitor ▼" if self.serial_monitor_visible else "Serial Monitor")

        if self.serial_monitor_visible:
            if not getattr(self, '_is_flashing_arduino', False):
                self._ensure_serial_reader_running()
                self._serial_monitor_timer.start(50)
        else:
            try:
                self._serial_monitor_timer.stop()
            except Exception:
                pass
            if not getattr(self, 'is_recording', False):
                self._stop_serial_capture(stop_reader=True)

    def _ensure_serial_reader_running(self) -> None:
        com_port = getattr(self, 'selected_com_port', None)
        if not com_port:
            self.log_message("No COM port selected. Use Setup System first.")
            return
        if serial is None:
            self.log_message("Serial features disabled (pyserial not installed).")
            return

        # Recreate if port changed
        if self._serial_reader is not None and getattr(self._serial_reader, 'port', None) != str(com_port):
            try:
                self._serial_reader.stop()
            except Exception:
                pass
            self._serial_reader = None

        if self._serial_reader is None:
            try:
                self._serial_reader = SerialPortReader(port=str(com_port))
                self._serial_reader.start()
                self.log_message(f"Serial capture started on {com_port}")
            except Exception as e:
                self._serial_reader = None
                self.log_message(f"Serial capture failed to start on {com_port}: {e}")

    def _serial_monitor_tick(self) -> None:
        if not getattr(self, 'serial_monitor_visible', False):
            return
        reader = getattr(self, '_serial_reader', None)
        if reader is None:
            return
        try:
            lines = reader.pop_lines()
        except Exception:
            return
        if not lines:
            return
        try:
            autoscroll = getattr(self, 'serial_monitor_autoscroll', True)
            vbar = self.serial_monitor_text.verticalScrollBar()
            prev_scroll = vbar.value()

            self.serial_monitor_text.append("\n".join(lines))

            if autoscroll:
                self.serial_monitor_text.moveCursor(QTextCursor.MoveOperation.End)
            else:
                # Keep the visible region fixed (pause-like), while still appending output.
                vbar.setValue(prev_scroll)
        except Exception:
            pass

    def toggle_serial_monitor_autoscroll(self):
        self.serial_monitor_autoscroll = not getattr(self, 'serial_monitor_autoscroll', True)
        self.serial_monitor_autoscroll_btn.setText(
            "Auto-scroll: On" if self.serial_monitor_autoscroll else "Auto-scroll: Off"
        )

    def _start_serial_csv_logging(self, out_video_path: Path) -> None:
        """Enable CSV logging (only while recording)."""
        self._ensure_serial_reader_running()
        if self._serial_reader is None:
            return

        csv_path = out_video_path.parent / "IMUTimeStamp.csv"
        header = "timestamp_ms, Q.W, Q.X, Q.Y, Q.Z, W.X, W.Y, W.Z"

        # Attempt SYNC-based time alignment (Arduino micros -> host clock).
        try:
            self._sync_imu_timebase()
        except Exception:
            pass

        try:
            self._serial_reader.enable_logging(csv_path, header)
            self.serial_csv_path = str(csv_path)
            self.log_message(f"Serial CSV logging enabled: {csv_path.name}")
        except Exception as e:
            self.serial_csv_path = None
            self.log_message(f"Failed to enable serial CSV logging: {e}")

    def _sync_imu_timebase(self, timeout_s: float = 0.6) -> None:
        """Align Arduino IMU timestamps (micros) to recording timebase (ms).

        Uses a single SYNC exchange:
        - host sends "SYNC\n"
        - Arduino replies "SYNC,<micros>"
        Offset is estimated via midpoint timing to reduce serial latency bias.
        """
        reader = getattr(self, "_serial_reader", None)
        if reader is None:
            return

        # Ensure we have a recording start marker.
        record_start_us = getattr(self, "record_start_host_us", None)
        if record_start_us is None:
            record_start_us = float(time.perf_counter() * 1_000_000.0)
            self.record_start_host_us = record_start_us

        try:
            reader.flush_input()
        except Exception:
            pass

        t_send_us = float(time.perf_counter() * 1_000_000.0)
        try:
            reader.send_line("SYNC")
        except Exception:
            pass

        deadline = time.perf_counter() + float(timeout_s)
        arduino_us = None
        t_recv_us = None
        while time.perf_counter() < deadline:
            lines = []
            try:
                lines = reader.pop_lines()
            except Exception:
                lines = []
            for line in lines:
                s = (line or "").strip()
                if not s.startswith("SYNC,"):
                    continue
                try:
                    arduino_us = float(s.split(",", 1)[1].strip())
                    t_recv_us = float(time.perf_counter() * 1_000_000.0)
                except Exception:
                    arduino_us = None
                    t_recv_us = None
                break
            if arduino_us is not None:
                break
            time.sleep(0.005)

        if arduino_us is None or t_recv_us is None:
            # No sync; log raw timestamps.
            try:
                reader.set_time_sync(None, None)
            except Exception:
                pass
            self.log_message("IMU sync: SYNC not received; logging raw Arduino timestamps")
            return

        t_mid_us = (t_send_us + t_recv_us) / 2.0
        sync_offset_us = t_mid_us - arduino_us

        try:
            reader.set_time_sync(sync_offset_us, float(record_start_us))
        except Exception:
            pass
        self.log_message("IMU sync: established")

    def _stop_serial_capture(self, stop_reader: bool = False) -> None:
        if self._serial_reader is not None:
            try:
                self._serial_reader.disable_logging()
            except Exception:
                pass
            if stop_reader:
                try:
                    self._serial_reader.stop()
                except Exception:
                    pass
                self._serial_reader = None

        if getattr(self, 'serial_csv_path', None):
            self.log_message(f"Serial CSV saved: {self.serial_csv_path}")
        self.serial_csv_path = None

    def _start_frame_timestamp_logging(self, out_video_path: Path) -> None:
        csv_path = out_video_path.parent / "FrameTimestamp.csv"
        self._record_frame_index = 0
        self._record_last_frame_ts_ms = 0.0
        self._frame_ts_writer = None
        self._frame_ts_fp = None
        try:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._frame_ts_fp = open(csv_path, "w", encoding="utf-8", newline="")
            self._frame_ts_writer = csv.writer(self._frame_ts_fp)
            self._frame_ts_writer.writerow(["frame_index", "timestamp_ms", "timestamp_s"])
            self.frame_csv_path = str(csv_path)
            self.log_message(f"Frame timestamp logging enabled: {csv_path.name}")
        except Exception as e:
            self.frame_csv_path = None
            self._frame_ts_writer = None
            self._frame_ts_fp = None
            self.log_message(f"Failed to enable frame timestamp logging: {e}")

    def _log_recorded_frame_timestamp(self, timestamp_ms: float) -> None:
        writer = getattr(self, "_frame_ts_writer", None)
        if writer is None:
            return
        ts_ms = max(0.0, float(timestamp_ms))
        try:
            writer.writerow([
                int(self._record_frame_index),
                f"{ts_ms:.3f}",
                f"{(ts_ms / 1000.0):.6f}",
            ])
            if self._frame_ts_fp is not None:
                self._frame_ts_fp.flush()
            self._record_frame_index += 1
            self._record_last_frame_ts_ms = ts_ms
        except Exception:
            pass

    def _stop_frame_timestamp_logging(self) -> None:
        try:
            if self._frame_ts_fp is not None:
                self._frame_ts_fp.close()
        except Exception:
            pass
        if getattr(self, "frame_csv_path", None):
            self.log_message(f"Frame timestamp CSV saved: {self.frame_csv_path}")
        self._frame_ts_fp = None
        self._frame_ts_writer = None
        self.frame_csv_path = None

    def _update_recording_timeline(self) -> None:
        """Grow timeline end while recording based on frames written."""
        out_fps = float(getattr(self, "_record_out_fps", 30.0) or 30.0)
        frame_count = int(getattr(self, "_record_frame_index", 0))
        if frame_count <= 0:
            return

        self.total_frames = frame_count
        self.fps = out_fps
        self.current_frame = max(0, frame_count - 1)

        self.timeline_slider.setEnabled(True)
        self.timeline_slider.setMaximum(max(0, self.total_frames - 1))
        self.timeline_slider.setValue(self.current_frame)

        duration_seconds = int(self.total_frames / max(1.0, self.fps))
        # During recording, keep the left label fixed at the recording start.
        self.current_time_label.setText("00:00:00")
        self.total_time_label.setText(self.seconds_to_time(duration_seconds))

    def _align_imu_csv_duration(self, csv_path: Optional[str], target_end_ms: Optional[float]) -> tuple[int, Optional[float], bool]:
        """Scale IMU timestamp column so first=0 and last ~= target_end_ms.

        Returns: (row_count, aligned_last_ms, changed)
        """
        if not csv_path or target_end_ms is None:
            return 0, None, False

        path = Path(csv_path)
        if not path.exists() or target_end_ms < 0:
            return 0, None, False

        try:
            with open(path, "r", encoding="utf-8", newline="") as fp:
                rows = list(csv.reader(fp))
        except Exception:
            return 0, None, False

        if len(rows) <= 1:
            return 0, None, False

        header = rows[0]
        data_rows = rows[1:]

        parsed_ts = []
        for row in data_rows:
            if not row:
                continue
            try:
                parsed_ts.append(float(row[0]))
            except Exception:
                continue

        if not parsed_ts:
            return 0, None, False

        first_ts = float(parsed_ts[0])
        rel_ts = [max(0.0, t - first_ts) for t in parsed_ts]
        src_end = float(rel_ts[-1]) if rel_ts else 0.0

        if src_end <= 0.0:
            scale = 1.0
        else:
            scale = float(target_end_ms) / src_end

        changed = abs(scale - 1.0) > 0.001

        aligned_ts = [max(0.0, t * scale) for t in rel_ts]

        ts_idx = 0
        for row in data_rows:
            if not row:
                continue
            try:
                _ = float(row[0])
            except Exception:
                continue
            row[0] = str(int(round(aligned_ts[ts_idx])))
            ts_idx += 1

        try:
            with open(path, "w", encoding="utf-8", newline="") as fp:
                writer = csv.writer(fp)
                writer.writerow(header)
                writer.writerows(data_rows)
        except Exception:
            return len(parsed_ts), None, False

        aligned_last = float(aligned_ts[-1]) if aligned_ts else None
        return len(parsed_ts), aligned_last, changed

    def start_recording(self):
        """Start recording from the selected camera.

        Implementation guarantees that real-world duration matches recorded duration
        by writing frames at a fixed output FPS (independent of camera-reported FPS).
        """
        if getattr(self, 'is_recording', False):
            return

        if getattr(self, 'selected_camera_idx', None) is None:
            QMessageBox.warning(self, "No Camera", "Please setup a camera first using the Setup System.")
            return

        # Stop playback if a video is currently loaded/playing
        try:
            if self.timer.isActive():
                self.timer.stop()
            self.play_pause_button.setText("▶")
        except Exception:
            pass

        # Stop any live-preview timer (recording loop provides preview)
        try:
            if hasattr(self, '_live_preview_timer') and self._live_preview_timer.isActive():
                self._live_preview_timer.stop()
        except Exception:
            pass

        # Clean up any existing capture
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass

        cap = cv2.VideoCapture(self.selected_camera_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            QMessageBox.critical(self, "Camera Error", f"Cannot open camera {self.selected_camera_idx}")
            return

        # Read first frame immediately (starts the recording "now")
        ret, frame = cap.read()
        if not ret:
            cap.release()
            QMessageBox.warning(self, "Error", "Unable to read frame to start recording.")
            return

        h, w = frame.shape[:2]

        session_dir = self._get_session_dir()
        session_dir.mkdir(parents=True, exist_ok=True)

        out_path = session_dir / "Recording.mp4"

        # Fixed output FPS to guarantee duration correctness.
        # Using camera-reported FPS is unreliable on some webcams (can cause 3x speed errors).
        self._record_out_fps = 30.0
        self._record_frame_interval = 1.0 / self._record_out_fps

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, self._record_out_fps, (w, h))
        if not writer.isOpened():
            cap.release()
            QMessageBox.warning(self, "Warning", "VideoWriter could not be opened; recording disabled.")
            return

        # Commit state
        self.cap = cap
        self.recording_writer = writer
        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.recording_file_path = str(out_path)
        # Host monotonic start time (microseconds)
        self._record_start_perf = time.perf_counter()
        self.record_start_host_us = float(self._record_start_perf * 1_000_000.0)
        self._record_latest_frame = frame
        self._record_next_write_t = self._record_start_perf
        self._recording_started_logged = False

        # Start frame timestamp CSV logging only while recording
        self._start_frame_timestamp_logging(out_path)

        # Start serial CSV logging only while recording
        self._start_serial_csv_logging(out_path)

        # UI
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self.start_record_btn.setText("Recording...")

        # Prepare timeline to grow with recording duration.
        self.timeline_slider.setEnabled(True)
        self.timeline_slider.setMaximum(0)
        self.timeline_slider.setValue(0)
        self.current_time_label.setText("00:00:00")
        self.total_time_label.setText("00:00:00")

        # Write first frame immediately so the file duration tracks wall-clock.
        try:
            self.recording_writer.write(frame)
            self._log_recorded_frame_timestamp(0.0)
            self._update_recording_timeline()
            self.update_preview(frame)
            self.log_message("Recording Started.")
            self._recording_started_logged = True
            self._record_next_write_t = time.perf_counter() + self._record_frame_interval
        except Exception:
            pass

        # High-frequency timer; we throttle actual writes to _record_out_fps
        if not hasattr(self, '_record_timer'):
            self._record_timer = QTimer(self)
            self._record_timer.timeout.connect(self._record_tick)
        self._record_timer.start(10)

    def _record_tick(self):
        if not getattr(self, 'is_recording', False):
            return
        if not getattr(self, 'cap', None) or not self.cap.isOpened():
            self.stop_recording()
            return

        # Read the newest frame (live preview)
        ret, frame = self.cap.read()
        if ret:
            self._record_latest_frame = frame
            try:
                self.update_preview(frame)
            except Exception:
                pass

        # Write frames at fixed output FPS to preserve real duration
        now = time.perf_counter()
        loops = 0
        while now >= getattr(self, '_record_next_write_t', now) and loops < 5:
            lf = getattr(self, '_record_latest_frame', None)
            if lf is None:
                break
            try:
                if getattr(self, 'recording_writer', None):
                    self.recording_writer.write(lf)
                    base_t = getattr(self, '_record_start_perf', None)
                    if base_t is not None:
                        elapsed_ms = (time.perf_counter() - float(base_t)) * 1000.0
                    else:
                        elapsed_ms = 0.0
                    self._log_recorded_frame_timestamp(elapsed_ms)
                if not getattr(self, '_recording_started_logged', False):
                    self.log_message("Recording Started.")
                    self._recording_started_logged = True
            except Exception:
                break

            self._record_next_write_t += getattr(self, '_record_frame_interval', 1.0 / 30.0)
            loops += 1

        # Keep timeline end time growing until recording finishes.
        if loops > 0:
            self._update_recording_timeline()

    def stop_recording(self):
        """Stop recording"""
        if not getattr(self, 'is_recording', False):
            return

        serial_csv_path = getattr(self, 'serial_csv_path', None)
        imu_count = 0
        imu_last_ms = None
        try:
            if self._serial_reader is not None:
                imu_count, imu_last_ms = self._serial_reader.get_logging_stats()
        except Exception:
            imu_count, imu_last_ms = 0, None

        frame_count = int(getattr(self, '_record_frame_index', 0))
        frame_last_ms = float(getattr(self, '_record_last_frame_ts_ms', 0.0)) if frame_count > 0 else None

        # Stop serial logging first (requested: only between Start/End Recording)
        try:
            self._stop_serial_capture(stop_reader=not getattr(self, 'serial_monitor_visible', False))
        except Exception:
            pass

        # Post-align IMU CSV duration to frame duration (first timestamp stays 0 ms).
        try:
            aligned_count, aligned_last_ms, changed = self._align_imu_csv_duration(serial_csv_path, frame_last_ms)
            if aligned_count > 0 and aligned_last_ms is not None:
                imu_count = aligned_count
                imu_last_ms = aligned_last_ms
                if changed:
                    self.log_message(
                        f"IMU duration aligned to frame duration: imu_end={imu_last_ms:.1f} ms, "
                        f"frame_end={float(frame_last_ms):.1f} ms"
                    )
        except Exception:
            pass

        # Stop frame timestamp logging for this recording.
        try:
            self._stop_frame_timestamp_logging()
        except Exception:
            pass

        # Stop record timer
        if hasattr(self, '_record_timer') and self._record_timer.isActive():
            try:
                self._record_timer.stop()
            except Exception:
                pass

        # Release writer
        if getattr(self, 'recording_writer', None):
            try:
                self.recording_writer.release()
            except Exception:
                pass
            self.recording_writer = None

        # Release camera
        if getattr(self, 'cap', None):
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        # Update state
        self.is_recording = False
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self.start_record_btn.setText("Start Recording")

        # Move recording files to Raw-Data subfolder
        try:
            if hasattr(self, 'recording_file_path') and self.recording_file_path:
                rec_path = Path(self.recording_file_path)
                session = rec_path.parent
                raw_data_dir = session / "Raw-Data"
                raw_data_dir.mkdir(parents=True, exist_ok=True)
                
                # Move Recording.mp4
                if rec_path.exists():
                    new_rec_path = raw_data_dir / rec_path.name
                    shutil.move(str(rec_path), str(new_rec_path))
                    self.recording_file_path = str(new_rec_path)
                
                # Move FrameTimestamp.csv
                frame_csv = session / "FrameTimestamp.csv"
                if frame_csv.exists():
                    shutil.move(str(frame_csv), str(raw_data_dir / "FrameTimestamp.csv"))
                
                # Move IMUTimeStamp.csv
                imu_csv = session / "IMUTimeStamp.csv"
                if imu_csv.exists():
                    shutil.move(str(imu_csv), str(raw_data_dir / "IMUTimeStamp.csv"))
                
                self.log_message(f"Recording files moved to {raw_data_dir.name}/")
        except Exception as e:
            self.log_message(f"Warning: Could not move recording files: {e}")

        # Log
        self.log_message("Recording Ended.")

        if frame_last_ms is not None and imu_last_ms is not None:
            delta_ms = abs(float(frame_last_ms) - float(imu_last_ms))
            self.log_message(
                f"Sync summary: frames={frame_count}, frame_end={frame_last_ms:.1f} ms; "
                f"imu_rows={imu_count}, imu_end={float(imu_last_ms):.1f} ms; delta={delta_ms:.1f} ms"
            )
        elif frame_last_ms is not None:
            self.log_message(
                f"Sync summary: frames={frame_count}, frame_end={frame_last_ms:.1f} ms; "
                f"IMU rows={imu_count}"
            )

        if hasattr(self, 'recording_file_path'):
            # Automatically load the new recording for segment creation
            self.load_video_from_path(self.recording_file_path)
        else:
            self.log_message("Recording stopped")

    def next_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.current_frame += 1
                self.timeline_slider.setValue(self.current_frame)
                self.update_preview(frame)
                self.current_time_label.setText(self.seconds_to_time(self.current_frame // self.fps))
            else:
                self.timer.stop()

    def toggle_play_pause(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play_pause_button.setText("▶")  # Play symbol
        else:
            self.timer.start(int(1000 / self.fps))
            self.play_pause_button.setText("⏸")  # Pause symbol

    def skip_frames(self, count):
        new_frame = max(0, min(self.total_frames - 1, self.current_frame + count))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = new_frame
            self.timeline_slider.setValue(self.current_frame)
            self.update_preview(frame)
            self.current_time_label.setText(self.seconds_to_time(self.current_frame // self.fps))

    def scrub_video(self):
        frame = self.timeline_slider.value()
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ret, frame_data = self.cap.read()
        if ret:
            self.current_frame = frame
            self.update_preview(frame_data)
            self.current_time_label.setText(self.seconds_to_time(self.current_frame // self.fps))

    def seconds_to_time(self, seconds):
        return QTime(0, 0).addSecs(int(seconds)).toString("HH:mm:ss")

    def set_recording_enabled(self, enabled: bool):
        self.recording_button.setEnabled(enabled)
        self.start_record_btn.setEnabled(enabled)
        self.stop_record_btn.setEnabled(False if enabled else False)
        self.recording_content.setEnabled(enabled)

    def set_segments_enabled(self, enabled: bool):
        self.segments_button.setEnabled(enabled)
        self.segment_list.setEnabled(enabled)
        # Optionally collapse the widget if disabled
        if not enabled:
            self.segment_list.setVisible(False)
            self.segments_collapsed = True
            self.segments_button.setText("Segments")
