import os
import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFrame, QFileDialog,
    QProgressBar, QMessageBox, QTimeEdit, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QTime
from PyQt6.QtGui import QImage, QPixmap, QIcon

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

    def run(self):
        os.makedirs(self.output_folder, exist_ok=True)
        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

        interval = int(cap.get(cv2.CAP_PROP_FPS) // self.fps) if self.fps > 0 else 1
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
        self.finished_parsing.emit(self.name)

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

        side_layout.addWidget(QLabel("Segments"))
        self.segment_list = QListWidget()
        self.segment_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.segment_list.customContextMenuRequested.connect(self.show_segment_menu)
        side_layout.addWidget(self.segment_list)

        self.view_frames_button = QPushButton("View Extracted Frames")
        self.view_frames_button.setEnabled(False)
        self.view_frames_button.clicked.connect(self.open_frame_browser)
        side_layout.addWidget(self.view_frames_button)

        self.reconstruct_button = QPushButton("Start 3D Reconstruction")
        self.reconstruct_button.clicked.connect(self.start_reconstruction)
        side_layout.addWidget(self.reconstruct_button)

        # --- Central Viewer ---
        video_layout = QVBoxLayout()
        self.viewer_label = QLabel("Video Preview")
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_layout.addWidget(self.viewer_label, 4)

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

        controls_layout = QHBoxLayout()
        self.back_button = QPushButton("<<")
        self.play_pause_button = QPushButton()
        self.play_pause_button.setIcon(QIcon.fromTheme("media-playback-start"))
        self.forward_button = QPushButton(">>")

        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.back_button.clicked.connect(lambda: self.skip_frames(-self.fps))
        self.forward_button.clicked.connect(lambda: self.skip_frames(self.fps))

        controls_layout.addWidget(self.back_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.forward_button)
        video_layout.addLayout(controls_layout)

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
        video_layout.addLayout(segment_controls)

        main_layout.addWidget(side_panel, 1)
        main_layout.addLayout(video_layout, 4)
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

        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

    def pause_video(self):
        if self.timer.isActive():
            self.timer.stop()

    def update_segment_progress(self, data):
        name, value = data
        self.segment_progress[name] = value
        avg = sum(self.segment_progress.values()) / len(self.segment_progress)
        self.progress.setValue(int(avg))

    def on_finished_parsing(self, name):
        self.completed_segments += 1
        self.status_label.setText(f"Segment '{name}' done.")
        if self.completed_segments == len(self.segments):
            self.progress.setVisible(False)
            self.status_label.setText("✅ All segments extracted!")
            self.load_button.setEnabled(True)
            self.cancel_button.setVisible(False)
            self.view_frames_button.setEnabled(True)
            QMessageBox.information(self, "Done", "All segments have been extracted.")

    def open_frame_browser(self):
        from frame_browser import FrameBrowser
        # ✅ pass both segment name and folder path
        segments = [(seg["name"], f"{seg['name'].replace(' ', '_')}_frame_output") for seg in self.segments]
        browser = FrameBrowser(segments, self)
        browser.exec()

        # After closing, you can access selections:
        chosen = browser.selected_frames
        #print("User selected frames:", chosen)
        # chosen is a dict: {folder_path: {img_name: {"checked": bool, "modified": bool}}}
        self.selected_frames = chosen

    def start_extraction(self):
        if not self.cap or not self.segments:
            QMessageBox.warning(self, "No Segments", "Please define at least one segment before extracting.")
            return

        self.pause_video()
        self.status_label.setText("Extracting frames...")
        self.load_button.setEnabled(False)
        self.cancel_button.setVisible(True)
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
            self.video_path = file_name
            self.cap = cv2.VideoCapture(file_name)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
            self.current_frame = 0

            self.timeline_slider.setMaximum(self.total_frames - 1)
            self.timeline_slider.setEnabled(True)

            self.segment_list.clear()
            self.segments = []

            duration_seconds = self.total_frames // self.fps
            self.total_time_label.setText(self.seconds_to_time(duration_seconds))
            self.status_label.setText("Video loaded. Ready.")
            self.extract_button.setEnabled(True)

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

    def cancel_extraction(self):
        for worker in self.worker_threads:
            if worker.isRunning():
                worker.terminate()
                worker.wait()
        self.status_label.setText("Extraction cancelled.")
        self.progress.setVisible(False)
        self.load_button.setEnabled(True)
        self.cancel_button.setVisible(False)

    def start_reconstruction(self):
        # Placeholder for your 3D reconstruction pipeline
        # You can pass in selected frames or segment outputs here
        QMessageBox.information(self, "3D Reconstruction", "Starting 3D reconstruction process...")

        # Example: if you want to use selected frames
        if hasattr(self, "selected_frames"):
            # Filter checked frames
            checked_frames = []
            for folder, frames in self.selected_frames.items():
                for img, data in frames.items():
                    if data["checked"]:
                        checked_frames.append(os.path.join(folder, img))

            print("Frames to reconstruct:", checked_frames)
            # TODO: call your reconstruction algorithm here

    def update_preview(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(self.viewer_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.viewer_label.setPixmap(pixmap)

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
            self.play_pause_button.setIcon(QIcon.fromTheme("media-playback-start"))
        else:
            self.timer.start(int(1000 / self.fps))
            self.play_pause_button.setIcon(QIcon.fromTheme("media-playback-pause"))

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