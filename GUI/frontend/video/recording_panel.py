"""
Recording panel widget (collapsible section content).

Contains the session name input and start/stop recording buttons.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton


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
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["20", "10", "5", "2", "1"])
        self.fps_combo.setCurrentIndex(0)  # default 20
        self.fps_combo.setFixedWidth(60)
        fps_row.addWidget(self.fps_combo)
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
        """Return selected FPS from the dropdown, defaulting to 20 if invalid."""
        try:
            return int(self.fps_combo.currentText())
        except (ValueError, TypeError):
            return 20
