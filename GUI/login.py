import sys
import sqlite3
import hashlib
import secrets
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from video_window import VideoWindow


class MainLoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LeEndoscope Login")
        self.setFixedSize(800, 600)
        self.showMaximized()
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout()

        # Title
        title = QLabel("LeEndoscope")
        title.setStyleSheet("font-size: 48px; font-weight: bold; margin: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addRow(title)

        # Buttons
        login_btn = QPushButton("Login")
        login_btn.setFixedSize(200, 50)
        login_btn.clicked.connect(self.show_login)

        create_btn = QPushButton("Create Account")
        create_btn.setFixedSize(200, 50)
        create_btn.clicked.connect(self.show_create_account)

        # Center buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(login_btn)
        button_layout.addWidget(create_btn)
        button_layout.addStretch()

        layout.addRow(button_layout)
        self.setLayout(layout)

    def show_login(self):
        self.login_window = LoginWindow()
        def on_success():
            self.login_window.close()
            self.close()

            self.video_window = VideoWindow()
            self.video_window.show()
        self.login_window.login_successful.connect(on_success)
        self.login_window.show()

    def show_create_account(self):
        self.create_window = CreateAccountWindow()
        self.create_window.show()


class CreateAccountWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Create Account")
        self.setFixedSize(320, 200)
        self._build_ui()

    def _build_ui(self):
        self.email = QLineEdit()
        self.email.setPlaceholderText("Enter email")

        self.username = QLineEdit()
        self.username.setPlaceholderText("Choose username")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Choose password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("Confirm password")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.create_button = QPushButton("Create Account")
        self.create_button.clicked.connect(self.create_account)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.cancel_button)

        form = QFormLayout()
        form.addRow(QLabel("Email:"), self.email)
        form.addRow(QLabel("Username:"), self.username)
        form.addRow(QLabel("Password:"), self.password)
        form.addRow(QLabel("Confirm:"), self.confirm_password)
        form.addRow(buttons)

        self.setLayout(form)

    def create_account(self):
        if self.password.text() != self.confirm_password.text():
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return

        if _db.create_user(self.username.text(), self.password.text()):
            QMessageBox.information(self, "Success", "Account created successfully!")
            self.close()
        else:
            QMessageBox.warning(self, "Error", "Username already exists!")


class LoginWindow(QWidget):
    login_successful = pyqtSignal()   # ✅ define the signal

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.setFixedSize(320, 140)
        self._build_ui()

    def _build_ui(self):
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self.attempt_login)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setDefault(True)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(self.login_button)
        buttons.addWidget(self.cancel_button)

        form = QFormLayout()
        form.addRow(QLabel("Username:"), self.username)
        form.addRow(QLabel("Password:"), self.password)
        form.addRow(buttons)

        self.setLayout(form)

    
    

    def attempt_login(self):
        user = self.username.text().strip()
        pwd = self.password.text()

        if self._check_credentials(user, pwd):
            QMessageBox.information(self, "Success", f"Welcome, {user}!")
            self.login_successful.emit()   # ✅ notify main app
            self.close()                   # ✅ close login window
        else:
            QMessageBox.warning(self, "Login failed", "Invalid username or password.")
            self.password.clear()
            self.password.setFocus()


    @staticmethod
    def _check_credentials(user, pwd):
        return user == "admin" and pwd == "secret"  # replaced below with DB check


class UserDatabase:
    def __init__(self, db_path: str | Path = None):
        if db_path is None:
            db_path = Path(__file__).with_suffix(".db")
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pwd_hash TEXT NOT NULL)"
        )
        self._conn.commit()

    def _hash_password(self, password: str, salt_hex: str) -> str:
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return dk.hex()

    def create_user(self, username: str, password: str) -> bool:
        username = username.strip()
        if not username or not password:
            return False
        salt = secrets.token_hex(16)
        pwd_hash = self._hash_password(password, salt)
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO users (username, salt, pwd_hash) VALUES (?, ?, ?)",
                    (username, salt, pwd_hash),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def verify_user(self, username: str, password: str) -> bool:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT salt, pwd_hash FROM users WHERE username = ?",
            (username.strip(),),
        )
        row = cur.fetchone()
        if not row:
            return False
        salt, stored_hash = row
        return self._hash_password(password, salt) == stored_hash

    def close(self):
        self._conn.close()


# Initialize database and ensure a default admin exists
_db = UserDatabase()
_db.create_user("admin", "secret")


# Replace static check with DB check
def _db_check_credentials(user, pwd):
    return _db.verify_user(user, pwd)


LoginWindow._check_credentials = staticmethod(_db_check_credentials)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainLoginWindow()
    win.show()
    sys.exit(app.exec())