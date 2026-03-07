"""
Serial monitor panel widget.

Provides a QFrame with text output, clear button, and autoscroll toggle
for displaying serial port data from an Arduino/ESP32.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit
from PyQt6.QtGui import QTextCursor

from shared.theme import SERIAL_MONITOR_STYLE


class SerialMonitorPanel(QFrame):
    """Serial monitor text display panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SERIAL_MONITOR_STYLE)

        self.autoscroll = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Serial Monitor"))
        header_row.addStretch(1)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(lambda: self.text_edit.clear())
        header_row.addWidget(self.clear_btn)

        self.autoscroll_btn = QPushButton("Auto-scroll: On")
        self.autoscroll_btn.setFixedHeight(28)
        self.autoscroll_btn.clicked.connect(self.toggle_autoscroll)
        header_row.addWidget(self.autoscroll_btn)

        layout.addLayout(header_row)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit, 1)

    def toggle_autoscroll(self):
        self.autoscroll = not self.autoscroll
        self.autoscroll_btn.setText(
            "Auto-scroll: On" if self.autoscroll else "Auto-scroll: Off"
        )

    def append_text(self, text: str) -> None:
        """Append text to the serial monitor, respecting autoscroll setting."""
        if not text:
            return
        try:
            vbar = self.text_edit.verticalScrollBar()
            prev_scroll = vbar.value()
            self.text_edit.append(str(text).rstrip("\r\n"))
            if self.autoscroll:
                self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
            else:
                vbar.setValue(prev_scroll)
        except Exception:
            pass

    def append_lines(self, lines: list[str]) -> None:
        """Append multiple lines efficiently."""
        if not lines:
            return
        try:
            vbar = self.text_edit.verticalScrollBar()
            prev_scroll = vbar.value()
            self.text_edit.append("\n".join(lines))
            if self.autoscroll:
                self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
            else:
                vbar.setValue(prev_scroll)
        except Exception:
            pass
