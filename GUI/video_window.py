import os
import cv2
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFrame, QFileDialog,
    QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QIcon


class ExtractionWorker(QThread):
    progress = pyqtSignal(int)
    preview = pyqtSignal(object)
    frame_index = pyqtSignal(int)
    finished_parsing = pyqtSignal()

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

            self.preview.emit(frame)
            self.frame_index.emit(frame_count)

            if frame_count % interval == 0:
                filename = os.path.join(self.output_folder, f"frame_{saved_count:05d}.jpg")
                cv2.imwrite(filename, frame)
                saved_count += 1

            progress_val = int((frame_count / total_frames) * 100)
            self.progress.emit(progress_val)

            frame_count += 1

        cap.release()
        self.finished_parsing.emit()


class VideoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Surgical Imaging Interface")
        self.resize(1000, 600)

        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # --- Side Panel ---
        side_panel = QFrame()
        side_layout = QVBoxLayout(side_panel)

        self.load_button = QPushButton("Load Video")
        self.load_button.clicked.connect(self.load_video_file)
        side_layout.addWidget(self.load_button)

        self.extract_button = QPushButton("Extract Frames")
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self.start_extraction)
        side_layout.addWidget(self.extract_button)

        self.cancel_button = QPushButton("Cancel Extraction")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_extraction)
        side_layout.addWidget(self.cancel_button)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        side_layout.addWidget(self.progress)

        self.status_label = QLabel("Idle")
        side_layout.addWidget(self.status_label)

        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setMinimum(0)
        opacity_slider.setMaximum(100)
        side_layout.addWidget(QLabel("Opacity"))
        side_layout.addWidget(opacity_slider)

        # --- Central Viewer ---
        video_layout = QVBoxLayout()
        self.viewer_label = QLabel("Video Preview")
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_layout.addWidget(self.viewer_label, 4)

        # Timeline slider with time labels
        timebar_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00:00")
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setEnabled(False)
        self.timeline_slider.sliderReleased.connect(self.scrub_video)
        self.total_time_label = QLabel("00:00:00")

        timebar_layout.addWidget(self.current_time_label)
        timebar_layout.addWidget(self.timeline_slider, 1)
        timebar_layout.addWidget(self.total_time_label)
        video_layout.addLayout(timebar_layout)

        # Playback controls
        controls_layout = QHBoxLayout()
        self.back_button = QPushButton("<<")
        self.play_pause_button = QPushButton()
        self.play_pause_button.setIcon(QIcon.fromTheme("media-playback-start"))  # ▶️

        self.forward_button = QPushButton(">>")

        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.back_button.clicked.connect(lambda: self.skip_frames(-self.fps))   # jump 1 sec back
        self.forward_button.clicked.connect(lambda: self.skip_frames(self.fps)) # jump 1 sec forward

        controls_layout.addWidget(self.back_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.forward_button)
        video_layout.addLayout(controls_layout)

        main_layout.addWidget(side_panel, 1)
        main_layout.addLayout(video_layout, 4)

        self.setCentralWidget(central_widget)

        # State
        self.worker = None
        self.video_path = None
        self.total_frames = 0
        self.cap = None
        self.fps = 30
        self.current_frame = 0

        # Timer for playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

    # --- Video Loading ---
    def load_video_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        if file_name:
            self.video_path = file_name
            self.cap = cv2.VideoCapture(file_name)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
            self.current_frame = 0

            self.timeline_slider.setMaximum(self.total_frames - 1)
            self.timeline_slider.setEnabled(True)

            duration_seconds = self.total_frames // self.fps
            self.total_time_label.setText(self.seconds_to_time(duration_seconds))

            self.status_label.setText("Video loaded. Ready.")
            self.extract_button.setEnabled(True)

            # ✅ Show the very first frame immediately
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if ret:
                self.update_preview(frame)
                self.current_time_label.setText("00:00:00")
    # --- Scrubbing ---
    def scrub_video(self):
        if not self.cap:
            return
        frame_index = self.timeline_slider.value()
        self.current_frame = frame_index
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        if ret:
            self.update_preview(frame)
            self.current_time_label.setText(self.seconds_to_time(frame_index // self.fps))


    # --- Playback Controls ---
    def play_video(self):
        if self.cap:
            # don’t reset frame each tick, just let cap.read() advance
            self.timer.start(int(1000 / self.fps))

    def pause_video(self):
        self.timer.stop()
    
    def toggle_play_pause(self):
        if self.timer.isActive():
            self.pause_video()
            self.play_pause_button.setIcon(QIcon.fromTheme("media-playback-start"))  # ▶️
        else:
            self.play_video()
            self.play_pause_button.setIcon(QIcon.fromTheme("media-playback-pause"))  # ⏸️

    def next_frame(self):
        if not self.cap:
            return
        ret, frame = self.cap.read()
        if not ret:
            self.pause_video()
            return

        self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        self.update_preview(frame)
        self.timeline_slider.setValue(self.current_frame)
        self.current_time_label.setText(self.seconds_to_time(self.current_frame // self.fps))

    def skip_frames(self, n):
        if not self.cap:
            return
        self.current_frame = max(0, min(self.total_frames - 1, self.current_frame + n))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        ret, frame = self.cap.read()
        if ret:
            self.update_preview(frame)
            self.timeline_slider.setValue(self.current_frame)
            self.current_time_label.setText(self.seconds_to_time(self.current_frame // self.fps))

    # --- Extraction ---
    def start_extraction(self):
        if not self.video_path:
            return

        output_folder = "frames_output"
        self.status_label.setText("Extracting frames...")

        self.load_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        self.worker = ExtractionWorker(self.video_path, output_folder, fps=2)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.preview.connect(self.update_preview)
        self.worker.finished_parsing.connect(self.on_finished_parsing)
        self.worker.start()

    def cancel_extraction(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.status_label.setText("Extraction cancelled.")
            self.progress.setVisible(False)
            self.load_button.setEnabled(True)
            self.cancel_button.setVisible(False)

    def on_finished_parsing(self):
        self.progress.setVisible(False)
        self.status_label.setText("Done!")
        self.load_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        QMessageBox.information(self, "Done", "Frame extraction complete!")

    # --- Helpers ---
    def update_preview(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.viewer_label.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.viewer_label.size(), Qt.AspectRatioMode.KeepAspectRatio
        ))

    def seconds_to_time(self, seconds):
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:02}"