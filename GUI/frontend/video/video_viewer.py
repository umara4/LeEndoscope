"""
Video viewer widget: display area, timeline, playback controls, segment addition.

Contains the central video display, timeline slider, play/pause/skip controls,
and the segment add row.
"""
from __future__ import annotations

import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QLineEdit, QTimeEdit,
)
from PyQt6.QtCore import Qt, QTime, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from shared.theme import (
    VIEWER_LABEL_STYLE, SLIDER_BASE_STYLE,
    SLIDER_GROOVE, SLIDER_HANDLE, SLIDER_HANDLE_BORDER,
    SEGMENT_HIGHLIGHT, BORDER_DEFAULT, SPACE_XS, RADIUS_SM,
)


class VideoViewer(QWidget):
    """Video display, timeline, playback controls, and segment add row."""

    add_segment_requested = pyqtSignal(str, QTime, QTime)  # (name, start, end)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Viewer label ---
        self.viewer_label = QLabel("Video Preview")
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_label.setMinimumSize(400, 300)
        self.viewer_label.setScaledContents(False)
        self.viewer_label.setStyleSheet(VIEWER_LABEL_STYLE)
        layout.addWidget(self.viewer_label, 4)

        # --- Timebar ---
        timebar = QHBoxLayout()
        self.current_time_label = QLabel("00:00:00")
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setEnabled(False)
        self.total_time_label = QLabel("00:00:00")
        timebar.addWidget(self.current_time_label)
        timebar.addWidget(self.timeline_slider, 1)
        timebar.addWidget(self.total_time_label)
        layout.addLayout(timebar)

        # --- Playback controls ---
        controls = QHBoxLayout()
        self.back_button = QPushButton("<<")
        self.back_button.setObjectName("back_button")
        self.back_button.setFixedSize(60, 40)

        self.play_pause_button = QPushButton("\u25b6")
        self.play_pause_button.setObjectName("play_pause_button")
        self.play_pause_button.setFixedSize(60, 40)

        self.forward_button = QPushButton(">>")
        self.forward_button.setObjectName("forward_button")
        self.forward_button.setFixedSize(60, 40)

        controls.addWidget(self.back_button)
        controls.addWidget(self.play_pause_button)
        controls.addWidget(self.forward_button)
        layout.addLayout(controls)

        # --- Segment add row ---
        seg_row = QHBoxLayout()
        self.segment_name_input = QLineEdit()
        self.segment_name_input.setPlaceholderText("Segment name")
        self.start_time_input = QTimeEdit()
        self.start_time_input.setDisplayFormat("HH:mm:ss")
        self.end_time_input = QTimeEdit()
        self.end_time_input.setDisplayFormat("HH:mm:ss")
        self.add_segment_btn = QPushButton("Add Segment")
        self.add_segment_btn.clicked.connect(self._on_add_segment)

        seg_row.addWidget(self.segment_name_input)
        seg_row.addWidget(QLabel("Start"))
        seg_row.addWidget(self.start_time_input)
        seg_row.addWidget(QLabel("End"))
        seg_row.addWidget(self.end_time_input)
        seg_row.addWidget(self.add_segment_btn)
        layout.addLayout(seg_row)

        # Slider base style for resetting
        self.slider_base_style = SLIDER_BASE_STYLE
        self.timeline_slider.setStyleSheet(self.slider_base_style)

    def _on_add_segment(self):
        name = self.segment_name_input.text()
        start = self.start_time_input.time()
        end = self.end_time_input.time()
        self.add_segment_requested.emit(name, start, end)

    def clear_segment_name(self):
        self.segment_name_input.clear()

    def set_video_duration(self, total_seconds: int):
        """Set the maximum allowed time for segment start/end inputs."""
        max_time = QTime(0, 0).addSecs(max(0, int(total_seconds)))
        self.start_time_input.setMaximumTime(max_time)
        self.end_time_input.setMaximumTime(max_time)

    def update_preview(self, frame):
        """Convert OpenCV frame to QPixmap and display."""
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self.viewer_label.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self.viewer_label.setPixmap(pixmap)

    def refresh_timeline_highlight(self, segments: list[dict], total_frames: int, fps: float):
        """Highlight slider regions for defined segments."""
        if not total_frames:
            self.timeline_slider.setStyleSheet(self.slider_base_style)
            return

        total = max(1, total_frames - 1)
        stops = [(0.0, SLIDER_GROOVE)]
        epsilon = 1.0 / max(10_000, total)
        for seg in segments:
            start_sec = QTime(0, 0).secsTo(seg["start"])
            end_sec = QTime(0, 0).secsTo(seg["end"])
            start_frame = max(0, int(start_sec * fps))
            end_frame = max(start_frame + 1, int(end_sec * fps))
            start_ratio = max(0.0, min(1.0, start_frame / total))
            end_ratio = max(start_ratio + epsilon, min(1.0, end_frame / total))
            stops.extend([
                (start_ratio, SLIDER_GROOVE),
                (min(1.0, start_ratio + epsilon), SEGMENT_HIGHLIGHT),
                (end_ratio, SEGMENT_HIGHLIGHT),
                (min(1.0, end_ratio + epsilon), SLIDER_GROOVE),
            ])
        stops.append((1.0, SLIDER_GROOVE))
        stops = sorted({(pos, color) for pos, color in stops}, key=lambda x: x[0])
        stop_str = ",\n        ".join(f"stop:{pos:.4f} {color}" for pos, color in stops)
        style = f"""
            QSlider::groove:horizontal {{
                border: 1px solid {BORDER_DEFAULT};
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    {stop_str});
                margin: {SPACE_XS} 0;
                border-radius: {RADIUS_SM};
            }}
            QSlider::handle:horizontal {{
                background: {SLIDER_HANDLE};
                border: 1px solid {SLIDER_HANDLE_BORDER};
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }}
        """
        self.timeline_slider.setStyleSheet(style)

    @staticmethod
    def seconds_to_time(seconds) -> str:
        return QTime(0, 0).addSecs(int(seconds)).toString("HH:mm:ss")
