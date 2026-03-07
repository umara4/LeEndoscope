"""
Patient list sidebar widget.

Split from patient_profile.py PatientListWidget.
Uses shared theme styles.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QListWidget

from shared.theme import SUCCESS_BUTTON_STYLE, SIDE_PANEL_STYLE, ACCENT_BUTTON_STYLE


class PatientListWidget(QFrame):
    """Left sidebar with patient list and new patient button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SIDE_PANEL_STYLE)

        layout = QVBoxLayout(self)

        # New Patient Button
        self.new_patient_btn = QPushButton("+ New Patient")
        self.new_patient_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        layout.addWidget(self.new_patient_btn)

        # Patient List
        self.patient_list = QListWidget()
        layout.addWidget(self.patient_list)

        # Add stretch to push button to bottom
        layout.addStretch()

        # Load Patient Button at bottom
        self.go_to_surgery_btn = QPushButton("Load Patient")
        self.go_to_surgery_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        layout.addWidget(self.go_to_surgery_btn)
