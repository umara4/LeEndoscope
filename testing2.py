import sys, os
from pathlib import Path

# Add GUI and backend directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'GUI'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'GUI', 'backend'))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QSlider, QFrame, QFileDialog, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

# ✅ Import your extraction function
from backend.extraction_service import extract_frames


class ExtractionWorker(QThread):
    progress = pyqtSignal(int)
    preview = pyqtSignal(object)

    def __init__(self, video_path, output_folder, fps):
        super().__init__()
        self.video_path = video_path
        self.output_folder = output_folder
        self.fps = fps

    def run(self):
        extract_frames(
            self.video_path,
            self.output_folder,
            frames_per_second=self.fps,
            progress_callback=self.progress.emit,
            preview_callback=self.preview.emit
        )


class MainWindow(QMainWindow):
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

        # Example slider
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

            # Start worker thread
            self.worker = ExtractionWorker(file_name, output_folder, fps=2)
            self.worker.progress.connect(self.progress.setValue)
            self.worker.preview.connect(self.update_preview)
            self.worker.start()

    def update_preview(self, frame):
        """Convert OpenCV frame to QPixmap and show in QLabel."""
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.viewer_label.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.viewer_label.size(), Qt.AspectRatioMode.KeepAspectRatio
        ))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())