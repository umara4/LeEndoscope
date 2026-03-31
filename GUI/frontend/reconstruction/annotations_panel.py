"""
Annotations panel -- collapsible UI controls for remote annotation
workflow on the Nerfstudio viewer.

Provides:
- Enable/disable toggle
- Mode selector (Navigate / Draw)
- Depth slider
- Finish / Clear Last / Clear All buttons
- Status label

All controls route through an AnnotationController (HTTP client wrapper).
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QComboBox, QSlider, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt, QTimer

from shared.theme import STYLE_BOLD_LABEL, ACCENT_BUTTON_STYLE, TEXT_MUTED
from shared.form_helpers import set_button_enabled_style

# Optional: only imported if controller is set
from backend.annotation_controller import AnnotationController


class AnnotationsPanel(QWidget):
    """Annotation controls that talk to the remote Viewer via AnnotationController."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller: AnnotationController | None = None

        # Debounce timer for depth slider
        self._depth_timer = QTimer(self)
        self._depth_timer.setSingleShot(True)
        self._depth_timer.setInterval(300)
        self._depth_timer.timeout.connect(self._send_depth)

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
            self._depth_slider.setValue(50)
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

        # -- Depth slider --
        depth_label = QLabel("Depth:")
        depth_label.setStyleSheet(STYLE_BOLD_LABEL)
        layout.addWidget(depth_label)

        depth_row = QHBoxLayout()
        self._depth_slider = QSlider(Qt.Orientation.Horizontal)
        self._depth_slider.setRange(0, 100)   # 0.0 – 10.0 in 0.1 steps
        self._depth_slider.setValue(50)        # default 5.0
        self._depth_slider.valueChanged.connect(self._on_depth_changed)
        depth_row.addWidget(self._depth_slider, stretch=1)

        self._depth_value = QLabel("5.0")
        self._depth_value.setFixedWidth(30)
        depth_row.addWidget(self._depth_value)
        layout.addLayout(depth_row)

        # -- Action buttons --
        self._finish_btn = QPushButton("Finish Scribble")
        self._finish_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._finish_btn.clicked.connect(self._on_finish)
        layout.addWidget(self._finish_btn)

        btn_row = QHBoxLayout()
        self._clear_last_btn = QPushButton("Clear Last")
        self._clear_last_btn.clicked.connect(self._on_clear_last)
        btn_row.addWidget(self._clear_last_btn)

        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.clicked.connect(self._on_clear_all)
        btn_row.addWidget(self._clear_all_btn)
        layout.addLayout(btn_row)

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
        self._depth_slider.setEnabled(enabled)
        set_button_enabled_style(self._finish_btn, enabled)
        set_button_enabled_style(self._clear_last_btn, enabled)
        set_button_enabled_style(self._clear_all_btn, enabled)
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

    def _on_depth_changed(self, value: int):
        depth = value / 10.0
        self._depth_value.setText(f"{depth:.1f}")
        # Debounce: restart timer on every slider tick
        self._depth_timer.start()

    def _send_depth(self):
        """Actually send the depth value after debounce delay."""
        if self._controller:
            depth = self._depth_slider.value() / 10.0
            self._controller.set_scribble_depth(depth)
        self._update_status()

    def _on_finish(self):
        if self._controller:
            self._controller.finish_stroke()

    def _on_clear_last(self):
        if self._controller:
            self._controller.clear_last_stroke()

    def _on_clear_all(self):
        if self._controller:
            self._controller.clear_all_strokes()

    # ------------------------------------------------------------------
    # Status display
    # ------------------------------------------------------------------

    def _update_status(self):
        if not self._controller:
            self._status_label.setText("Not connected")
            return
        enabled = self._enable_cb.isChecked()
        mode = self._mode_combo.currentText()
        depth = self._depth_slider.value() / 10.0
        state = "Enabled" if enabled else "Disabled"
        self._status_label.setText(f"{state} | Mode: {mode} | Depth: {depth:.1f}")
