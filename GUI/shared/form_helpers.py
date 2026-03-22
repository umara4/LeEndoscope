"""
Shared form helpers and reusable UI components.

Consolidates duplicate code that was previously defined in multiple files:
- make_row() was duplicated 4 times across ui_windows.py
- password_ok() was duplicated in CreateAccountWindow and ResetPasswordWindow
- AnimatedButton was in ui_windows.py
- Button state helpers were duplicated 4+ times in VideoWindow
"""
from __future__ import annotations
import re

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPalette

from shared.theme import (
    BTN_DISABLED_BG, BTN_DISABLED_TEXT,
    BORDER_DEFAULT, BORDER_SUBTLE, RADIUS_SM, SPACE_MD,
    ERROR_BG,
)


# ---------------------------------------------------------------------------
# Form row builder (was duplicated 4x in ui_windows.py)
# ---------------------------------------------------------------------------
def make_centered_form_row(
    label_widget: QLabel,
    input_widget: QLineEdit,
    warning: QLabel | None = None,
    label_w: int = 160,
    input_w: int = 225,
    warning_w: int = 160,
) -> QWidget:
    """Build a 3-column centered row: label | input | warning.

    The center column has fixed width and is centered by the left/right
    expanding columns.
    """
    label_widget.setFixedWidth(label_w)
    input_widget.setFixedWidth(input_w)
    label_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
    label_widget.setWordWrap(True)

    # left area: contains the label, right-aligned
    left = QWidget()
    left_l = QHBoxLayout()
    left_l.setContentsMargins(0, 0, 0, 0)
    left_l.addWidget(label_widget, 0, Qt.AlignmentFlag.AlignRight)
    left.setLayout(left_l)

    # center area: contains the input and has fixed width
    center = QWidget()
    center_l = QHBoxLayout()
    center_l.setContentsMargins(0, 0, 0, 0)
    center_l.addWidget(input_widget, 0, Qt.AlignmentFlag.AlignCenter)
    center.setLayout(center_l)
    center.setFixedWidth(input_w)

    # right area: contains the warning, left-aligned
    right = QWidget()
    right_l = QHBoxLayout()
    right_l.setContentsMargins(0, 0, 0, 0)
    if warning:
        warning.setFixedWidth(warning_w)
        warning.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_l.addWidget(warning)
    right_l.addStretch()
    right.setLayout(right_l)

    row_h = QHBoxLayout()
    row_h.setContentsMargins(0, 0, 0, 0)
    row_h.addWidget(left, 1)
    row_h.addWidget(center, 0)
    row_h.addWidget(right, 1)

    container = QWidget()
    container.setLayout(row_h)
    return container


# ---------------------------------------------------------------------------
# Password validation (was duplicated in CreateAccountWindow + ResetPasswordWindow)
# ---------------------------------------------------------------------------
def password_ok(pwd: str) -> bool:
    """Validate password meets strength requirements.

    Requirements:
    - At least 10 characters
    - One uppercase letter
    - One lowercase letter
    - One digit
    - One special character (!@#$%^&*)
    """
    if len(pwd) < 10:
        return False
    if not re.search(r"[A-Z]", pwd):
        return False
    if not re.search(r"[a-z]", pwd):
        return False
    if not re.search(r"[0-9]", pwd):
        return False
    if not re.search(r"[!@#$%^&*]", pwd):
        return False
    return True


def validate_password_field(
    password_input: QLineEdit,
    password_warning: QLabel,
    confirm_input: QLineEdit | None = None,
    confirm_warning: QLabel | None = None,
):
    """Validate a password input field and optionally its confirmation field.

    Call this from textChanged signals.
    """
    pwd = password_input.text()
    palette = password_input.palette()
    if password_ok(pwd):
        palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        try:
            password_warning.setText("")
        except Exception:
            pass
    else:
        palette.setColor(QPalette.ColorRole.Base, QColor(ERROR_BG))
        try:
            password_warning.setText("Password does not meet requirements")
        except Exception:
            pass
    password_input.setPalette(palette)

    # Also validate confirm field if provided
    if confirm_input is not None and confirm_warning is not None:
        validate_confirm_field(password_input, confirm_input, confirm_warning)


def validate_confirm_field(
    password_input: QLineEdit,
    confirm_input: QLineEdit,
    confirm_warning: QLabel,
):
    """Validate that confirm field matches password field."""
    pwd = password_input.text()
    confirm = confirm_input.text()
    palette = confirm_input.palette()
    if confirm == pwd or confirm == "":
        palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        try:
            confirm_warning.setText("")
        except Exception:
            pass
    else:
        palette.setColor(QPalette.ColorRole.Base, QColor(ERROR_BG))
        try:
            confirm_warning.setText("Passwords do not match")
        except Exception:
            pass
    confirm_input.setPalette(palette)


# ---------------------------------------------------------------------------
# AnimatedButton (was in ui_windows.py)
# ---------------------------------------------------------------------------
class AnimatedButton(QPushButton):
    """A QPushButton that animates size on hover and pulses on click."""

    def __init__(self, *args, grow=1.08, duration=140, **kwargs):
        super().__init__(*args, **kwargs)
        self._grow = float(grow)
        self._duration = int(duration)
        self._base_size = None
        self._anim = None

    def _ensure_base(self):
        if self._base_size is None:
            self._base_size = self.size()
            self.setMaximumWidth(self._base_size.width())
            self.setMaximumHeight(self._base_size.height())

    def enterEvent(self, ev):
        self._ensure_base()
        target_w = int(self._base_size.width() * self._grow)
        target_h = int(self._base_size.height() * self._grow)
        self._start_anim(target_w, target_h)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._ensure_base()
        self._start_anim(self._base_size.width(), self._base_size.height())
        super().leaveEvent(ev)

    def mousePressEvent(self, ev):
        self._ensure_base()
        shrink_w = int(self._base_size.width() * 0.94)
        shrink_h = int(self._base_size.height() * 0.94)
        self._start_anim(
            shrink_w, shrink_h, duration=90,
            on_finished=lambda: self._start_anim(
                self._base_size.width(), self._base_size.height(), duration=120
            ),
        )
        super().mousePressEvent(ev)

    def _start_anim(self, target_w, target_h, duration=None, on_finished=None):
        duration = duration or self._duration
        if self._anim:
            try:
                self._anim[0].stop()
                self._anim[1].stop()
            except Exception:
                pass

        anim_w = QPropertyAnimation(self, b"maximumWidth")
        anim_w.setDuration(duration)
        anim_w.setEndValue(target_w)
        anim_w.setEasingCurve(QEasingCurve.Type.InOutQuad)

        anim_h = QPropertyAnimation(self, b"maximumHeight")
        anim_h.setDuration(duration)
        anim_h.setEndValue(target_h)
        anim_h.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._anim = (anim_w, anim_h)
        anim_w.start()
        anim_h.start()

        if on_finished:
            anim_h.finished.connect(on_finished)


# ---------------------------------------------------------------------------
# Button state helper (was duplicated 4+ times in VideoWindow)
# ---------------------------------------------------------------------------
def set_button_enabled_style(button: QPushButton, enabled: bool):
    """Set a button's enabled state with appropriate styling.

    When disabled, the button text turns grey and the button cannot be clicked.
    When enabled, the button inherits from the global APP_STYLESHEET.
    """
    button.setEnabled(enabled)
    if enabled:
        button.setStyleSheet("")  # Reset to inherit from APP_STYLESHEET
        # Force Qt to re-evaluate the global stylesheet for this widget
        style = button.style()
        if style:
            style.unpolish(button)
            style.polish(button)
        button.update()
    else:
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {BTN_DISABLED_BG};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: {RADIUS_SM};
                padding: {SPACE_MD};
                font-weight: bold;
                color: {BTN_DISABLED_TEXT};
            }}
        """)
