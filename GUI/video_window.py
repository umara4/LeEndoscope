# video_window.py
import os
import cv2
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFrame, QFileDialog, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap


class ExtractionWorker(QThread):
    progress = pyqtSignal(int)
    preview = pyqtSignal(object)
    finished_parsing = pyqtSignal()   # ✅ new signal

    def __init__(self, video_path, output_folder, fps=2):
        super().__init__()
        self.video_path = video_path
        self.output_folder = output_folder
        self.fps = fps

    def run(self):
        os.makedirs(self.output_folder, exist_ok=True)
        cap = cv2.VideoCapture(self.video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        interval = int(video_fps // self.fps) if self.fps > 0 else 1

        frame_count, saved_count = 0, 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Emit preview frame
            self.preview.emit(frame)

            # Save every Nth frame
            if frame_count % interval == 0:
                filename = os.path.join(self.output_folder, f"frame_{saved_count:05d}.jpg")
                cv2.imwrite(filename, frame)
                saved_count += 1

            # Emit progress
            progress_val = int((frame_count / total_frames) * 100)
            self.progress.emit(progress_val)

            frame_count += 1

        cap.release()
        self.finished_parsing.emit()   # ✅ notify when done


class VideoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Surgical Imaging Interface")
        self.resize(1000, 600)

        # --- Central Layout ---
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # --- Side Panel ---
        side_panel = QFrame()
        side_layout = QVBoxLayout(side_panel)

        load_button = QPushButton("Load Video")
        load_button.clicked.connect(self.load_video_file)
        side_layout.addWidget(load_button)

        self.progress = QProgressBar()
        side_layout.addWidget(self.progress)

        # ✅ Status label
        self.status_label = QLabel("Idle")
        side_layout.addWidget(self.status_label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        side_layout.addWidget(QLabel("Opacity"))
        side_layout.addWidget(slider)

        # --- Central Viewer (QLabel for frames) ---
        self.viewer_label = QLabel("Video Preview")
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Add to Layout ---
        main_layout.addWidget(side_panel, 1)
        main_layout.addWidget(self.viewer_label, 4)

        self.setCentralWidget(central_widget)

        # Worker thread placeholder
        self.worker = None

    def load_video_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        if file_name:
            output_folder = "frames_output"

            # Update status
            self.status_label.setText("Parsing frames...")

            # Start worker thread
            self.worker = ExtractionWorker(file_name, output_folder, fps=2)
            self.worker.progress.connect(self.progress.setValue)
            self.worker.preview.connect(self.update_preview)
            self.worker.finished_parsing.connect(self.on_finished_parsing)
            self.worker.start()

    def update_preview(self, frame):
        """Convert OpenCV frame to QPixmap and show in QLabel."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.viewer_label.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.viewer_label.size(), Qt.AspectRatioMode.KeepAspectRatio
        ))

    def on_finished_parsing(self):
        self.progress.setValue(100)
        self.status_label.setText("Done!")   # ✅ update status label
        QMessageBox.information(self, "Done", "Frame extraction complete!")