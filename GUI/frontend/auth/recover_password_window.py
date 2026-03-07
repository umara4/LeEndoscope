"""
Password recovery windows: RecoverPasswordWindow and ResetPasswordWindow.

Split from ui_windows.py. Uses shared form_helpers and geometry_mixin.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

from shared.form_helpers import (
    AnimatedButton, make_centered_form_row, password_ok,
    validate_password_field, validate_confirm_field,
)
from shared.geometry_mixin import CenteredWidgetMixin
from shared.theme import (
    STYLE_PAGE_TITLE, STYLE_INSTRUCTIONS_LABEL, STYLE_WARNING_LABEL,
    STYLE_REQUIREMENTS_LABEL,
)


class RecoverPasswordWindow(QWidget, CenteredWidgetMixin):
    def __init__(self, parent=None, db=None):
        super().__init__()
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.parent_window = parent
        self.db = db
        self.setWindowTitle("Recover Password")
        self.setMinimumSize(500, 300)
        try:
            self.restore_geometry_if_available()
        except Exception:
            pass
        try:
            self._build_ui()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error_layout(str(e))

    def _show_error_layout(self, error_msg):
        try:
            error_label = QLabel(f"Error loading window:\n\n{error_msg}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setWordWrap(True)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.close)
            layout = QVBoxLayout()
            layout.addWidget(error_label)
            layout.addWidget(close_btn)
            self.setLayout(layout)
            self.setMinimumSize(400, 200)
        except Exception:
            self.close()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Recover Password")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(STYLE_PAGE_TITLE)
        main_layout.addWidget(title)
        main_layout.addSpacing(10)

        instructions = QLabel("Enter your email or username to receive a password reset link")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        instructions.setStyleSheet(STYLE_INSTRUCTIONS_LABEL)
        main_layout.addWidget(instructions)
        main_layout.addSpacing(15)

        label = QLabel("Email or Username:")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter your email or username")
        self.input_field.setFixedWidth(300)
        self.input_warning = QLabel("")
        self.input_warning.setStyleSheet(STYLE_WARNING_LABEL)

        main_layout.addWidget(make_centered_form_row(label, self.input_field, self.input_warning))
        main_layout.addSpacing(20)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        send_btn = AnimatedButton("Send Recovery Link")
        send_btn.setFixedSize(180, 40)
        send_btn.clicked.connect(self.send_recovery_link)

        cancel_btn = AnimatedButton("Cancel")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self._back_to_main)

        btn_layout.addWidget(send_btn)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        content = QWidget()
        content.setLayout(main_layout)
        content.setMinimumWidth(640)
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        outer = QHBoxLayout()
        outer.addStretch()
        outer.addWidget(content)
        outer.addStretch()
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(outer)

    def send_recovery_link(self):
        try:
            input_value = self.input_field.text().strip()
            if not input_value:
                self.input_warning.setText("Please enter email or username")
                return

            username = None
            if input_value.count('@') > 0:
                username = self.db.get_user_by_email(input_value) if self.db else None
                if not username:
                    self.input_warning.setText("No account found with this email")
                    return
            else:
                if self.db and self.db.username_exists(input_value):
                    username = input_value
                else:
                    self.input_warning.setText("Username not found")
                    return

            reset_token = self.db.generate_reset_token(username) if self.db else None
            if not reset_token:
                self.input_warning.setText("Error generating reset token")
                return

            self.reset_window = ResetPasswordWindow(reset_token, parent=self.parent_window, db=self.db)
            self.transition_to(self.reset_window)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.input_warning.setText(f"Error: {str(e)[:50]}")

    def _back_to_main(self):
        self.save_geometry_on_close()
        self.close()
        if self.parent_window:
            try:
                self.parent_window.apply_geometry_from(self)
            except Exception:
                pass
            try:
                self.parent_window.show()
                self.parent_window.raise_()
                self.parent_window.activateWindow()
            except Exception:
                pass


class ResetPasswordWindow(QWidget, CenteredWidgetMixin):
    """Window for resetting password using a valid reset token."""

    def __init__(self, reset_token: str, parent=None, db=None):
        super().__init__()
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.reset_token = reset_token
        self.parent_window = parent
        self.db = db
        self.setWindowTitle("Reset Password")
        self.setMinimumSize(500, 400)
        try:
            self.restore_geometry_if_available()
        except Exception:
            pass
        try:
            self._build_ui()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error_layout(str(e))

    def _show_error_layout(self, error_msg):
        try:
            error_label = QLabel(f"Error loading window:\n\n{error_msg}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setWordWrap(True)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.close)
            layout = QVBoxLayout()
            layout.addWidget(error_label)
            layout.addWidget(close_btn)
            self.setLayout(layout)
            self.setMinimumSize(400, 200)
        except Exception:
            self.close()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)
        if self.parent_window:
            try:
                self.parent_window.apply_geometry_from(self)
            except Exception:
                pass
            try:
                self.parent_window.show()
                self.parent_window.raise_()
                self.parent_window.activateWindow()
            except Exception:
                pass
        else:
            try:
                from frontend.auth.login_window import MainLoginWindow
                main_login = MainLoginWindow(db=self.db)
                main_login.show()
            except Exception:
                pass

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Reset Your Password")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(STYLE_PAGE_TITLE)
        main_layout.addWidget(title)
        main_layout.addSpacing(10)

        instructions = QLabel("Enter your new password below")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setStyleSheet(STYLE_INSTRUCTIONS_LABEL)
        main_layout.addWidget(instructions)
        main_layout.addSpacing(15)

        # New Password
        password_label = QLabel("New Password:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter new password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.password_warning = QLabel("")
        self.password_warning.setStyleSheet(STYLE_WARNING_LABEL)
        self.password_warning.setWordWrap(True)
        self.password_input.textChanged.connect(self._validate_password)
        main_layout.addWidget(make_centered_form_row(
            password_label, self.password_input, self.password_warning, input_w=225
        ))

        # Confirm Password
        confirm_label = QLabel("Confirm Password:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm new password")
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.confirm_warning = QLabel("")
        self.confirm_warning.setStyleSheet(STYLE_WARNING_LABEL)
        self.confirm_warning.setWordWrap(True)
        self.confirm_input.textChanged.connect(self._validate_confirm)
        main_layout.addWidget(make_centered_form_row(
            confirm_label, self.confirm_input, self.confirm_warning, input_w=225
        ))

        # Requirements
        self.pwd_req_label = QLabel(
            "Password Requirements:\n"
            "- At least 10 characters\n"
            "- One uppercase letter\n"
            "- One lowercase letter\n"
            "- One number\n"
            "- One special character (!, @, #, $, %, ^, &, *)"
        )
        self.pwd_req_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pwd_req_label.setStyleSheet(STYLE_REQUIREMENTS_LABEL)
        main_layout.addWidget(self.pwd_req_label)
        main_layout.addSpacing(15)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        reset_btn = AnimatedButton("Reset Password")
        reset_btn.setFixedSize(180, 40)
        reset_btn.clicked.connect(self.reset_password)

        cancel_btn = AnimatedButton("Cancel")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self._back_to_main)

        btn_layout.addWidget(reset_btn)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        content = QWidget()
        content.setLayout(main_layout)
        content.setFixedWidth(640)
        content.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        outer = QHBoxLayout()
        outer.addStretch()
        outer.addWidget(content)
        outer.addStretch()
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(outer)

    def _validate_password(self):
        validate_password_field(
            self.password_input, self.password_warning,
            self.confirm_input, self.confirm_warning,
        )

    def _validate_confirm(self):
        validate_confirm_field(
            self.password_input, self.confirm_input, self.confirm_warning,
        )

    def reset_password(self):
        if not password_ok(self.password_input.text()):
            QMessageBox.warning(self, "Error", "Password does not meet the requirements!")
            return
        if self.password_input.text() != self.confirm_input.text():
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return

        new_password = self.password_input.text()
        if self.db and self.db.reset_password_with_token(self.reset_token, new_password):
            QMessageBox.information(self, "Success", "Password reset successfully! You can now log in with your new password.")
            self._go_to_main_login()
        else:
            QMessageBox.warning(self, "Error", "Invalid or expired reset token. Please try again.")
            self._back_to_main()

    def _back_to_main(self):
        self.save_geometry_on_close()
        self.close()
        if self.parent_window:
            try:
                self.parent_window.apply_geometry_from(self)
            except Exception:
                pass
            try:
                self.parent_window.show()
                self.parent_window.raise_()
                self.parent_window.activateWindow()
            except Exception:
                pass

    def _go_to_main_login(self):
        from frontend.auth.login_window import MainLoginWindow
        self.save_geometry_on_close()
        main_login = MainLoginWindow(db=self.db)
        self.transition_to(main_login)
