import sys
import sqlite3
import hashlib
import secrets
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize
from PyQt6.QtGui import QColor, QPalette, QFont
from video_window import VideoWindow

# ------------------------ Global window memory ------------------------
_window_geometry = None  # Will store last geometry (x, y, width, height)
_start_size = None       # Store initial window size


def save_geometry(window):
    global _window_geometry
    _window_geometry = window.geometry()


def get_last_geometry():
    global _window_geometry
    return _window_geometry


def get_start_size():
    global _start_size
    return _start_size


# ------------------------ Database ------------------------
class UserDatabase:
    def __init__(self, db_path: str | Path = None):
        if db_path is None:
            db_path = Path(__file__).with_suffix(".db")
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                pwd_hash TEXT NOT NULL
            )
            """
        )
        # Add email column if missing
        cur = self._conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cur.fetchall()]
        if "email" not in columns:
            self._conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        self._conn.commit()

    def _hash_password(self, password: str, salt_hex: str) -> str:
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return dk.hex()

    def create_user(self, username: str, password: str, email: str = "") -> bool:
        username = username.strip()
        email = email.strip()
        if not username or not password:
            return False
        if self.username_exists(username) or self.email_exists(email):
            return False
        salt = secrets.token_hex(16)
        pwd_hash = self._hash_password(password, salt)
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO users (username, salt, pwd_hash, email) VALUES (?, ?, ?, ?)",
                    (username, salt, pwd_hash, email),
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

    def username_exists(self, username: str) -> bool:
        cur = self._conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username.strip(),))
        return cur.fetchone() is not None

    def email_exists(self, email: str) -> bool:
        cur = self._conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE email = ?", (email.strip(),))
        return cur.fetchone() is not None

    def close(self):
        self._conn.close()


# Initialize database and default admin
_db = UserDatabase()
_db.create_user("admin", "secret", "admin@example.com")


# ------------------------ Main Login Window ------------------------
class MainLoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LeEndoscope Login")

        screen = QApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 2 / 3)
        height = int(screen.height() * 2 / 3)
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        global _start_size
        _start_size = self.size()

        geo = get_last_geometry()
        if geo:
            self.setGeometry(geo)

        self._build_ui()
        self.show()

    def closeEvent(self, event):
        save_geometry(self)
        super().closeEvent(event)

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("LeEndoscope")
        title.setStyleSheet("font-size: 48px; font-weight: bold; margin: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Buttons layout
        button_layout = QHBoxLayout()
        login_btn = QPushButton("Login")
        login_btn.setFixedSize(200, 50)
        login_btn.clicked.connect(self.show_login)

        create_btn = QPushButton("Create Account")
        create_btn.setFixedSize(200, 50)
        create_btn.clicked.connect(self.show_create_account)

        button_layout.addStretch()
        button_layout.addWidget(login_btn)
        button_layout.addWidget(create_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def show_login(self):
        geo = self.geometry()
        self.close()
        self.login_window = LoginWindow(parent=self, geometry=geo)
        self.login_window.show()

    def show_create_account(self):
        geo = self.geometry()
        self.close()
        self.create_window = CreateAccountWindow(parent=self, geometry=geo)
        self.create_window.show()


# ------------------------ Login Window ------------------------
class LoginWindow(QWidget):
    login_successful = pyqtSignal()

    def __init__(self, parent=None, geometry=None):
        super().__init__()
        self.parent_window = parent
        self.setWindowTitle("Login")
        if geometry:
            self.setGeometry(geometry)
        self._build_ui()

    def closeEvent(self, event):
        save_geometry(self)
        super().closeEvent(event)

    def _build_ui(self):
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")
        self.username.setFixedWidth(300)

        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setFixedWidth(300)

        self.login_button = QPushButton("Login")
        self.login_button.setFixedSize(150, 40)
        self.login_button.clicked.connect(self.attempt_login)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedSize(150, 40)
        self.cancel_button.clicked.connect(self._back_to_main)

        buttons = QHBoxLayout()
        buttons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttons.addStretch()
        buttons.addWidget(self.login_button)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()

        form = QVBoxLayout()
        form.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addWidget(QLabel("Username:"))
        form.addWidget(self.username)
        form.addWidget(QLabel("Password:"))
        form.addWidget(self.password)
        form.addLayout(buttons)

        self.setLayout(form)

    def attempt_login(self):
        user = self.username.text().strip()
        pwd = self.password.text()
        if _db.verify_user(user, pwd):
            QMessageBox.information(self, "Success", f"Welcome, {user}!")
            self.login_successful.emit()
            self.close()
        else:
            QMessageBox.warning(self, "Login failed", "Invalid username or password.")
            self.password.clear()
            self.password.setFocus()

    def _back_to_main(self):
        save_geometry(self)
        self.close()
        if self.parent_window:
            self.parent_window.show()


# ------------------------ Create Account Window ------------------------
class CreateAccountWindow(QWidget):
    def __init__(self, parent=None, geometry=None):
        super().__init__()
        self.parent_window = parent
        self.setWindowTitle("Create Account")
        if geometry:
            self.setGeometry(geometry)
        self._build_ui()

    def closeEvent(self, event):
        save_geometry(self)
        super().closeEvent(event)

    def _build_ui(self):
        self.email = QLineEdit()
        self.email.setPlaceholderText("Enter email")
        self.email.setFixedWidth(300)
        self.email.textChanged.connect(self._validate_email)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Choose username")
        self.username.setFixedWidth(300)
        self.username.textChanged.connect(self._validate_username)

        self.username_warning = QLabel()
        self.username_warning.setStyleSheet("color:red")
        self.email_warning = QLabel()
        self.email_warning.setStyleSheet("color:red")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Choose password")
        self.password.setFixedWidth(300)
        self.password.textChanged.connect(self._validate_password)

        self.password_requirements = QLabel(
            "Password requirements:\n"
            "- At least 10 characters\n"
            "- Uppercase letters\n"
            "- Lowercase letters\n"
            "- Numbers\n"
            "- Special symbols (!@#$%^&*)"
        )
        self.password_requirements.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.password_requirements.setWordWrap(True)
        self.password_requirements.setFixedWidth(300)

        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("Confirm password")
        self.confirm_password.setFixedWidth(300)
        self.confirm_password.textChanged.connect(self._validate_confirm)

        self.create_button = QPushButton("Create Account")
        self.create_button.setFixedSize(150, 40)
        self.create_button.clicked.connect(self.create_account)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedSize(150, 40)
        self.cancel_button.clicked.connect(self._back_to_main)

        # Forgot password section centered
        self.forgot_label = QLabel("Forgot your password?")
        self.forgot_button = QPushButton("Create new password")
        font = QFont()
        font.setUnderline(True)
        self.forgot_button.setFont(font)
        self.forgot_button.setFlat(True)
        self.forgot_button.clicked.connect(self.show_recover_window)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.create_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()

        forgot_layout = QHBoxLayout()
        forgot_layout.addStretch()
        forgot_layout.addWidget(self.forgot_label)
        forgot_layout.addWidget(self.forgot_button)
        forgot_layout.addStretch()

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("Email:"))
        layout.addWidget(self.email)
        layout.addWidget(self.email_warning)
        layout.addWidget(QLabel("Username:"))
        layout.addWidget(self.username)
        layout.addWidget(self.username_warning)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self.password)
        layout.addWidget(self.password_requirements)
        layout.addWidget(QLabel("Confirm:"))
        layout.addWidget(self.confirm_password)
        layout.addLayout(buttons_layout)
        layout.addLayout(forgot_layout)

        self.setLayout(layout)

    # ------------------- Validation -------------------
    def _validate_username(self):
        if _db.username_exists(self.username.text()):
            self.username.setStyleSheet("background-color: #FFCCCC")
            self.username_warning.setText("Username already used")
        else:
            self.username.setStyleSheet("")
            self.username_warning.setText("")

    def _validate_email(self):
        if _db.email_exists(self.email.text()):
            self.email.setStyleSheet("background-color: #FFCCCC")
            self.email_warning.setText("Email already used")
        else:
            self.email.setStyleSheet("")
            self.email_warning.setText("")

    def _validate_password(self):
        pwd = self.password.text()
        palette = self.password.palette()
        if self._password_ok(pwd):
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        else:
            palette.setColor(QPalette.ColorRole.Base, QColor("#FFCCCC"))
        self.password.setPalette(palette)
        self._validate_confirm()

    def _validate_confirm(self):
        pwd = self.password.text()
        confirm = self.confirm_password.text()
        palette = self.confirm_password.palette()
        if confirm == pwd or confirm == "":
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        else:
            palette.setColor(QPalette.ColorRole.Base, QColor("#FFCCCC"))
        self.confirm_password.setPalette(palette)

    @staticmethod
    def _password_ok(pwd: str) -> bool:
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

    # ------------------- Actions -------------------
    def create_account(self):
        if not self._password_ok(self.password.text()):
            QMessageBox.warning(self, "Error", "Password does not meet the requirements!")
            return
        if self.password.text() != self.confirm_password.text():
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return
        if _db.create_user(self.username.text(), self.password.text(), self.email.text()):
            QMessageBox.information(self, "Success", "Account created successfully!")
            self._back_to_main()
        else:
            QMessageBox.warning(self, "Error", "Username or email already exists!")

    def _back_to_main(self):
        save_geometry(self)
        self.close()
        if self.parent_window:
            self.parent_window.show()

    def show_recover_window(self):
        save_geometry(self)
        self.close()
        self.recover_window = RecoverPasswordWindow(parent=self.parent_window)
        self.recover_window.show()


# ------------------------ Recover Password Placeholder ------------------------
class RecoverPasswordWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent_window = parent
        geo = get_last_geometry()
        if geo:
            self.setGeometry(geo)
        self.setWindowTitle("Recover Password")
        self._build_ui()
        self.show()

    def closeEvent(self, event):
        save_geometry(self)
        super().closeEvent(event)

    def _build_ui(self):
        self.back_button = QPushButton("Back to Main Login")
        self.back_button.clicked.connect(self._back_to_main)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("Recover Password Placeholder"))
        layout.addWidget(self.back_button)
        self.setLayout(layout)

    def _back_to_main(self):
        save_geometry(self)
        self.close()
        if self.parent_window:
            self.parent_window.show()


# ------------------------ Run App ------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_login = MainLoginWindow()
    main_login.show()
    sys.exit(app.exec())