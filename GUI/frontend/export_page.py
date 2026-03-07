"""
Export page placeholder (QWidget for embedding in AppShell).

No functionality yet -- displays a placeholder message.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from shared.theme import TEXT_SECONDARY


class ExportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        label = QLabel("Export functionality coming soon.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 16px;")
        layout.addWidget(label)
