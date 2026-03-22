"""
ImagingPage -- embeddable QWidget for the surgical imaging interface.

Adapted from VideoWindow (video_main_window.py) to work as a page inside
the main application shell rather than a standalone QMainWindow.

Owns backend services and child widgets, wires signals between them.

Uses:
  - backend/serial_service.py (SerialPortReader)
  - backend/arduino_flasher.py (ArduinoFlasher)
  - backend/extraction_service.py (SegmentExtractor)
  - backend/camera_service.py (probe_cameras)
  - frontend/video/side_panel.py (SidePanel)
  - frontend/video/video_viewer.py (VideoViewer)
  - frontend/video/segment_controls.py (SegmentControls)
  - frontend/video/serial_monitor_panel.py (SerialMonitorPanel)
"""
from __future__ import annotations

import os
import csv
import json
import time
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout,
    QFileDialog, QInputDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QTime, QEvent, QThread, pyqtSignal

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

from shared.constants import (
    DATA_DIR, PROJECT_ROOT, SERIAL_BAUD_RATE,
    RECORD_TICK_MS, LIVE_PREVIEW_MS, DEFAULT_RECORDING_FPS,
    BNO_RESET_CHECK_MS, BNO_RESET_TIMEOUT_S, IMU_SYNC_POLL_MS,
)
from shared.form_helpers import set_button_enabled_style

from backend.serial_service import SerialPortReader
from backend.arduino_flasher import ArduinoFlasher
from backend.extraction_service import SegmentExtractor, WholeVideoExtractor, SegmentCSVGenerator
from backend.camera_service import probe_cameras
from backend.session_manager import sanitize_filename_component

from frontend.video.side_panel import SidePanel
from frontend.video.video_viewer import VideoViewer
from frontend.video.segment_controls import SegmentControls
from frontend.video.serial_monitor_panel import SerialMonitorPanel


class FileCopyWorker(QThread):
    """Copy files in a background thread to avoid UI freezes."""
    finished = pyqtSignal(bool, str)  # (success, error_message)

    def __init__(self, copy_pairs: list, parent=None):
        """copy_pairs: list of (source_path, dest_path) tuples."""
        super().__init__(parent)
        self._copy_pairs = copy_pairs

    def run(self):
        try:
            for src, dst in self._copy_pairs:
                shutil.copy2(str(src), str(dst))
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class CameraProbeWorker(QThread):
    """Probe available cameras in a background thread."""
    finished = pyqtSignal(list)  # list of camera indices

    def run(self):
        try:
            cams = probe_cameras()
        except Exception:
            cams = []
        self.finished.emit(cams)


class FQBNDetectWorker(QThread):
    """Detect board FQBN and prepare flash commands in background."""
    finished = pyqtSignal(str, list, list)  # fqbn, compile_cmd, upload_cmd

    def __init__(self, cli_path, com_port, sketch_dir, parent=None):
        super().__init__(parent)
        self._cli_path = cli_path
        self._com_port = com_port
        self._sketch_dir = sketch_dir

    def run(self):
        fqbn = self._detect_fqbn()
        compile_cmd = [self._cli_path, "compile", "--fqbn", fqbn, str(self._sketch_dir)]
        upload_cmd = [self._cli_path, "upload", "-p", str(self._com_port), "--fqbn", fqbn, str(self._sketch_dir)]
        self.finished.emit(fqbn, compile_cmd, upload_cmd)

    def _detect_fqbn(self) -> str:
        default_fqbn = "esp32:esp32:esp32"
        try:
            proc = subprocess.run(
                [self._cli_path, "board", "list", "--format", "json"],
                check=False, capture_output=True, text=True, timeout=12,
            )
            payload = proc.stdout or ""
            parsed = json.loads(payload) if payload.strip() else {}
            for entry in parsed.get("detected_ports", []):
                address = str(entry.get("port", {}).get("address", "")).strip()
                if address.upper() != str(self._com_port).strip().upper():
                    continue
                for board in entry.get("matching_boards", []) or []:
                    fqbn = str(board.get("fqbn", "")).strip()
                    if fqbn:
                        return fqbn
                props = entry.get("port", {}).get("properties", {})
                vid = str(props.get("vid", "")).strip().upper()
                pid = str(props.get("pid", "")).strip().upper()
                vid_n = vid if vid.startswith("0X") else f"0X{vid}"
                pid_n = pid if pid.startswith("0X") else f"0X{pid}"
                for (mv, mp), mapped_fqbn in ImagingPage._VID_PID_FQBN_MAP.items():
                    if vid_n == mv.upper() and pid_n == mp.upper():
                        return mapped_fqbn
        except Exception:
            pass
        return default_fqbn


class ImagingPage(QWidget):
    navigate_to_reconstruction = pyqtSignal(dict)
    recording_saved = pyqtSignal(str, str)  # video_path, imu_path

    def __init__(self, parent=None):
        super().__init__(parent)

        # Patient context (set later via set_patient_context)
        self.patient_id: Optional[str] = None
        self.patient_db = None

        # --- Shared state ---
        self.session_name: str = ""
        self.session_base_name: str = ""
        self.session_dir: Optional[Path] = None

        self.video_path = None
        self.cap = None
        self.fps = 30
        self.total_frames = 0
        self.current_frame = 0
        self.worker_threads = []
        self.segment_progress = {}
        self.completed_segments = 0
        self.current_video_id = None
        self.selected_frames = {}

        self.selected_camera_idx = None
        self.selected_com_port = None

        # Recording
        self.is_recording = False
        self.recording_writer = None
        self.recording_file_path = None
        self.frame_csv_path: Optional[str] = None
        self._frame_ts_fp = None
        self._frame_ts_writer = None
        self._record_frame_index = 0
        self._record_last_frame_ts_ms = 0.0
        self._record_start_perf = None

        # Serial
        self._serial_reader: Optional[SerialPortReader] = None
        self.serial_csv_path: Optional[str] = None
        self._is_flashing_arduino = False

        # Flash async state
        self._flash_pending_start_camera = False
        self._flash_com_port_for_reset = None
        self._flash_compile_cmd = []
        self._flash_upload_cmd = []
        self._flash_com_port = None
        self._flash_compile_ok = False
        self._flash_upload_ok = False
        self._flashing_stage = None
        self.flash_thread = None

        # --- Build layout ---
        main_layout = QHBoxLayout(self)

        # Side panel
        self._side = SidePanel(has_patient=True)
        self._side.load_button.clicked.connect(self.load_video_file)
        self._side.flash_refresh_button.clicked.connect(self._refresh_flash_comports)
        self._side.flash_start_button.clicked.connect(self.flash_hardware)
        self._side.refresh_button.clicked.connect(self.refresh_setup_dropdowns)
        self._side.save_setup_button.clicked.connect(self.save_setup_and_start_camera)
        self._side.serial_monitor_button.clicked.connect(self._toggle_serial_monitor)
        self._side.recording_panel.start_btn.clicked.connect(self.start_recording)
        self._side.recording_panel.stop_btn.clicked.connect(self.stop_recording)
        self._side.extract_button.clicked.connect(self._toggle_extract)
        self._side.cancel_button.clicked.connect(self.cancel_extraction)
        self._side.view_frames_button.clicked.connect(self.open_frame_browser)
        self._side.reconstruct_button.clicked.connect(self.start_reconstruction)

        # Segment controls
        self._segments = SegmentControls()
        self._segments.segment_added.connect(self._on_segment_changed)
        self._segments.segment_deleted.connect(self._on_segment_changed)
        self._segments.segment_renamed.connect(self._on_segment_changed)
        self._side.segments_button.clicked.connect(self._toggle_segments)
        # Insert segment list into side panel layout (after segments_button)
        idx = self._side.layout().indexOf(self._side.segments_button) + 1
        self._side.layout().insertWidget(idx, self._segments)

        main_layout.addWidget(self._side, 0)
        self._side.setFixedWidth(240)

        # Video viewer
        self._viewer = VideoViewer()
        self._viewer.play_pause_button.clicked.connect(self.toggle_play_pause)
        self._viewer.back_button.clicked.connect(lambda: self.skip_frames(-self.fps))
        self._viewer.forward_button.clicked.connect(lambda: self.skip_frames(self.fps))
        self._viewer.timeline_slider.sliderReleased.connect(self.scrub_video)
        self._viewer.add_segment_requested.connect(self._on_add_segment)
        main_layout.addWidget(self._viewer, 1)

        # Serial monitor (right side, hidden by default)
        self._serial_panel = SerialMonitorPanel()
        self._serial_panel.setVisible(False)
        main_layout.addWidget(self._serial_panel, 1)

        # Serial monitor poll timer
        self._serial_monitor_timer = QTimer(self)
        self._serial_monitor_timer.timeout.connect(self._serial_monitor_tick)

        # Playback timer
        self._play_timer = QTimer()
        self._play_timer.timeout.connect(self.next_frame)

        # Disable recording and segments on startup
        self._side.set_recording_enabled(False)
        self._segments.set_enabled(False)

    # ------------------------------------------------------------------
    # Patient context
    # ------------------------------------------------------------------
    def set_patient_context(self, patient_id, patient_db):
        old_id = self.patient_id
        self.patient_id = patient_id
        self.patient_db = patient_db

        # When patient changes, reset the imaging state so no stale
        # video / session from a different patient is shown.
        if patient_id != old_id:
            self._reset_imaging_state()

    def _reset_imaging_state(self):
        """Clear video, session, and viewer state for a fresh patient context."""
        # Stop playback
        if self._play_timer.isActive():
            self._play_timer.stop()
        if hasattr(self, '_live_preview_timer') and self._live_preview_timer.isActive():
            self._live_preview_timer.stop()

        # Release video capture
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        # Reset video/session state
        self.video_path = None
        self.total_frames = 0
        self.current_frame = 0
        self.current_video_id = None
        self.selected_frames = {}
        self.session_name = ""
        self.session_base_name = ""
        self.session_dir = None
        self.recording_file_path = None

        # Reset viewer
        self._viewer.viewer_label.clear()
        self._viewer.viewer_label.setText("No video loaded")
        self._viewer.timeline_slider.setMaximum(0)
        self._viewer.timeline_slider.setValue(0)
        self._viewer.timeline_slider.setEnabled(False)
        self._viewer.current_time_label.setText("00:00:00")
        self._viewer.total_time_label.setText("00:00:00")
        try:
            self._viewer.play_pause_button.setText("\u25b6")
        except Exception:
            pass

        # Reset segments
        self._segments.clear()
        self._segments.set_enabled(False)
        self._side.segments_button.setEnabled(False)
        set_button_enabled_style(self._side.segments_button, False)

        # Reset side panel buttons
        set_button_enabled_style(self._side.extract_button, False)
        set_button_enabled_style(self._side.view_frames_button, False)
        set_button_enabled_style(self._side.reconstruct_button, False)
        self._side.serial_monitor_button.setEnabled(False)
        set_button_enabled_style(self._side.serial_monitor_button, False)

    # ------------------------------------------------------------------
    # Patient media loading
    # ------------------------------------------------------------------
    def load_patient_media(self, video_path=None, imu_path=None, session_name=None):
        """Auto-load patient's video and IMU data without file dialogs."""
        if not video_path:
            return
        video_p = Path(video_path)
        if not video_p.exists():
            self.log_message(f"Video not found: {video_path}")
            return

        name = session_name.strip() if session_name and session_name.strip() else video_p.stem
        session_dir = self._create_load_session_dir(name)
        raw_dir = session_dir / "Raw Data"
        raw_dir.mkdir(parents=True, exist_ok=True)

        dest_video = raw_dir / "Recording.mp4"
        copy_pairs = [(str(video_p), str(dest_video))]

        if imu_path:
            imu_p = Path(imu_path)
            if imu_p.exists():
                copy_pairs.append((str(imu_p), str(raw_dir / "IMUTimeStamp.csv")))

        self.log_message("Copying patient media to session directory...")

        # Store state for the callback
        self._pending_patient_load = {
            "session_dir": session_dir,
            "dest_video": dest_video,
            "video_name": video_p.name,
        }

        self._patient_copy_worker = FileCopyWorker(copy_pairs, parent=self)
        self._patient_copy_worker.finished.connect(self._on_patient_copy_finished)
        self._patient_copy_worker.start()

    def _on_patient_copy_finished(self, success: bool, error_msg: str):
        """Handle completion of background file copy for load_patient_media."""
        if not success:
            self.log_message(f"Failed to copy patient media: {error_msg}")
            return

        pending = self._pending_patient_load
        session_dir = pending["session_dir"]
        dest_video = pending["dest_video"]

        self.log_message(f"Copied video to {dest_video.name}")
        self.session_dir = session_dir
        self.recording_file_path = str(dest_video)
        self.load_video_from_path(str(dest_video))
        self.log_message(f"Patient media loaded: {pending['video_name']}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self):
        try:
            self._stop_serial_capture(stop_reader=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Terminal / logging
    # ------------------------------------------------------------------
    def terminal_log(self, message: str):
        cursor = self._side.terminal_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(message + "\n")
        self._side.terminal_display.setTextCursor(cursor)
        self._side.terminal_display.ensureCursorVisible()

    def log_message(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._side.terminal_display.append(f"[{timestamp}] {message}")
        cursor = self._side.terminal_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._side.terminal_display.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Patient integration
    # ------------------------------------------------------------------
    def _link_extracted_frames_to_patient(self):
        if not self.patient_id or not self.patient_db:
            return
        try:
            patient = self.patient_db.load_patient(self.patient_id)
            if not patient:
                return
            if not self.session_dir:
                return
            output_dir = Path(self.session_dir) / "Output Data"
            if not output_dir.is_dir():
                return
            for entry in output_dir.iterdir():
                if entry.is_dir():
                    dir_path = str(entry)
                    if dir_path not in patient.associated_images:
                        patient.associated_images.append(dir_path)
                        self.terminal_log(f"Linked extracted frames to patient: {entry.name}")
            self.patient_db.save_patient(patient)
            self.terminal_log("Extracted frames saved to patient profile")
        except Exception as e:
            self.terminal_log(f"Error linking extracted frames to patient: {e}")

    def _patient_folder_name(self) -> Optional[str]:
        """Build 'PATIENT-FirstLast' folder name from patient DB record."""
        if not self.patient_id or not self.patient_db:
            return None
        try:
            p = self.patient_db.load_patient(self.patient_id)
            if not p:
                return None
            first = (p.first_name or "").strip()
            last = (p.last_name or "").strip()
            name_part = sanitize_filename_component(f"{first}{last}") or self.patient_id[:12]
            return f"PATIENT-{name_part}"
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Session directory
    # ------------------------------------------------------------------
    def _get_session_dir(self) -> Path:
        try:
            name = self._side.recording_panel.session_name_input.text().strip()
        except Exception:
            name = ""
        if not name:
            name = "Session"
        current_base = getattr(self, "session_base_name", "")
        if self.session_dir is not None and current_base and name == current_base:
            return Path(self.session_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = sanitize_filename_component(name) or "Session"
        safe = f"{base}-{timestamp}"
        self.session_base_name = name
        self.session_name = safe
        # Nest under PATIENT-FirstLast directory when patient context exists
        patient_folder = self._patient_folder_name()
        if patient_folder:
            patient_dir = DATA_DIR / patient_folder
            patient_dir.mkdir(parents=True, exist_ok=True)
            self.session_dir = patient_dir / safe
        else:
            self.session_dir = DATA_DIR / safe
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir

    def _segment_frames_output_dir(self, seg: dict) -> str:
        if self.session_dir is not None:
            session_dir = Path(self.session_dir)
        else:
            session_dir = self._get_session_dir()
        output_dir = session_dir / "Output Data"
        name = str(seg.get("name", "segment")).strip() or "segment"
        safe = sanitize_filename_component(name.replace(" ", "_")) or "segment"
        d = output_dir / safe
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def _create_load_session_dir(self, session_name: str) -> Path:
        """Create a session directory for loaded (non-recorded) data."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = sanitize_filename_component(session_name) or "Session"
        safe = f"{base}-{timestamp}"
        self.session_base_name = session_name
        self.session_name = safe

        patient_folder = self._patient_folder_name()
        if patient_folder:
            patient_dir = DATA_DIR / patient_folder
            patient_dir.mkdir(parents=True, exist_ok=True)
            session_dir = patient_dir / safe
        else:
            session_dir = DATA_DIR / safe
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def _validate_imu_csv(self, csv_path: Path) -> bool:
        """Validate that the selected CSV has the expected IMU format (11+ columns)."""
        try:
            with open(csv_path, "r", encoding="utf-8") as fp:
                reader = csv.reader(fp)
                header = next(reader, None)
                if header is None:
                    QMessageBox.warning(self, "Invalid IMU CSV", "The selected CSV file is empty.")
                    return False

                valid_rows = 0
                for row in reader:
                    if len(row) < 11:
                        continue
                    try:
                        float(row[0].strip())
                        [float(row[j].strip()) for j in range(1, 11)]
                        valid_rows += 1
                    except ValueError:
                        continue
                    if valid_rows >= 3:
                        break

                if valid_rows == 0:
                    QMessageBox.warning(
                        self, "Invalid IMU CSV",
                        "The selected CSV does not contain valid IMU data.\n\n"
                        "Expected format: 11 columns per row\n"
                        "  timestamp_ms, Q.W, Q.X, Q.Y, Q.Z, W.X, W.Y, W.Z, A.X, A.Y, A.Z"
                    )
                    return False
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Cannot read CSV file:\n{e}")
            return False
        return True

    # ------------------------------------------------------------------
    # Data loading and playback
    # ------------------------------------------------------------------
    def load_video_file(self):
        """Multi-step Load Data flow: pick mp4, pick IMU CSV, create session, copy files."""

        # Step 1: Select video file
        video_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        if not video_path:
            return
        video_path = Path(video_path)
        video_dir = str(video_path.parent)

        # Step 2: Select IMU CSV file
        imu_path, _ = QFileDialog.getOpenFileName(
            self, "Select IMU CSV File", video_dir,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not imu_path:
            return
        imu_path = Path(imu_path)

        # Step 3: Validate IMU CSV format
        if not self._validate_imu_csv(imu_path):
            return

        # Step 4: Auto-detect FrameTimestamp.csv in same folder as IMU CSV
        imu_dir = imu_path.parent
        frame_ts_path = imu_dir / "FrameTimestamp.csv"
        has_frame_ts = frame_ts_path.exists()
        if has_frame_ts:
            self.log_message(f"Auto-detected FrameTimestamp.csv in {imu_dir.name}/")
        else:
            self.log_message("FrameTimestamp.csv not found; extraction will use video timestamps")

        # Step 5: Prompt for session name
        default_name = video_path.stem
        session_name, ok = QInputDialog.getText(
            self, "Session Name",
            "Enter a name for this session:",
            text=default_name
        )
        if not ok or not session_name.strip():
            return

        # Step 6: Create session directory
        session_dir = self._create_load_session_dir(session_name.strip())
        raw_dir = session_dir / "Raw Data"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Step 7: Copy files into Raw Data/ (background thread)
        dest_video = raw_dir / "Recording.mp4"
        dest_imu = raw_dir / "IMUTimeStamp.csv"
        copy_pairs = [
            (str(video_path), str(dest_video)),
            (str(imu_path), str(dest_imu)),
        ]
        if has_frame_ts:
            dest_frame_ts = raw_dir / "FrameTimestamp.csv"
            copy_pairs.append((str(frame_ts_path), str(dest_frame_ts)))

        self.log_message("Copying files to session directory...")
        self._side.load_button.setEnabled(False)

        # Store state for the callback
        self._pending_load = {
            "session_dir": session_dir,
            "dest_video": dest_video,
            "raw_dir": raw_dir,
            "has_frame_ts": has_frame_ts,
        }

        self._file_copy_worker = FileCopyWorker(copy_pairs, parent=self)
        self._file_copy_worker.finished.connect(self._on_load_copy_finished)
        self._file_copy_worker.start()

    def _on_load_copy_finished(self, success: bool, error_msg: str):
        """Handle completion of background file copy for load_video_file."""
        self._side.load_button.setEnabled(True)
        if not success:
            QMessageBox.critical(
                self, "Copy Error",
                f"Failed to copy files into session directory:\n{error_msg}"
            )
            return

        pending = self._pending_load
        session_dir = pending["session_dir"]
        dest_video = pending["dest_video"]
        raw_dir = pending["raw_dir"]

        self.log_message(f"Copied video to {dest_video.name}")
        self.log_message(f"Copied IMU data to IMUTimeStamp.csv")
        if pending["has_frame_ts"]:
            self.log_message(f"Copied frame timestamps to FrameTimestamp.csv")

        # Step 8: Set session state
        self.session_dir = session_dir
        self.recording_file_path = str(dest_video)

        # Step 9: Load video for playback
        self.load_video_from_path(str(dest_video))
        self.log_message(f"Session loaded: {session_dir.name}")

        # Push loaded media back to patient profile
        imu_dest = str(raw_dir / "IMUTimeStamp.csv")
        self.recording_saved.emit(str(dest_video), imu_dest if Path(imu_dest).exists() else "")

    def load_video_from_path(self, file_name):
        video_to_load = file_name

        self.video_path = video_to_load
        self.current_video_id = os.path.abspath(video_to_load)
        self.cap = cv2.VideoCapture(video_to_load)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        if not fps or fps < 1:
            fps = 30.0
        self.fps = fps
        self.current_frame = 0
        self.selected_frames = {}

        # Load recording FPS from metadata if available
        self.recording_fps = self.fps
        if self.session_dir:
            metadata_path = Path(self.session_dir) / "Raw Data" / "recording_metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    self.recording_fps = float(meta.get("recording_fps", self.fps))
                except Exception:
                    pass

        self._viewer.timeline_slider.setMaximum(max(0, self.total_frames - 1))
        self._viewer.timeline_slider.setEnabled(True)
        self._segments.clear()
        self._viewer.refresh_timeline_highlight([], self.total_frames, self.fps)

        duration_seconds = int(self.total_frames / max(1.0, self.fps))
        self._viewer.total_time_label.setText(self._viewer.seconds_to_time(duration_seconds))
        self._viewer.set_video_duration(duration_seconds)

        set_button_enabled_style(self._side.extract_button, True)
        set_button_enabled_style(self._side.view_frames_button, False)
        set_button_enabled_style(self._side.reconstruct_button, False)
        self.log_message("Video loaded")

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = self.cap.read()
        if ret:
            self._viewer.update_preview(frame)
            self._viewer.current_time_label.setText("00:00:00")

        self._segments.set_enabled(True)
        self._side.segments_button.setEnabled(True)
        set_button_enabled_style(self._side.segments_button, True)
        if self._play_timer.isActive():
            self._play_timer.stop()
        try:
            self._viewer.play_pause_button.setText("\u25b6")
        except Exception:
            pass

    def pause_video(self):
        if self._play_timer.isActive():
            self._play_timer.stop()

    def next_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.current_frame += 1
                self._viewer.timeline_slider.setValue(self.current_frame)
                self._viewer.update_preview(frame)
                self._viewer.current_time_label.setText(
                    self._viewer.seconds_to_time(self.current_frame // self.fps)
                )
            else:
                self._play_timer.stop()

    def toggle_play_pause(self):
        if self._play_timer.isActive():
            self._play_timer.stop()
            self._viewer.play_pause_button.setText("\u25b6")
        else:
            self._play_timer.start(int(1000 / self.fps))
            self._viewer.play_pause_button.setText("\u23f8")

    def skip_frames(self, count):
        new_frame = max(0, min(self.total_frames - 1, self.current_frame + count))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = new_frame
            self._viewer.timeline_slider.setValue(self.current_frame)
            self._viewer.update_preview(frame)
            self._viewer.current_time_label.setText(
                self._viewer.seconds_to_time(self.current_frame // self.fps)
            )

    def scrub_video(self):
        frame = self._viewer.timeline_slider.value()
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ret, frame_data = self.cap.read()
        if ret:
            self.current_frame = frame
            self._viewer.update_preview(frame_data)
            self._viewer.current_time_label.setText(
                self._viewer.seconds_to_time(self.current_frame // self.fps)
            )

    # ------------------------------------------------------------------
    # Segments
    # ------------------------------------------------------------------
    def _on_add_segment(self, name: str, start: QTime, end: QTime):
        if self._segments.add_segment(name, start, end):
            self._viewer.clear_segment_name()
            set_button_enabled_style(self._side.extract_button, True)
            self.log_message(f"{name or 'Segment'} added")
            self._viewer.refresh_timeline_highlight(
                self._segments.segments, self.total_frames, self.fps
            )

    def _on_segment_changed(self):
        self._viewer.refresh_timeline_highlight(
            self._segments.segments, self.total_frames, self.fps
        )

    def _toggle_segments(self):
        visible = self._segments.toggle_visible()
        self._side.segments_button.setText("Segments \u25bc" if visible else "Segments")

    # ------------------------------------------------------------------
    # Flash Hardware (standalone)
    # ------------------------------------------------------------------
    def _refresh_flash_comports(self):
        """Populate the Flash Hardware COM port dropdown."""
        self._side.flash_comport_combo.clear()
        ports = self._get_comports()
        if not ports:
            self._side.flash_comport_combo.addItem("No COM ports found", None)
        else:
            for port, desc in ports:
                self._side.flash_comport_combo.addItem(f"{port} - {desc}" if desc else port, port)

    def flash_hardware(self):
        """Flash Arduino and reset BNO055 -- standalone, does not start camera."""
        com_port = self._side.flash_comport_combo.currentData()
        if com_port is None:
            QMessageBox.warning(self, "No COM Port", "Please select a COM port for flashing.")
            return

        self._side.flash_start_button.setEnabled(False)

        # Stop any existing serial reader so the port is free
        try:
            self._serial_monitor_timer.stop()
        except Exception:
            pass
        try:
            if self._serial_reader is not None:
                self._serial_reader.stop()
                self._serial_reader = None
        except Exception:
            pass

        # Show serial monitor panel to display flash output
        if not self._serial_panel.isVisible():
            self._serial_panel.setVisible(True)
            self._side.serial_monitor_button.setText("Serial Monitor \u25bc")

        # Store flash COM port for BNO reset later
        self._flash_com_port_for_reset = str(com_port)
        self._flash_pending_start_camera = False

        # Give OS time to release port handle
        QTimer.singleShot(500, self._continue_flash_hardware)

    def _continue_flash_hardware(self):
        """Continue flash after port release delay."""
        com_port = getattr(self, '_flash_com_port_for_reset', None)
        if not com_port:
            self._side.flash_start_button.setEnabled(True)
            return
        self.log_message("Flashing Arduino with latest sketch...")
        self._serial_panel.append_text("[FLASH] Flashing Arduino with latest sketch...")
        self._flash_latest_arduino_code(com_port, continue_setup=False)

    # ------------------------------------------------------------------
    # Setup system
    # ------------------------------------------------------------------
    def refresh_setup_dropdowns(self):
        # COM ports: fast enough to stay synchronous
        self._side.comport_combo.clear()
        ports = self._get_comports()
        if not ports:
            self._side.comport_combo.addItem("No COM ports found", None)
        else:
            for port, desc in ports:
                self._side.comport_combo.addItem(f"{port} - {desc}" if desc else port, port)

        # Cameras: probe in background thread
        self._side.camera_combo.clear()
        self._side.camera_combo.addItem("Scanning cameras...", -1)
        self._side.camera_combo.setEnabled(False)
        self._camera_probe_worker = CameraProbeWorker(parent=self)
        self._camera_probe_worker.finished.connect(self._on_camera_probe_done)
        self._camera_probe_worker.start()

    def _on_camera_probe_done(self, cams: list):
        self._side.camera_combo.clear()
        self._side.camera_combo.setEnabled(True)
        if not cams:
            self._side.camera_combo.addItem("No cameras found", -1)
        else:
            for c in cams:
                self._side.camera_combo.addItem(f"Camera {c}", c)

    def _get_comports(self):
        if serial is None:
            return []
        try:
            return [(p.device, p.description) for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    def _find_arduino_cli_executable(self) -> Optional[str]:
        candidates = [
            "arduino-cli",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Arduino CLI", "arduino-cli.exe"),
            r"C:\Program Files\Arduino CLI\arduino-cli.exe",
            r"C:\Program Files (x86)\Arduino CLI\arduino-cli.exe",
        ]
        for c in candidates:
            try:
                if c == "arduino-cli":
                    resolved = shutil.which(c)
                    if resolved:
                        return resolved
                elif Path(c).exists():
                    return c
            except Exception:
                pass
        return None

    _VID_PID_FQBN_MAP = {
        ("0x10C4", "0xEA60"): "esp32:esp32:esp32",
        ("0x1A86", "0x7523"): "esp32:esp32:esp32",
    }

    def save_setup_and_start_camera(self):
        """Save camera/COM selections and start live preview."""
        camera_idx = self._side.camera_combo.currentData()
        if camera_idx is None or camera_idx == -1:
            QMessageBox.warning(self, "No Camera Selected", "Please select a valid camera.")
            return
        com_port = self._side.comport_combo.currentData()
        if com_port is None:
            QMessageBox.warning(self, "No COM Port Selected", "Please select a valid COM port.")
            return

        self.selected_camera_idx = camera_idx
        self.selected_com_port = com_port
        self.log_message(f"Setup Saved: Camera {camera_idx} and COM PORT {com_port}")

        # Start camera live preview
        self.start_live_preview(camera_idx)

        # Start serial reader (background, for recording use)
        self._ensure_serial_reader_running()

        # Enable recording
        self._side.set_recording_enabled(True)

        # Enable serial monitor
        self._side.serial_monitor_button.setEnabled(True)
        set_button_enabled_style(self._side.serial_monitor_button, True)

    def _flash_latest_arduino_code(self, com_port: str, continue_setup: bool = False) -> bool:
        sketch_dir = PROJECT_ROOT / "ArduinoCode" / "sensorOutput"
        sketch_file = sketch_dir / "sensorOutput.ino"
        if not sketch_dir.exists() or not sketch_file.exists():
            self._serial_panel.append_text(f"[ERROR] Sketch not found at {sketch_file}")
            return False
        cli_path = self._find_arduino_cli_executable()
        if not cli_path:
            self._serial_panel.append_text("[ERROR] arduino-cli not found.")
            return False
        self._flash_pending_start_camera = continue_setup
        self._serial_panel.append_text("[FLASH] Detecting board type...")
        # Detect FQBN in background thread (avoids 12s timeout on main thread)
        self._fqbn_worker = FQBNDetectWorker(cli_path, com_port, sketch_dir, parent=self)
        self._fqbn_worker.finished.connect(
            lambda fqbn, cc, uc: self._on_fqbn_detected(fqbn, cc, uc, com_port)
        )
        self._fqbn_worker.start()
        return True

    def _on_fqbn_detected(self, fqbn: str, compile_cmd: list, upload_cmd: list, com_port: str):
        self._serial_panel.append_text(f"[FLASH] Detected FQBN: {fqbn}")
        self._run_flash_async(compile_cmd, upload_cmd, com_port)

    def _run_flash_async(self, compile_cmd, upload_cmd, com_port):
        self._is_flashing_arduino = True
        self._flash_compile_cmd = compile_cmd
        self._flash_upload_cmd = upload_cmd
        self._flash_com_port = com_port
        self._flash_compile_ok = False
        self._flash_upload_ok = False
        self._flashing_stage = "compile"
        self._serial_panel.append_text(f"[FLASH] Running: {' '.join(compile_cmd)}")
        self.flash_thread = ArduinoFlasher(compile_cmd, timeout_s=180.0)
        self.flash_thread.output_line.connect(self._serial_panel.append_text)
        self.flash_thread.finished.connect(self._on_flash_compile_finished)
        self.flash_thread.start()

    def _on_flash_compile_finished(self, rc: int, output: str):
        if rc == 0:
            self._flash_compile_ok = True
            self._serial_panel.append_text("[FLASH] Compile successful, starting upload...")
            self._flashing_stage = "upload"
            self._serial_panel.append_text(f"[FLASH] Running: {' '.join(self._flash_upload_cmd)}")
            self.flash_thread = ArduinoFlasher(self._flash_upload_cmd, timeout_s=180.0)
            self.flash_thread.output_line.connect(self._serial_panel.append_text)
            self.flash_thread.finished.connect(self._on_flash_upload_finished)
            self.flash_thread.start()
        else:
            self._is_flashing_arduino = False
            self._serial_panel.append_text(f"[FLASH] Compile failed: {output}")
            self._show_flash_result(False, "Compile failed")

    def _on_flash_upload_finished(self, rc: int, output: str):
        self._is_flashing_arduino = False
        if rc == 0:
            self._flash_upload_ok = True
            self._serial_panel.append_text("[FLASH] Upload successful")
            self._show_flash_result(True, f"Uploaded to {self._flash_com_port}")
        else:
            self._serial_panel.append_text(f"[FLASH] Upload failed: {output}")
            self._show_flash_result(False, "Upload failed")

    def _show_flash_result(self, success: bool, msg: str):
        if success:
            self.log_message("Arduino flash finished successfully!")
            self._serial_panel.append_text("[FLASH] Resetting BNO055 sensor...")
            self.log_message("Resetting BNO055 sensor...")
            self._reset_bno055_after_flash()
        else:
            self.log_message(f"Arduino flash failed: {msg}")
            self._side.flash_start_button.setEnabled(True)
            QMessageBox.critical(self, "Flash Failed", msg)

    # ------------------------------------------------------------------
    # BNO055 reset after flash
    # ------------------------------------------------------------------
    def _reset_bno055_after_flash(self):
        # Give ESP32 time to boot -- use QTimer instead of blocking sleep
        QTimer.singleShot(2000, self._reset_bno055_start)

    def _reset_bno055_start(self):
        # Use the flash COM port for the serial reader during BNO reset
        flash_port = getattr(self, '_flash_com_port_for_reset', None) or self.selected_com_port
        if flash_port:
            self.selected_com_port = flash_port
        try:
            self._ensure_serial_reader_running()
        except Exception as e:
            self._serial_panel.append_text(f"[ERROR] Cannot open serial after flash: {e}")
            self._finish_bno_reset(success=False)
            return
        if self._serial_reader is None:
            self._serial_panel.append_text("[ERROR] Serial reader not available for BNO055 reset")
            self._finish_bno_reset(success=False)
            return
        self._serial_monitor_timer.start(50)
        self._bno_reset_attempts = 0
        self._bno_reset_max_attempts = 3
        self._send_bno_reset_command()

    def _send_bno_reset_command(self):
        if self._serial_reader is not None:
            self._serial_reader.flush_input()
            self._serial_reader.send_line("RESET_BNO")
            self._serial_panel.append_text("[BNO055] Sent RESET_BNO command")
        self._bno_reset_start_time = time.time()
        self._bno_reset_timer = QTimer(self)
        self._bno_reset_timer.timeout.connect(self._check_bno_reset_response)
        self._bno_reset_timer.start(BNO_RESET_CHECK_MS)

    def _check_bno_reset_response(self):
        elapsed = time.time() - self._bno_reset_start_time
        if self._serial_reader is not None:
            lines = self._serial_reader.pop_lines()
            for line in lines:
                self._serial_panel.append_text(line)
                if "BNO055_READY" in line:
                    self._bno_reset_timer.stop()
                    self._serial_panel.append_text("[BNO055] Sensor reset successful")
                    self.log_message("BNO055 sensor reset successful")
                    self._finish_bno_reset(success=True)
                    return
                if "BNO055_ERROR" in line:
                    self._bno_reset_timer.stop()
                    self._bno_reset_attempts += 1
                    if self._bno_reset_attempts < self._bno_reset_max_attempts:
                        self._serial_panel.append_text(
                            f"[BNO055] Reset failed, retrying ({self._bno_reset_attempts}/{self._bno_reset_max_attempts})..."
                        )
                        self._send_bno_reset_command()
                    else:
                        self._serial_panel.append_text("[BNO055] Reset failed after all retries")
                        self._finish_bno_reset(success=False)
                    return
        if elapsed > BNO_RESET_TIMEOUT_S:
            self._bno_reset_timer.stop()
            self._bno_reset_attempts += 1
            if self._bno_reset_attempts < self._bno_reset_max_attempts:
                self._serial_panel.append_text(
                    f"[BNO055] Reset timed out, retrying ({self._bno_reset_attempts}/{self._bno_reset_max_attempts})..."
                )
                self._send_bno_reset_command()
            else:
                self._serial_panel.append_text("[BNO055] Reset timed out after all retries -- proceeding anyway")
                self._finish_bno_reset(success=True)

    def _finish_bno_reset(self, success: bool):
        try:
            if hasattr(self, '_bno_reset_timer') and self._bno_reset_timer.isActive():
                self._bno_reset_timer.stop()
        except Exception:
            pass
        if success:
            self.log_message("BNO055 reset successful -- hardware is ready")
        else:
            self.log_message("BNO055 reset failed")
        self._flash_pending_start_camera = False
        self._side.flash_start_button.setEnabled(True)

    def start_live_preview(self, camera_idx):
        try:
            if self.cap:
                self.cap.release()
            self.cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                QMessageBox.critical(self, "Camera Error", f"Cannot open camera {camera_idx}")
                return
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, DEFAULT_RECORDING_FPS)
            self._viewer.viewer_label.setText("Live Camera Preview")
            if not hasattr(self, '_live_preview_timer'):
                self._live_preview_timer = QTimer()
                self._live_preview_timer.timeout.connect(self._update_live_preview)
            self._live_preview_timer.start(LIVE_PREVIEW_MS)
            self.log_message(f"Started live preview from camera {camera_idx}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start live preview: {e}")
            self.log_message(f"Error starting live preview: {e}")

    def _update_live_preview(self):
        if not self.cap or not self.cap.isOpened():
            if hasattr(self, '_live_preview_timer'):
                self._live_preview_timer.stop()
            return
        ret, frame = self.cap.read()
        if ret:
            self._viewer.update_preview(frame)
        else:
            if hasattr(self, '_live_preview_timer'):
                self._live_preview_timer.stop()

    # ------------------------------------------------------------------
    # Serial monitor
    # ------------------------------------------------------------------
    def _toggle_serial_monitor(self):
        visible = not self._serial_panel.isVisible()
        self._serial_panel.setVisible(visible)
        self._side.serial_monitor_button.setText("Serial Monitor \u25bc" if visible else "Serial Monitor")
        if visible:
            if not self._is_flashing_arduino:
                self._ensure_serial_reader_running()
                self._serial_monitor_timer.start(50)
        else:
            try:
                self._serial_monitor_timer.stop()
            except Exception:
                pass
            if not self.is_recording:
                self._stop_serial_capture(stop_reader=True)

    def _ensure_serial_reader_running(self):
        com_port = self.selected_com_port
        if not com_port:
            self.log_message("No COM port selected. Use Setup System first.")
            return
        if serial is None:
            self.log_message("Serial features disabled (pyserial not installed).")
            return
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

    def _serial_monitor_tick(self):
        if not self._serial_panel.isVisible():
            return
        reader = self._serial_reader
        if reader is None:
            return
        try:
            lines = reader.pop_lines()
        except Exception:
            return
        if lines:
            self._serial_panel.append_lines(lines)

    def _start_serial_csv_logging(self, out_video_path: Path):
        self._ensure_serial_reader_running()
        if self._serial_reader is None:
            return
        csv_path = out_video_path.parent / "IMUTimeStamp.csv"
        header = "timestamp_ms, Q.W, Q.X, Q.Y, Q.Z, W.X, W.Y, W.Z, A.X, A.Y, A.Z"
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

    def _sync_imu_timebase(self, timeout_s: float = 0.6):
        reader = self._serial_reader
        if reader is None:
            return
        record_start_us = getattr(self, "record_start_host_us", None)
        if record_start_us is None:
            record_start_us = float(time.perf_counter() * 1_000_000.0)
            self.record_start_host_us = record_start_us
        try:
            reader.flush_input()
        except Exception:
            pass
        self._imu_sync_send_us = float(time.perf_counter() * 1_000_000.0)
        try:
            reader.send_line("SYNC")
        except Exception:
            pass
        self._imu_sync_deadline = time.perf_counter() + float(timeout_s)
        self._imu_sync_record_start_us = record_start_us
        # Poll via QTimer instead of busy-wait
        if not hasattr(self, '_imu_sync_timer'):
            self._imu_sync_timer = QTimer(self)
            self._imu_sync_timer.timeout.connect(self._imu_sync_poll)
        self._imu_sync_timer.start(IMU_SYNC_POLL_MS)

    def _imu_sync_poll(self):
        reader = self._serial_reader
        if reader is None:
            self._imu_sync_timer.stop()
            self.log_message("IMU sync: SYNC not received; logging raw Arduino timestamps")
            return
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
                continue
            # Sync found
            self._imu_sync_timer.stop()
            t_mid_us = (self._imu_sync_send_us + t_recv_us) / 2.0
            sync_offset_us = t_mid_us - arduino_us
            try:
                reader.set_time_sync(sync_offset_us, float(self._imu_sync_record_start_us))
            except Exception:
                pass
            self.log_message("IMU sync: established")
            return
        # Check timeout
        if time.perf_counter() >= self._imu_sync_deadline:
            self._imu_sync_timer.stop()
            try:
                reader.set_time_sync(None, None)
            except Exception:
                pass
            self.log_message("IMU sync: SYNC not received; logging raw Arduino timestamps")

    def _stop_serial_capture(self, stop_reader: bool = False):
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

    # ------------------------------------------------------------------
    # Frame timestamp logging
    # ------------------------------------------------------------------
    def _start_frame_timestamp_logging(self, out_video_path: Path):
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

    def _log_recorded_frame_timestamp(self, timestamp_ms: float):
        writer = self._frame_ts_writer
        if writer is None:
            return
        ts_ms = max(0.0, float(timestamp_ms))
        try:
            writer.writerow([int(self._record_frame_index), f"{ts_ms:.3f}", f"{(ts_ms / 1000.0):.6f}"])
            self._record_frame_index += 1
            self._record_last_frame_ts_ms = ts_ms
            # Batch flush: once per second instead of every frame
            now = time.perf_counter()
            if now - getattr(self, '_frame_ts_last_flush', 0.0) >= 1.0:
                if self._frame_ts_fp is not None:
                    self._frame_ts_fp.flush()
                self._frame_ts_last_flush = now
        except Exception:
            pass

    def _stop_frame_timestamp_logging(self):
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

    def _update_recording_timeline(self):
        out_fps = float(getattr(self, "_record_out_fps", 30.0) or 30.0)
        frame_count = int(getattr(self, "_record_frame_index", 0))
        if frame_count <= 0:
            return
        self.total_frames = frame_count
        self.fps = out_fps
        self.current_frame = max(0, frame_count - 1)
        self._viewer.timeline_slider.setEnabled(True)
        self._viewer.timeline_slider.setMaximum(max(0, self.total_frames - 1))
        self._viewer.timeline_slider.setValue(self.current_frame)
        duration_seconds = int(self.total_frames / max(1.0, self.fps))
        self._viewer.current_time_label.setText("00:00:00")
        self._viewer.total_time_label.setText(self._viewer.seconds_to_time(duration_seconds))

    def _align_imu_csv_duration(self, csv_path, target_end_ms):
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
        scale = float(target_end_ms) / src_end if src_end > 0 else 1.0
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

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def start_recording(self):
        if self.is_recording:
            return
        if self.selected_camera_idx is None:
            QMessageBox.warning(self, "No Camera", "Please setup a camera first using the Setup System.")
            return

        try:
            if self._play_timer.isActive():
                self._play_timer.stop()
            self._viewer.play_pause_button.setText("\u25b6")
        except Exception:
            pass
        try:
            if hasattr(self, '_live_preview_timer') and self._live_preview_timer.isActive():
                self._live_preview_timer.stop()
        except Exception:
            pass
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass

        cap = cv2.VideoCapture(self.selected_camera_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            QMessageBox.critical(self, "Camera Error", f"Cannot open camera {self.selected_camera_idx}")
            return
        ret, frame = cap.read()
        if not ret:
            cap.release()
            QMessageBox.warning(self, "Error", "Unable to read frame to start recording.")
            return

        h, w = frame.shape[:2]
        session_dir = self._get_session_dir()
        session_dir.mkdir(parents=True, exist_ok=True)
        out_path = session_dir / "Recording.mp4"

        self._record_out_fps = float(self._side.recording_panel.get_recording_fps())
        self._record_frame_interval = 1.0 / self._record_out_fps

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, self._record_out_fps, (w, h))
        if not writer.isOpened():
            cap.release()
            QMessageBox.warning(self, "Warning", "VideoWriter could not be opened; recording disabled.")
            return

        self.cap = cap
        self.recording_writer = writer
        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.recording_file_path = str(out_path)
        self._record_start_perf = time.perf_counter()
        self.record_start_host_us = float(self._record_start_perf * 1_000_000.0)
        self._record_latest_frame = frame
        self._record_next_write_t = self._record_start_perf
        self._recording_started_logged = False

        self._start_frame_timestamp_logging(out_path)
        self._start_serial_csv_logging(out_path)

        self._side.recording_panel.start_btn.setEnabled(False)
        self._side.recording_panel.stop_btn.setEnabled(True)
        self._side.recording_panel.start_btn.setText("Recording...")
        self._side.recording_panel.fps_input.setEnabled(False)

        self._viewer.timeline_slider.setEnabled(True)
        self._viewer.timeline_slider.setMaximum(0)
        self._viewer.timeline_slider.setValue(0)
        self._viewer.current_time_label.setText("00:00:00")
        self._viewer.total_time_label.setText("00:00:00")

        try:
            self.recording_writer.write(frame)
            self._log_recorded_frame_timestamp(0.0)
            self._update_recording_timeline()
            self._viewer.update_preview(frame)
            self.log_message("Recording Started.")
            self._recording_started_logged = True
            self._record_next_write_t = time.perf_counter() + self._record_frame_interval
        except Exception:
            pass

        if not hasattr(self, '_record_timer'):
            self._record_timer = QTimer(self)
            self._record_timer.timeout.connect(self._record_tick)
        self._record_timer.start(RECORD_TICK_MS)

    def _record_tick(self):
        if not self.is_recording:
            return
        if not self.cap or not self.cap.isOpened():
            self.stop_recording()
            return
        ret, frame = self.cap.read()
        if ret:
            self._record_latest_frame = frame
            try:
                self._viewer.update_preview(frame)
            except Exception:
                pass
        now = time.perf_counter()
        loops = 0
        while now >= getattr(self, '_record_next_write_t', now) and loops < 5:
            lf = getattr(self, '_record_latest_frame', None)
            if lf is None:
                break
            try:
                if self.recording_writer:
                    self.recording_writer.write(lf)
                    base_t = self._record_start_perf
                    elapsed_ms = (time.perf_counter() - float(base_t)) * 1000.0 if base_t else 0.0
                    self._log_recorded_frame_timestamp(elapsed_ms)
                if not getattr(self, '_recording_started_logged', False):
                    self.log_message("Recording Started.")
                    self._recording_started_logged = True
            except Exception:
                break
            self._record_next_write_t += self._record_frame_interval
            loops += 1
        if loops > 0:
            self._update_recording_timeline()

    def stop_recording(self):
        if not self.is_recording:
            return
        serial_csv_path = self.serial_csv_path
        imu_count, imu_last_ms = 0, None
        try:
            if self._serial_reader is not None:
                imu_count, imu_last_ms = self._serial_reader.get_logging_stats()
        except Exception:
            pass
        frame_count = int(self._record_frame_index)
        frame_last_ms = float(self._record_last_frame_ts_ms) if frame_count > 0 else None

        try:
            self._stop_serial_capture(stop_reader=not self._serial_panel.isVisible())
        except Exception:
            pass

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

        try:
            self._stop_frame_timestamp_logging()
        except Exception:
            pass

        if hasattr(self, '_record_timer') and self._record_timer.isActive():
            try:
                self._record_timer.stop()
            except Exception:
                pass

        if self.recording_writer:
            try:
                self.recording_writer.release()
            except Exception:
                pass
            self.recording_writer = None

        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.is_recording = False
        self._side.recording_panel.start_btn.setEnabled(True)
        self._side.recording_panel.stop_btn.setEnabled(False)
        self._side.recording_panel.start_btn.setText("Start Recording")
        self._side.recording_panel.fps_input.setEnabled(True)

        # Move recording files to Raw Data
        try:
            if self.recording_file_path:
                rec_path = Path(self.recording_file_path)
                session = rec_path.parent
                raw_dir = session / "Raw Data"
                raw_dir.mkdir(parents=True, exist_ok=True)
                if rec_path.exists():
                    new_rec = raw_dir / rec_path.name
                    shutil.move(str(rec_path), str(new_rec))
                    self.recording_file_path = str(new_rec)
                for name in ("FrameTimestamp.csv", "IMUTimeStamp.csv"):
                    src = session / name
                    if src.exists():
                        shutil.move(str(src), str(raw_dir / name))
                self.log_message(f"Recording files moved to {raw_dir.name}/")
                # Save recording metadata
                try:
                    metadata = {
                        "recording_fps": self._record_out_fps,
                        "total_frames": int(self._record_frame_index),
                        "duration_ms": float(self._record_last_frame_ts_ms),
                    }
                    metadata_path = raw_dir / "recording_metadata.json"
                    with open(metadata_path, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2)
                    self.log_message(f"Recording metadata saved ({self._record_out_fps} fps)")
                except Exception as e:
                    self.log_message(f"Warning: Could not save recording metadata: {e}")
        except Exception as e:
            self.log_message(f"Warning: Could not move recording files: {e}")

        self.log_message("Recording Ended.")
        if frame_last_ms is not None and imu_last_ms is not None:
            delta_ms = abs(float(frame_last_ms) - float(imu_last_ms))
            self.log_message(
                f"Sync summary: frames={frame_count}, frame_end={frame_last_ms:.1f} ms; "
                f"imu_rows={imu_count}, imu_end={float(imu_last_ms):.1f} ms; delta={delta_ms:.1f} ms"
            )
        elif frame_last_ms is not None:
            self.log_message(f"Sync summary: frames={frame_count}, frame_end={frame_last_ms:.1f} ms; IMU rows={imu_count}")

        self.recording_fps = self._record_out_fps

        if self.recording_file_path:
            self.load_video_from_path(self.recording_file_path)

        self._save_recording_to_patient()

    def _save_recording_to_patient(self):
        """Emit signal so AppShell can push recording paths to patient profile."""
        video_path = self.recording_file_path or ""
        imu_path = ""
        if self.session_dir:
            candidate = Path(self.session_dir) / "Raw Data" / "IMUTimeStamp.csv"
            if candidate.exists():
                imu_path = str(candidate)
        if video_path or imu_path:
            self.recording_saved.emit(video_path, imu_path)
            self.log_message("Recording sent to patient profile")

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def _toggle_extract(self):
        if self._side.extract_button.isEnabled():
            if self._side.extract_collapsed:
                self._side.set_extract_expanded(True)
                self.start_extraction()
            else:
                self._side.set_extract_expanded(False)

    def start_extraction(self):
        """Phase 1: Extract ALL frames from the video. Phase 2 (segment CSVs) runs on completion."""
        if not self.session_dir:
            QMessageBox.warning(self, "No Session", "No session directory available. Load a video first.")
            return

        self.pause_video()
        self.log_message("Starting full-video frame extraction...")

        self._side.load_button.setEnabled(False)
        self._side.cancel_button.setVisible(True)
        self._side.progress_bar.setVisible(True)
        self._side.progress_bar.setValue(0)
        self._side.set_extract_expanded(True)

        session_path = Path(self.session_dir)
        frames_dir = session_path / "Output Data" / "Frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        self._whole_video_extractor = WholeVideoExtractor(
            video_path=self.video_path,
            output_folder=str(frames_dir),
            session_dir=self.session_dir,
        )
        self._whole_video_extractor.progress.connect(self._side.progress_bar.setValue)
        self._whole_video_extractor.finished.connect(self._on_whole_extraction_finished)
        self.worker_threads = [self._whole_video_extractor]
        self._whole_video_extractor.start()

    def _on_whole_extraction_finished(self, success: bool):
        """Phase 2: Generate per-segment CSVs after all frames are extracted."""
        if not success:
            self._side.progress_bar.setVisible(False)
            self._side.cancel_button.setVisible(False)
            self._side.load_button.setEnabled(True)
            self._side.set_extract_expanded(False)
            self.log_message("Frame extraction cancelled or failed.")
            return

        self.log_message("Full-video frame extraction complete.")

        # Phase 2: generate per-segment CSVs (fast, synchronous)
        session_path = Path(self.session_dir)
        frames_dir = session_path / "Output Data" / "Frames"
        frames_index_csv = str(frames_dir / "frame_index.csv")

        if self._segments.segments:
            for seg in self._segments.segments:
                name = seg["name"]
                fps = seg["fps_combo"].currentData()
                start_sec = QTime(0, 0).secsTo(seg["start"])
                end_sec = QTime(0, 0).secsTo(seg["end"])
                start_frame = int(start_sec * self.fps)
                end_frame = int(end_sec * self.fps)
                seg_output_dir = self._segment_frames_output_dir(seg)

                generator = SegmentCSVGenerator(
                    frames_index_csv=frames_index_csv,
                    segment_output_dir=seg_output_dir,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    extraction_fps=fps,
                    video_fps=self.fps,
                    segment_name=name,
                    session_dir=self.session_dir,
                )
                count = generator.generate()
                self.log_message(f"Segment '{name}': {count} frames mapped at {fps} fps")

        # Finalize
        self._side.progress_bar.setValue(100)
        self._side.progress_bar.setVisible(False)
        self._side.cancel_button.setVisible(False)
        self._side.load_button.setEnabled(True)
        set_button_enabled_style(self._side.view_frames_button, True)
        set_button_enabled_style(self._side.extract_button, True)
        set_button_enabled_style(self._side.reconstruct_button, True)
        self._side.set_extract_expanded(False)
        self.log_message("Frame extraction finished.")
        if self.patient_id and self.patient_db:
            self._link_extracted_frames_to_patient()
        QMessageBox.information(self, "Done", "Frame extraction complete.")

    def cancel_extraction(self):
        for worker in self.worker_threads:
            if worker.isRunning():
                worker.request_stop()
                worker.wait()
        self._side.progress_bar.setVisible(False)
        self._side.cancel_button.setVisible(False)
        self._side.load_button.setEnabled(True)
        self._side.set_extract_expanded(False)
        self.log_message("Frame extraction cancelled")

    # ------------------------------------------------------------------
    # Frame browser & reconstruction
    # ------------------------------------------------------------------
    def open_frame_browser(self):
        from frontend.frame_browser.frame_browser import FrameBrowser
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Load a video before viewing frames.")
            return

        session_path = Path(self.session_dir) if self.session_dir else None
        frames_dir = session_path / "Output Data" / "Frames" if session_path else None

        segments = []
        if frames_dir and frames_dir.exists():
            # Always show "All Frames" tab
            segments.append(("All Frames", str(frames_dir)))
            # Add per-segment filtered tabs
            for seg in self._segments.segments:
                seg_dir = self._segment_frames_output_dir(seg)
                csv_path = Path(seg_dir) / "segment_frames.csv"
                if csv_path.exists():
                    segments.append((seg["name"], str(frames_dir), str(csv_path)))

        if not segments:
            QMessageBox.warning(self, "No Frames", "No extracted frames found. Extract frames first.")
            return

        initial_selection = {folder: images.copy() for folder, images in self.selected_frames.items()}
        browser = FrameBrowser(
            segments,
            video_id=self.current_video_id or self.video_path,
            parent=self,
            initial_selection=initial_selection,
        )
        browser.exec()
        self.selected_frames = browser.selected_frames

    def start_reconstruction(self):
        terminal_text = self._side.terminal_display.toPlainText()
        self.navigate_to_reconstruction.emit({"terminal_log": terminal_text})

    def _build_session_info(self) -> dict | None:
        """Collect session paths for the reconstruction page."""
        if self.session_dir is None:
            return None

        session_dir = Path(self.session_dir)
        frames_dir = session_dir / "Output Data" / "Frames"
        if not frames_dir.is_dir():
            return None

        segments = []
        for seg in self._segments.segments:
            seg_dir = self._segment_frames_output_dir(seg)
            csv_path = Path(seg_dir) / "segment_frames.csv"
            if csv_path.exists():
                segments.append({
                    "name": seg["name"],
                    "segment_csv_path": str(csv_path),
                    "frames_dir": str(frames_dir),
                })

        if not segments:
            return None

        return {
            "session_dir": str(session_dir),
            "session_name": self.session_name or session_dir.name,
            "frames_dir": str(frames_dir),
            "segments": segments,
        }
