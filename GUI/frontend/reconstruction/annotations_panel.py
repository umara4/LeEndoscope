"""
Annotations panel -- collapsible UI controls for remote annotation
workflow on the Nerfstudio viewer.

Provides:
- Enable/disable toggle
- Mode selector (Navigate / Draw)
- Finish / Clear buttons
- Status label

All controls route through an AnnotationController (HTTP client wrapper).
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout,
    QCheckBox, QComboBox, QPushButton, QLabel,
)
from PyQt6.QtCore import pyqtSignal

from shared.theme import STYLE_BOLD_LABEL, ACCENT_BUTTON_STYLE, TEXT_MUTED
from shared.form_helpers import set_button_enabled_style

# Optional: only imported if controller is set
from backend.annotation_controller import AnnotationController


class AnnotationsPanel(QWidget):
    """Annotation controls that talk to the remote Viewer via AnnotationController."""

    screenshot_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller: AnnotationController | None = None

        self._build_ui()
        self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_controller(self, controller: AnnotationController | None):
        """Bind or unbind the annotation controller."""
        self._controller = controller
        has_ctrl = controller is not None
        self._set_controls_enabled(has_ctrl)
        if not has_ctrl:
            # Reset UI state
            self._enable_cb.setChecked(False)
            self._mode_combo.setCurrentIndex(0)
            self._update_status()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # -- Enable toggle --
        self._enable_cb = QCheckBox("Enable Annotations")
        self._enable_cb.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self._enable_cb)

        # -- Mode selector --
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet(STYLE_BOLD_LABEL)
        layout.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Navigate", "Draw"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        # -- Action buttons --
        self._finish_btn = QPushButton("Finish Scribble")
        self._finish_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._finish_btn.clicked.connect(self._on_finish)
        layout.addWidget(self._finish_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(self._clear_btn)

        # -- Screenshot button --
        self._screenshot_btn = QPushButton("Screenshot")
        self._screenshot_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._screenshot_btn.clicked.connect(self.screenshot_requested.emit)
        layout.addWidget(self._screenshot_btn)

        # -- Status label --
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Enable / disable all controls
    # ------------------------------------------------------------------

    def _set_controls_enabled(self, enabled: bool):
        self._enable_cb.setEnabled(enabled)
        self._mode_combo.setEnabled(enabled)
        set_button_enabled_style(self._finish_btn, enabled)
        set_button_enabled_style(self._clear_btn, enabled)
        set_button_enabled_style(self._screenshot_btn, enabled)
        self._update_status()

    # ------------------------------------------------------------------
    # Control callbacks
    # ------------------------------------------------------------------

    def _on_enable_toggled(self, checked: bool):
        if self._controller:
            self._controller.set_scribble_enabled(checked)
        self._update_status()

    def _on_mode_changed(self, text: str):
        if self._controller:
            self._controller.set_scribble_mode(text.lower())
        self._update_status()

    def _on_finish(self):
        if self._controller:
            self._controller.finish_stroke()

    def _on_clear(self):
        if self._controller:
            self._controller.clear_strokes()

    # ------------------------------------------------------------------
    # Status display
    # ------------------------------------------------------------------

    def _update_status(self):
        if not self._controller:
            self._status_label.setText("Not connected")
            return
        enabled = self._enable_cb.isChecked()
        mode = self._mode_combo.currentText()
        state = "Enabled" if enabled else "Disabled"
        self._status_label.setText(f"{state} | Mode: {mode}")
