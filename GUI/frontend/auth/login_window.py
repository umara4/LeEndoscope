"""
Login windows: MainLoginWindow and LoginWindow.

Split from ui_windows.py. Uses shared form_helpers and geometry_mixin.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from shared.form_helpers import AnimatedButton, make_centered_form_row
from shared.geometry_mixin import CenteredWidgetMixin, copy_geometry_state


class MainLoginWindow(QWidget, CenteredWidgetMixin):
    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.setWindowTitle("LeEndoscope Login")
        self.restore_geometry_if_available()
        self._build_ui()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)

    def _build_ui(self):
        title = QLabel("LeEndoscope")
        title.setStyleSheet("font-size: 48px; font-weight: bold; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        login_btn = QPushButton("Login")
        login_btn.setFixedSize(200, 50)
        login_btn.clicked.connect(self.show_login)

        create_btn = QPushButton("Create Account")
        create_btn.setFixedSize(200, 50)
        create_btn.clicked.connect(self.show_create_account)

        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_row.addWidget(login_btn)
        button_row.addWidget(create_btn)

        inner = QVBoxLayout()
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title)
        inner.addLayout(button_row)

        self.setLayout(self.create_centered_wrapper(inner))

    def show_login(self):
        self.login_window = LoginWindow(parent=self, db=self.db)
        try:
            self.login_window.apply_geometry_from(self)
        except Exception:
            pass
        self.login_window.show()
        self.save_geometry_on_close()
        self.hide()

    def show_create_account(self):
        from frontend.auth.create_account_window import CreateAccountWindow
        self.create_window = CreateAccountWindow(parent=self, db=self.db)
        try:
            self.create_window.apply_geometry_from(self)
        except Exception:
            pass
        self.create_window.show()
        self.save_geometry_on_close()
        self.hide()


class LoginWindow(QWidget, CenteredWidgetMixin):
    login_successful = pyqtSignal()

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
        self.setWindowTitle("Login")
        self.restore_geometry_if_available()
        self._build_ui()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)

    def _build_ui(self):
        username_label = QLabel("Username:")
        password_label = QLabel("Password:")

        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")
        self.username.setFixedWidth(300)

        self.username_warning = QLabel("")
        self.username_warning.setStyleSheet("color: red; font-size: 12px;")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setFixedWidth(300)

        self.password_warning = QLabel("")
        self.password_warning.setStyleSheet("color: red; font-size: 12px;")

        login_button = AnimatedButton("Login")
        login_button.setFixedSize(150, 40)
        login_button.clicked.connect(self.attempt_login)

        cancel_button = AnimatedButton("Cancel")
        cancel_button.setFixedSize(150, 40)
        cancel_button.clicked.connect(self._back_to_main)

        form = QVBoxLayout()
        form.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.setSpacing(8)

        form.addWidget(make_centered_form_row(
            username_label, self.username, self.username_warning,
            label_w=110, input_w=225
        ))
        form.addWidget(make_centered_form_row(
            password_label, self.password, self.password_warning,
            label_w=110, input_w=225
        ))

        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_row.addWidget(login_button)
        button_row.addWidget(cancel_button)
        form.addLayout(button_row)

        recover_label = QLabel('Forgot your password? <a href="recover"><u>Recover your password</u></a>')
        recover_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        recover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        recover_label.setStyleSheet("QLabel a { color: #90d5ff; text-decoration: underline; }")
        recover_label.linkActivated.connect(self._show_recover_password)
        form.addWidget(recover_label)

        content = QWidget()
        content.setLayout(form)
        content.setFixedWidth(640)
        content.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        outer = QHBoxLayout()
        outer.addStretch()
        outer.addWidget(content)
        outer.addStretch()
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(outer)

    def attempt_login(self):
        user = self.username.text().strip()
        pwd = self.password.text()
        if not user:
            QMessageBox.warning(self, "Error", "Please enter a username.")
            return
        if self.db and self.db.verify_user(user, pwd):
            QMessageBox.information(self, "Success", f"Welcome, {user}!")
            self.login_successful.emit()

            from frontend.patient.patient_profile_window import PatientProfileWindow
            self.patient_window = PatientProfileWindow()
            self.transition_to(self.patient_window)
        else:
            QMessageBox.warning(self, "Login failed", "Invalid username or password.")
            self.password.clear()
            self.password.setFocus()

    def _back_to_main(self):
        self.save_geometry_on_close()
        if self.parent_window:
            self.parent_window.apply_geometry_from(self)
            self.parent_window.show()
        QTimer.singleShot(100, lambda: self.close())

    def _show_recover_password(self, href: str):
        try:
            from frontend.auth.recover_password_window import RecoverPasswordWindow
            self.recover_window = RecoverPasswordWindow(parent=self.parent_window, db=self.db)
            self.transition_to(self.recover_window)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to open password recovery window: {e}")
