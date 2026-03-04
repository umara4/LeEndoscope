"""
Create account window.

Split from ui_windows.py CreateAccountWindow.
Uses shared form_helpers and geometry_mixin.
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


class CreateAccountWindow(QWidget, CenteredWidgetMixin):
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
        self.setWindowTitle("Create Account")
        self.setMinimumWidth(400)
        self.restore_geometry_if_available()
        self.build_ui()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)

    def build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Create Account")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title)
        main_layout.addSpacing(10)

        # Email
        email_label = QLabel("Email:")
        self.email_input = QLineEdit()
        self.email_input.setFixedWidth(300)
        self.email_warning = QLabel("")
        self.email_warning.setStyleSheet("color: red; font-size: 12px;")
        self.email_input.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        email_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.email_input.textChanged.connect(self._validate_email)
        main_layout.addWidget(make_centered_form_row(email_label, self.email_input, self.email_warning))

        # Username
        username_label = QLabel("Username:")
        self.username_input = QLineEdit()
        self.username_input.setFixedWidth(300)
        self.username_warning = QLabel("")
        self.username_warning.setStyleSheet("color: red; font-size: 12px;")
        self.username_input.textChanged.connect(self._validate_username)
        main_layout.addWidget(make_centered_form_row(username_label, self.username_input, self.username_warning))

        # Password
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setFixedWidth(225)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.password_warning = QLabel("")
        self.password_warning.setStyleSheet("color: red; font-size: 12px;")
        self.password_warning.setWordWrap(True)
        self.password_input.textChanged.connect(self._validate_password)
        main_layout.addWidget(make_centered_form_row(password_label, self.password_input, self.password_warning))

        # Confirm Password
        confirm_label = QLabel("Confirm Password:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setFixedWidth(225)
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.confirm_warning = QLabel("")
        self.confirm_warning.setStyleSheet("color: red; font-size: 12px;")
        self.confirm_warning.setWordWrap(True)
        self.confirm_input.textChanged.connect(self._validate_confirm)
        main_layout.addWidget(make_centered_form_row(confirm_label, self.confirm_input, self.confirm_warning))

        # Password requirements
        self.pwd_req_label = QLabel(
            "Password Requirements:\n"
            "- At least 8 characters\n"
            "- One uppercase letter\n"
            "- One number\n"
            "- One special character (!, @, #, etc.)"
        )
        self.pwd_req_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pwd_req_label.setStyleSheet("font-size: 12px; color: gray;")
        main_layout.addWidget(self.pwd_req_label)
        main_layout.addSpacing(15)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        create_btn = AnimatedButton("Create Account")
        create_btn.setFixedSize(180, 40)
        create_btn.clicked.connect(self.create_account)

        cancel_btn = AnimatedButton("Cancel")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self._back_to_main)

        btn_layout.addWidget(create_btn)
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

    # --- Validation ---
    def _validate_username(self):
        username = self.username_input.text().strip()
        if self.db and self.db.username_exists(username):
            self.username_input.setStyleSheet("background-color: #FFCCCC")
            self.username_warning.setText("Username already in use")
        else:
            self.username_input.setStyleSheet("")
            self.username_warning.setText("")

    def _validate_email(self):
        email = self.email_input.text().strip()
        if self.db and self.db.email_exists(email):
            self.email_input.setStyleSheet("background-color: #FFCCCC")
            self.email_warning.setText("Email already in use!")
        else:
            self.email_input.setStyleSheet("")
            self.email_warning.setText("")

    def _validate_password(self):
        validate_password_field(
            self.password_input, self.password_warning,
            self.confirm_input, self.confirm_warning,
        )

    def _validate_confirm(self):
        validate_confirm_field(
            self.password_input, self.confirm_input, self.confirm_warning,
        )

    # --- Actions ---
    def create_account(self):
        if not password_ok(self.password_input.text()):
            QMessageBox.warning(self, "Error", "Password does not meet the requirements!")
            return
        if self.password_input.text() != self.confirm_input.text():
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return
        username = self.username_input.text().strip()
        pwd = self.password_input.text()
        email = self.email_input.text().strip()
        created = self.db.create_user(username, pwd, email) if self.db else False
        if created:
            QMessageBox.information(self, "Success", "Account created successfully!")
            if self.parent_window:
                try:
                    self.parent_window.apply_geometry_from(self)
                except Exception:
                    pass
                self.parent_window.show()
            self.save_geometry_on_close()
            self.close()
        else:
            QMessageBox.warning(self, "Error", "Username or email already exists!")

    def _back_to_main(self):
        self.save_geometry_on_close()
        self.close()
        if self.parent_window:
            try:
                self.parent_window.apply_geometry_from(self)
            except Exception:
                pass
            self.parent_window.show()
