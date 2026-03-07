"""
Side panel widget for the Video Window.

Contains: Load Data, Flash Hardware, Setup System, Serial Monitor toggle,
Recording, Segments, Extract Frames, View Frames buttons, and the terminal
display. Navigation buttons (Back to Patient, Reconstruct, Log Out) live
in the top bar above the video preview — see video_main_window.py.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTextEdit, QProgressBar, QWidget,
)

from shared.theme import SIDE_PANEL_STYLE, TERMINAL_DISPLAY_STYLE, TERMINAL_LABEL_STYLE, STYLE_BOLD_LABEL
from shared.form_helpers import set_button_enabled_style
from frontend.video.recording_panel import RecordingPanel


class SidePanel(QFrame):
    """Side panel with all control buttons and collapsible sections."""

    def __init__(self, has_patient: bool = False, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SIDE_PANEL_STYLE)

        layout = QVBoxLayout(self)

        # --- Load Data ---
        self.load_button = QPushButton("Load Data")
        layout.addWidget(self.load_button)

        # --- Flash Hardware (collapsible) ---
        self.flash_collapsed = True
        self.flash_button = QPushButton("Flash Hardware")
        self.flash_button.setFixedHeight(40)
        self.flash_button.clicked.connect(self.toggle_flash)
        layout.addWidget(self.flash_button)

        self.flash_content = QWidget()
        flash_layout = QVBoxLayout(self.flash_content)
        flash_layout.setContentsMargins(5, 5, 5, 5)
        flash_layout.setSpacing(6)

        flash_com_label = QLabel("Select COM Port:")
        flash_com_label.setStyleSheet(STYLE_BOLD_LABEL)
        self.flash_comport_combo = QComboBox()
        flash_layout.addWidget(flash_com_label)
        flash_layout.addWidget(self.flash_comport_combo)

        flash_btn_row = QHBoxLayout()
        self.flash_refresh_button = QPushButton("Refresh")
        self.flash_start_button = QPushButton("Flash && Reset BNO055")
        flash_btn_row.addWidget(self.flash_refresh_button)
        flash_btn_row.addWidget(self.flash_start_button)
        flash_layout.addLayout(flash_btn_row)

        self.flash_content.setVisible(False)
        layout.addWidget(self.flash_content)

        # --- Setup System (collapsible) ---
        self.setup_collapsed = True
        self.setup_button = QPushButton("Setup System")
        self.setup_button.setFixedHeight(40)
        self.setup_button.clicked.connect(self.toggle_setup)
        layout.addWidget(self.setup_button)

        self.setup_content = QWidget()
        setup_layout = QVBoxLayout(self.setup_content)
        setup_layout.setContentsMargins(5, 5, 5, 5)
        setup_layout.setSpacing(6)

        camera_label = QLabel("Select Camera:")
        camera_label.setStyleSheet(STYLE_BOLD_LABEL)
        self.camera_combo = QComboBox()
        setup_layout.addWidget(camera_label)
        setup_layout.addWidget(self.camera_combo)

        com_label = QLabel("Select COM Port:")
        com_label.setStyleSheet(STYLE_BOLD_LABEL)
        self.comport_combo = QComboBox()
        setup_layout.addWidget(com_label)
        setup_layout.addWidget(self.comport_combo)

        btn_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.save_setup_button = QPushButton("Save Setup")
        btn_row.addWidget(self.refresh_button)
        btn_row.addWidget(self.save_setup_button)
        setup_layout.addLayout(btn_row)

        self.setup_content.setVisible(False)
        layout.addWidget(self.setup_content)

        # --- Serial Monitor toggle ---
        self.serial_monitor_button = QPushButton("Serial Monitor")
        self.serial_monitor_button.setFixedHeight(40)
        layout.addWidget(self.serial_monitor_button)

        # --- Recording (collapsible) ---
        self.recording_collapsed = True
        self.recording_button = QPushButton("Recording")
        self.recording_button.setFixedHeight(40)
        self.recording_button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.recording_button)

        self.recording_panel = RecordingPanel()
        self.recording_panel.setVisible(False)
        layout.addWidget(self.recording_panel)

        # --- Segments (collapsible) ---
        self.segments_button = QPushButton("Segments")
        self.segments_button.setFixedHeight(40)
        layout.addWidget(self.segments_button)

        # Segment list is owned by SegmentControls, inserted by coordinator

        # --- Extract Frames ---
        self.extract_collapsed = True
        self.extract_button = QPushButton("Extract Frames")
        self.extract_button.setFixedHeight(40)
        self.extract_button.setEnabled(False)
        set_button_enabled_style(self.extract_button, False)
        layout.addWidget(self.extract_button)

        # Extract content (progress + cancel)
        self.extract_content = QWidget()
        ext_layout = QVBoxLayout(self.extract_content)
        ext_layout.setContentsMargins(5, 5, 5, 5)
        ext_layout.setSpacing(5)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        ext_layout.addWidget(self.progress_bar)

        self.cancel_button = QPushButton("Cancel Extraction")
        self.cancel_button.setVisible(False)
        ext_layout.addWidget(self.cancel_button)

        self.extract_content.setVisible(False)
        layout.addWidget(self.extract_content)

        # --- View Extracted Frames ---
        self.view_frames_button = QPushButton("View Extracted Frames")
        self.view_frames_button.setEnabled(False)
        set_button_enabled_style(self.view_frames_button, False)
        layout.addWidget(self.view_frames_button)

        # --- Start Reconstruction ---
        self.reconstruct_button = QPushButton("Start Reconstruction")
        self.reconstruct_button.setFixedHeight(40)
        layout.addWidget(self.reconstruct_button)

        # --- Spacer ---
        layout.addStretch(1)

        # --- Terminal ---
        terminal_label = QLabel("Terminal")
        terminal_label.setStyleSheet(TERMINAL_LABEL_STYLE)
        layout.addWidget(terminal_label)

        self.terminal_display = QTextEdit()
        self.terminal_display.setReadOnly(True)
        self.terminal_display.setFixedHeight(120)
        self.terminal_display.setStyleSheet(TERMINAL_DISPLAY_STYLE)
        layout.addWidget(self.terminal_display)

    # --- Toggle helpers ---
    def toggle_flash(self):
        self.flash_collapsed = not self.flash_collapsed
        self.flash_content.setVisible(not self.flash_collapsed)
        self.flash_button.setText("Flash Hardware \u25bc" if not self.flash_collapsed else "Flash Hardware")

    def toggle_setup(self):
        self.setup_collapsed = not self.setup_collapsed
        self.setup_content.setVisible(not self.setup_collapsed)
        self.setup_button.setText("Setup System \u25bc" if not self.setup_collapsed else "Setup System")

    def toggle_recording(self):
        self.recording_collapsed = not self.recording_collapsed
        self.recording_panel.setVisible(not self.recording_collapsed)
        self.recording_button.setText("Recording \u25bc" if not self.recording_collapsed else "Recording")

    def set_recording_enabled(self, enabled: bool):
        self.recording_button.setEnabled(enabled)
        self.recording_panel.start_btn.setEnabled(enabled)
        self.recording_panel.stop_btn.setEnabled(False)
        self.recording_panel.setEnabled(enabled)

    def set_extract_expanded(self, expanded: bool):
        self.extract_collapsed = not expanded
        self.extract_content.setVisible(expanded)
        self.extract_button.setText("Extract Frames \u25bc" if expanded else "Extract Frames")
