"""
Video capture window: select camera, start live preview+recording, stop, export frames.
"""
from pathlib import Path
import cv2
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox
)

RECORDINGS_DIR = Path(__file__).parent / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)

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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RECORDINGS_DIR / f"recording_{idx}_{timestamp}.mp4"
        ret, frame = self.capture.read()
        if not ret:
            QMessageBox.critical(self, "Error", "Failed to read from camera.")
            self.capture.release()
            self.capture = None
            return

        h, w = frame.shape[:2]
        fps = self.capture.get(cv2.CAP_PROP_FPS) or 20.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
        if not self.writer.isOpened():
            QMessageBox.warning(self, "Warning", "VideoWriter could not be opened; recording disabled.")
            self.writer = None

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
        QMessageBox.information(self, "Stopped", "Recording stopped and saved to recordings/")

    def export_frames(self):
        rec_file, _ = QFileDialog.getOpenFileName(self, "Select recording to export frames", str(RECORDINGS_DIR), "Video Files (*.mp4 *.avi)")
        if not rec_file:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Choose output folder for frames", str(RECORDINGS_DIR))
        if not out_dir:
            return
        self._extract_frames(str(rec_file), Path(out_dir))
        QMessageBox.information(self, "Exported", f"Frames exported to {out_dir}")

    def _extract_frames(self, video_path, out_dir: Path, step=1):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(video_path)
        idx = 0
        saved = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                fname = out_dir / f"frame_{idx:06d}.png"
                cv2.imwrite(str(fname), frame)
                saved += 1
            idx += 1
        cap.release()
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
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFrame, QFileDialog,
    QProgressBar, QMessageBox, QTimeEdit, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QInputDialog, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QTime, QEvent
from PyQt6.QtGui import QImage, QPixmap, QIcon
from geometry_store import load_geometry, save_geometry, get_start_size

class SegmentExtractor(QThread):
    progress = pyqtSignal(tuple)  # (segment_name, progress_value)
    finished_parsing = pyqtSignal(str)  # emits segment name when done

    def __init__(self, video_path, output_folder, start_frame, end_frame, fps=2, name=""):
        super().__init__()
        self.video_path = video_path
        self.output_folder = output_folder
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.fps = fps
        self.name = name

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
        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

        interval = max(1, int(cap.get(cv2.CAP_PROP_FPS) // self.fps)) if self.fps > 0 else 1
        frame_count, saved_count = self.start_frame, 0

        while frame_count < self.end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % interval == 0:
                filename = os.path.join(self.output_folder, f"frame_{saved_count:05d}.jpg")
                cv2.imwrite(filename, frame)
                saved_count += 1

            progress_val = int(((frame_count - self.start_frame) / (self.end_frame - self.start_frame)) * 100)
            self.progress.emit((self.name, progress_val))

            frame_count += 1

        cap.release()
        selected, rejected = self.eval_frames()
        self.finished_parsing.emit(self.name)

class VideoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Surgical Imaging Interface")
        self.resize(1000, 600)
        
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

        # Collapsible Start Camera section
        self.camera_panel_collapsed = True
        self.camera_button = QPushButton("Start Camera")
        self.camera_button.setFixedHeight(40)
        self.camera_button.clicked.connect(self.toggle_camera_panel)
        side_layout.addWidget(self.camera_button)

        # Camera content (hidden by default)
        self.camera_content = QWidget()
        cam_layout = QVBoxLayout(self.camera_content)
        cam_layout.setContentsMargins(5, 5, 5, 5)
        cam_layout.setSpacing(6)

        self.camera_combo = QComboBox()
        cams = []
        try:
            cams = probe_cameras()
        except Exception:
            pass
        if not cams:
            self.camera_combo.addItem("No cameras found", -1)
        else:
            for c in cams:
                self.camera_combo.addItem(f"Camera {c}", c)
        # auto-refresh when selection changes
        self.camera_combo.currentIndexChanged.connect(self.on_camera_selected)

        # Recording controls inside collapsible area
        btn_layout = QHBoxLayout()
        self.start_record_btn = QPushButton("Start Recording")
        self.start_record_btn.clicked.connect(self.start_camera_recording)
        self.start_record_btn.setEnabled(False)

        self.stop_record_btn = QPushButton("Stop Recording")
        self.stop_record_btn.clicked.connect(self.stop_camera_recording)
        self.stop_record_btn.setEnabled(False)

        btn_layout.addWidget(self.start_record_btn)
        btn_layout.addWidget(self.stop_record_btn)

        cam_layout.addWidget(self.camera_combo)
        cam_layout.addLayout(btn_layout)
        self.camera_content.setVisible(False)
        side_layout.addWidget(self.camera_content)

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

    def pause_video(self):
        if self.timer.isActive():
            self.timer.stop()

    def closeEvent(self, event):
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

    def open_frame_browser(self):
        from frame_browser import FrameBrowser
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Load a video before viewing frames.")
            return

        segments = [(seg["name"], f"{seg['name'].replace(' ', '_')}_frame_output") for seg in self.segments]

        initial_selection = {folder: images.copy() for folder, images in self.selected_frames.items()}
        # Filtering hook: if you add a filter/scoring routine, populate initial_selection
        # with any frames you wish to auto-uncheck before opening the browser.
        # Example (disabled):
        # for seg in self.segments:
        #     folder_path = f"{seg['name'].replace(' ', '_')}_frame_output"
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
            folder_name = f"{name.replace(' ', '_')}_frame_output"

            worker = SegmentExtractor(self.video_path, folder_name, start_frame, end_frame, fps=2, name=name)
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
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
        self.current_frame = 0
        # Reset any previous frame selections when a new video is loaded
        self.selected_frames = {}

        self.timeline_slider.setMaximum(max(0, self.total_frames - 1))
        self.timeline_slider.setEnabled(True)

        self.segment_list.clear()
        self.segments = []

        duration_seconds = self.total_frames // max(1, self.fps)
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
        from datetime import datetime
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
            # Minimum height for at least 1 item space
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

    # --- Camera capture methods (collapsible panel) ---
    def toggle_camera_panel(self):
        self.camera_panel_collapsed = not self.camera_panel_collapsed
        self.camera_content.setVisible(not self.camera_panel_collapsed)
        if self.camera_panel_collapsed:
            self.camera_button.setText("Start Camera")
        else:
            self.camera_button.setText("Start Camera ▼")
            # ensure camera list is up to date when expanded
            try:
                cams = probe_cameras()
            except Exception:
                cams = []
            self.camera_combo.clear()
            if not cams:
                self.camera_combo.addItem("No cameras found", -1)
            else:
                for c in cams:
                    self.camera_combo.addItem(f"Camera {c}", c)

    def on_camera_selected(self, index):
        idx = self.camera_combo.itemData(index)
        if idx is None or idx == -1:
            return
        # stop any existing camera preview
        if getattr(self, 'cam_timer', None) and self.cam_timer.isActive():
            self.cam_timer.stop()
        if getattr(self, 'cam_capture', None):
            try:
                self.cam_capture.release()
            except Exception:
                pass
            self.cam_capture = None

        # open new camera for preview (not recording)
        self.cam_capture = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not self.cam_capture or not self.cam_capture.isOpened():
            QMessageBox.warning(self, "Camera", f"Unable to open camera {idx}")
            return

        # enable start recording button now that preview is available
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)

        # start preview timer
        fps = self.cam_capture.get(cv2.CAP_PROP_FPS) or 20.0
        self.cam_timer = QTimer(self)
        self.cam_timer.timeout.connect(self._update_camera_frame)
        self.cam_timer.start(int(1000 / max(1, fps)))

        self.cam_recording = False
        self.cam_writer = None
        self.last_camera_recording = None
        self.recording_start_time = None
        self.log_message(f"Camera switched to Camera {idx}")

    def _update_camera_frame(self):
        if not getattr(self, 'cam_capture', None):
            return
        ret, frame = self.cam_capture.read()
        if not ret:
            return
        # show preview
        self.update_preview(frame)
        # record if active
        if getattr(self, 'cam_recording', False) and getattr(self, 'cam_writer', None):
            try:
                self.cam_writer.write(frame)
            except Exception:
                pass

    def start_camera_recording(self):
        if not getattr(self, 'cam_capture', None) or not self.cam_capture.isOpened():
            QMessageBox.warning(self, "No Preview", "Start camera preview before recording.")
            return
        # prepare writer
        idx = None
        # try to find selected camera index
        cur = self.camera_combo.currentIndex()
        idx = self.camera_combo.itemData(cur)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RECORDINGS_DIR / f"camera_recording_{idx}_{timestamp}.mp4"
        # grab a frame to get size
        ret, frame = self.cam_capture.read()
        if not ret:
            QMessageBox.warning(self, "Error", "Unable to read frame to start recording.")
            return
        h, w = frame.shape[:2]
        fps = self.cam_capture.get(cv2.CAP_PROP_FPS) or 20.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.cam_writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
        if not self.cam_writer.isOpened():
            self.cam_writer = None
            QMessageBox.warning(self, "Warning", "VideoWriter could not be opened; recording disabled.")

        self.cam_recording = True
        self.recording_start_time = datetime.now()
        self.last_camera_recording = str(out_path)
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        ts = self.recording_start_time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_message(f"Recording started at {ts}")

    def stop_camera_recording(self):
        if not getattr(self, 'cam_recording', False):
            return
        # stop writer
        if getattr(self, 'cam_writer', None):
            try:
                self.cam_writer.release()
            except Exception:
                pass
            self.cam_writer = None
        # also stop preview timer and release camera if present
        if getattr(self, 'cam_timer', None) and self.cam_timer.isActive():
            try:
                self.cam_timer.stop()
            except Exception:
                pass
        if getattr(self, 'cam_capture', None):
            try:
                self.cam_capture.release()
            except Exception:
                pass
            self.cam_capture = None

        self.cam_recording = False
        self.stop_record_btn.setEnabled(False)
        self.start_record_btn.setEnabled(True)

        # compute duration and log concise message
        duration = None
        if getattr(self, 'recording_start_time', None):
            end_time = datetime.now()
            duration = end_time - self.recording_start_time
            end_ts = end_time.strftime("%Y-%m-%d %H:%M:%S")
            self.log_message(f"Recording stopped at {end_ts} (duration {duration})")
        else:
            self.log_message("Recording stopped")

        # automatically load the saved recording into the player if it exists
        if getattr(self, 'last_camera_recording', None):
            rec_path = Path(self.last_camera_recording)
            if rec_path.exists():
                try:
                    self.load_video_from_path(str(rec_path))
                    self.log_message(f"Loaded recording {rec_path.name}")
                except Exception as e:
                    self.log_message(f"Failed to auto-load recording: {e}")
            else:
                self.log_message(f"Recorded file not found: {rec_path}")

        # show brief info to the user
        if getattr(self, 'last_camera_recording', None):
            QMessageBox.information(self, "Stopped", f"Recording finished. Duration: {duration}")

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
        return QTime(0, 0).addSecs(seconds).toString("HH:mm:ss")
