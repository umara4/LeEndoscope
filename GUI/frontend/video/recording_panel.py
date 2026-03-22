"""
Recording panel widget (collapsible section content).

Contains the session name input and start/stop recording buttons.
"""
from __future__ import annotations

from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton


class RecordingPanel(QWidget):
    """Recording controls: session name, FPS, start/stop buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        # Session name row
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Session Name:"))
        self.session_name_input = QLineEdit()
        self.session_name_input.setPlaceholderText("e.g., WhiteCylinder")
        session_row.addWidget(self.session_name_input)
        layout.addLayout(session_row)

        # Recording FPS row
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("Recording FPS:"))
        self.fps_input = QLineEdit()
        self.fps_input.setText("30")
        self.fps_input.setPlaceholderText("30")
        self.fps_input.setValidator(QIntValidator(1, 120))
        self.fps_input.setFixedWidth(60)
        fps_row.addWidget(self.fps_input)
        fps_row.addStretch()
        layout.addLayout(fps_row)

        # Start / Stop buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Recording")
        self.start_btn.setEnabled(True)
        self.stop_btn = QPushButton("End Recording")
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

    def get_recording_fps(self) -> int:
        """Return user-entered FPS, defaulting to 30 if invalid."""
        try:
            val = int(self.fps_input.text())
            return max(1, min(120, val))
        except (ValueError, TypeError):
            return 30
