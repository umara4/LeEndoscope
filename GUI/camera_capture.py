# A PyQt5 widget that provides camera selection, live preview, start/stop recording and frame extraction.

from PyQt5 import QtCore, QtGui, QtWidgets
import cv2
import os
import time

class CameraCaptureWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, max_test_idx=8, recordings_dir=None):
        super().__init__(parent)
        self.recordings_dir = recordings_dir or os.path.join(os.path.dirname(__file__), "recordings")
        os.makedirs(self.recordings_dir, exist_ok=True)

        # UI
        self.cam_combo = QtWidgets.QComboBox()
        self.refresh_btn = QtWidgets.QPushButton("Refresh Cameras")
        self.start_btn = QtWidgets.QPushButton("Start Video Capture")
        self.stop_btn = QtWidgets.QPushButton("Stop Capture")
        self.extract_btn = QtWidgets.QPushButton("Extract Frames from File")
        self.video_label = QtWidgets.QLabel()
        self.video_label.setFixedSize(640, 480)
        self.status_label = QtWidgets.QLabel("Idle")

        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(QtWidgets.QLabel("Camera:"))
        top_row.addWidget(self.cam_combo)
        top_row.addWidget(self.refresh_btn)
        top_row.addWidget(self.start_btn)
        top_row.addWidget(self.stop_btn)
        top_row.addWidget(self.extract_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.video_label)
        layout.addWidget(self.status_label)

        # State
        self._cap = None
        self._writer = None
        self._recording = False
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._query_frame)
        self._fps = 20.0
        self._fourcc = cv2.VideoWriter_fourcc(*"XVID")

        # Signals
        self.refresh_btn.clicked.connect(lambda: self._find_cameras(max_test_idx))
        self.start_btn.clicked.connect(self.start_capture)
        self.stop_btn.clicked.connect(self.stop_capture)
        self.extract_btn.clicked.connect(self.extract_frames_dialog)

        # Initialize camera list
        self._find_cameras(max_test_idx)

    def _find_cameras(self, max_idx=8):
        self.cam_combo.clear()
        found = []
        for i in range(0, max_idx):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap is None or not cap.isOpened():
                if cap:
                    cap.release()
                continue
            ret, _ = cap.read()
            if ret:
                found.append(i)
            cap.release()
        if not found:
            self.cam_combo.addItem("No cameras found", -1)
        else:
            for i in found:
                self.cam_combo.addItem(f"Camera {i}", i)
        self.status_label.setText(f"Found {len(found)} camera(s)")

    def start_capture(self):
        cam_idx = self.cam_combo.currentData()
        if cam_idx is None or cam_idx == -1:
            self.status_label.setText("No camera selected")
            return
        if self._cap and self._cap.isOpened():
            self.status_label.setText("Already capturing")
            return

        self._cap = cv2.VideoCapture(int(cam_idx), cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self.status_label.setText(f"Failed to open camera {cam_idx}")
            return

        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        fps = self._cap.get(cv2.CAP_PROP_FPS) or self._fps

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.recordings_dir, f"capture_cam{cam_idx}_{timestamp}.avi")
        self._writer = cv2.VideoWriter(filename, self._fourcc, fps, (w, h))
        if not self._writer.isOpened():
            # fallback: try MJPG
            self._fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            self._writer = cv2.VideoWriter(filename, self._fourcc, fps, (w, h))

        self._recording = True
        self._output_file = filename
        self._timer.start(int(1000 / max(1, fps)))
        self.status_label.setText(f"Recording to {os.path.basename(filename)}")

    def _query_frame(self):
        if not self._cap or not self._cap.isOpened():
            return
        ret, frame = self._cap.read()
        if not ret:
            return
        # write frame if recording
        if self._recording and self._writer:
            try:
                self._writer.write(frame)
            except Exception:
                pass

        # convert for display
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_img = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        scaled = qt_img.scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio)
        self.video_label.setPixmap(QtGui.QPixmap.fromImage(scaled))

    def stop_capture(self):
        self._timer.stop()
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        if self._writer:
            try:
                self._writer.release()
            except Exception:
                pass
            self._writer = None
        was_recording = self._recording
        self._recording = False
        if was_recording and hasattr(self, "_output_file"):
            self.status_label.setText(f"Saved: {os.path.basename(self._output_file)}")
        else:
            self.status_label.setText("Stopped")

    def extract_frames_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select video file", self.recordings_dir, "Video Files (*.avi *.mp4 *.mov *.mkv)")
        if not path:
            return
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder", os.path.dirname(path))
        if not out_dir:
            return
        self.extract_frames(path, out_dir)

    @staticmethod
    def extract_frames(video_path, out_dir, prefix="frame"):
        os.makedirs(out_dir, exist_ok=True)
        cap = cv2.VideoCapture(video_path)
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            fname = os.path.join(out_dir, f"{prefix}_{idx:06d}.png")
            cv2.imwrite(fname, frame)
            idx += 1
        cap.release()
        return idx

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = CameraCaptureWidget()
    w.show()
    sys.exit(app.exec_())