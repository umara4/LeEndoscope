"""
Patient list sidebar widget.

Split from patient_profile.py PatientListWidget.
Uses shared theme styles.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QListWidget

from shared.theme import GREEN_BUTTON_STYLE, PATIENT_LIST_STYLE, SIDE_PANEL_STYLESHEET


class PatientListWidget(QFrame):
    """Left sidebar with patient list and new patient button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SIDE_PANEL_STYLESHEET)

        layout = QVBoxLayout(self)

        # New Patient Button
        self.new_patient_btn = QPushButton("+ New Patient")
        self.new_patient_btn.setStyleSheet(GREEN_BUTTON_STYLE)
        layout.addWidget(self.new_patient_btn)

        # Patient List
        self.patient_list = QListWidget()
        self.patient_list.setStyleSheet(PATIENT_LIST_STYLE)
        layout.addWidget(self.patient_list)

        # Add stretch to push button to bottom
        layout.addStretch()

        # Go to Surgery Button at bottom
        self.go_to_surgery_btn = QPushButton("Go to Surgery")
        self.go_to_surgery_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
        """)
        layout.addWidget(self.go_to_surgery_btn)
