"""
ui_windows.py
All window classes and UI code with persistent geometry and centered layout.
"""
from __future__ import annotations
import re
from PyQt6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QGridLayout, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import QSize as QtSize

from db import UserDatabase
from geometry_store import save_geometry, load_geometry, save_start_size, get_start_size
from video_window import VideoWindow  # import at top


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
            # ensure maximum sizes are initialized for animation targets
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
        # quick pulse shrink then restore
        self._ensure_base()
        shrink_w = int(self._base_size.width() * 0.94)
        shrink_h = int(self._base_size.height() * 0.94)
        self._start_anim(shrink_w, shrink_h, duration=90, on_finished=lambda: self._start_anim(self._base_size.width(), self._base_size.height(), duration=120))
        super().mousePressEvent(ev)

    def _start_anim(self, target_w, target_h, duration=None, on_finished=None):
        duration = duration or self._duration
        # animate maximumWidth and maximumHeight together
        if self._anim:
            try:
                self._anim.stop()
            except Exception:
                pass
        # animate width
        anim_w = QPropertyAnimation(self, b"maximumWidth")
        anim_w.setDuration(duration)
        anim_w.setEndValue(target_w)
        anim_w.setEasingCurve(QEasingCurve.Type.InOutQuad)
        # animate height
        anim_h = QPropertyAnimation(self, b"maximumHeight")
        anim_h.setDuration(duration)
        anim_h.setEndValue(target_h)
        anim_h.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # keep a reference so they don't get GC'd
        self._anim = (anim_w, anim_h)

        def start_both():
            anim_w.start()
            anim_h.start()

        start_both()

        if on_finished:
            anim_h.finished.connect(on_finished)


def copy_geometry_state(src: QWidget, dst: QWidget):
    """Copy geometry and window state from src widget to dst widget.

    Used for windows that do not include the CenteredWidgetMixin (e.g. QMainWindow subclasses).
    """
    try:
        geo = src.geometry()
        dst.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
        dst.setWindowState(src.windowState())
    except Exception:
        # best-effort: ignore failures
        pass

def password_ok(pwd: str) -> bool:
    if len(pwd) < 10: return False
    if not re.search(r"[A-Z]", pwd): return False
    if not re.search(r"[a-z]", pwd): return False
    if not re.search(r"[0-9]", pwd): return False
    if not re.search(r"[!@#$%^&*]", pwd): return False
    return True

DB = UserDatabase()
DB.ensure_admin()

class CenteredWidgetMixin:
    def restore_geometry_if_available(self):
        g = load_geometry()
        screen = self.screen().availableGeometry()
        # If stored geometry looks like a fullscreen/near-fullscreen save (e.g. from
        # previous runs), ignore it so the app opens at a reasonable small default.
        if g:
            gx, gy, gw, gh = g
            try:
                if gw >= int(screen.width() * 0.95) or gh >= int(screen.height() * 0.95):
                    # treat as no geometry stored
                    g = None
            except Exception:
                pass
        if g:
            self.setGeometry(*g)
        else:
            # Default: use a much smaller start size so the app opens compact.
            start_size = get_start_size()
            if start_size:
                width, height = start_size
            else:
                # New default start size (width x height)
                width = 1000
                height = 700
                # Ensure defaults don't exceed screen
                width = min(width, screen.width())
                height = min(height, screen.height())
                save_start_size(width, height)
            x = (screen.width() - width) // 2
            y = (screen.height() - height) // 2
            self.setGeometry(x, y, width, height)

    def apply_geometry_from(self, other: QWidget):
        """Copy geometry and window state from another widget.

        This is used during transitions between windows so the new
        window appears in the same place and state as the previous one.
        """
        try:
            geo = other.geometry()
            self.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
            # preserve minimized/maximized state
            self.setWindowState(other.windowState())
        except Exception:
            # fallback to stored geometry
            self.restore_geometry_if_available()

    def save_geometry_on_close(self):
        geo = self.geometry()
        save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))

    def create_centered_wrapper(self, inner_layout):
        wrapper = QVBoxLayout()
        wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper.addLayout(inner_layout)
        return wrapper

    def resizeEvent(self, event):
        # Save geometry on resize
        geo = self.geometry()
        save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        QWidget.resizeEvent(self, event)

    def moveEvent(self, event):
        # Save geometry on move
        try:
            geo = self.geometry()
            save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        except Exception:
            pass
        QWidget.moveEvent(self, event)

    def changeEvent(self, event):
        # Save geometry when window state changes (minimize/maximize)
        if event.type() == QEvent.Type.WindowStateChange:
            try:
                geo = self.geometry()
                save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
            except Exception:
                pass
        QWidget.changeEvent(self, event)

    def transition_to(self, new_window: QWidget, delay_ms: int = 120):
        """Show new_window with copied geometry/state and close this window after a short delay.

        This helps make transitions look seamless instead of appearing like the app closed and reopened.
        """
        try:
            new_window.apply_geometry_from(self)
        except Exception:
            try:
                copy_geometry_state(self, new_window)
            except Exception:
                pass
        new_window.show()

        def _close_old():
            try:
                self.save_geometry_on_close()
            except Exception:
                pass
            try:
                self.close()
            except Exception:
                pass

        QTimer.singleShot(delay_ms, _close_old)

class MainLoginWindow(QWidget, CenteredWidgetMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LeEndoscope Login")
        # Do not overwrite saved start size with a large value; rely on the
        # mixin's restore logic which will use a small default when needed.
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
        from ui_windows import LoginWindow
        # Create new window and show it, keep main window hidden (not closed)
        self.login_window = LoginWindow(parent=self)
        try:
            self.login_window.apply_geometry_from(self)
        except Exception:
            pass
        self.login_window.show()
        self.save_geometry_on_close()
        self.hide()

    def show_create_account(self):
        from ui_windows import CreateAccountWindow
        self.create_window = CreateAccountWindow(parent=self)
        try:
            self.create_window.apply_geometry_from(self)
        except Exception:
            pass
        self.create_window.show()
        self.save_geometry_on_close()
        self.hide()

class LoginWindow(QWidget, CenteredWidgetMixin):
    login_successful = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()
        # Ensure window can be minimized
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.parent_window = parent
        self.setWindowTitle("Login")
        self.restore_geometry_if_available()
        self._build_ui()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)

    def _build_ui(self):
        # Build a compact two-row form where label and input are on same line
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

        # Buttons
        login_button = AnimatedButton("Login")
        login_button.setFixedSize(150, 40)
        login_button.clicked.connect(self.attempt_login)

        cancel_button = AnimatedButton("Cancel")
        cancel_button.setFixedSize(150, 40)
        cancel_button.clicked.connect(self._back_to_main)

        form = QVBoxLayout()
        form.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.setSpacing(8)

        # Helper to create a fixed-width row widget so label+input block is centered
        def make_row(label_widget: QLabel, input_widget: QLineEdit, warning: QLabel | None = None, label_w: int = 110, input_w: int = 225, warning_w: int = 160):
            # Build a 3-column row: left (label), center (input fixed width), right (warning).
            # The center column has fixed width and is centered by the left/right expanding columns.
            label_widget.setFixedWidth(label_w)
            input_widget.setFixedWidth(input_w)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignRight)

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

        form.addWidget(make_row(username_label, self.username, self.username_warning, input_w=225))
        form.addWidget(make_row(password_label, self.password, self.password_warning, input_w=225))

        # Buttons row
        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_row.addWidget(login_button)
        button_row.addWidget(cancel_button)
        form.addLayout(button_row)

        # Recover password link
        recover_label = QLabel('Forgot your password? <a href="recover"><u>Recover your password</u></a>')
        recover_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        recover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        recover_label.setStyleSheet("QLabel a { color: #90d5ff; text-decoration: underline; }")
        recover_label.linkActivated.connect(self._show_recover_password)
        form.addWidget(recover_label)

        # Wrap the form in a fixed-width content widget so it's centered as a block
        content = QWidget()
        content.setLayout(form)
        # widen the content area so right-side warnings fit without clipping
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
        if DB.verify_user(user, pwd):
            QMessageBox.information(self, "Success", f"Welcome, {user}!")
            self.login_successful.emit()  # optional signal for other listeners

            # After login we now show the patient profile manager instead of
            # the surgical video interface.  Import locally to avoid circular
            # dependencies and keep startup cost minimal.
            from patient_profile import PatientProfileWindow

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
        # close after small delay to let parent render
        QTimer.singleShot(100, lambda: self.close())

    def _show_recover_password(self, href: str):
        try:
            from ui_windows import RecoverPasswordWindow
            # keep a reference so the window isn't garbage-collected
            self.recover_window = RecoverPasswordWindow(parent=self.parent_window)
            self.transition_to(self.recover_window)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to open password recovery window: {e}")

class CreateAccountWindow(QWidget, CenteredWidgetMixin):
    def __init__(self, parent=None):
        super().__init__()
        # Ensure window can be minimized
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.parent_window = parent
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

        # ---- Title ----
        title = QLabel("Create Account")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title)
        main_layout.addSpacing(10)

        # ---- Form Layout (centered rows) ----
        # We'll build rows (HBox) and center each row so all inputs appear centered
        def row(label_widget: QLabel, input_widget: QLineEdit, warning: QLabel | None = None, label_w: int = 160, input_w: int = 225, warning_w: int = 160):
            # Build a 3-column row: left (label), center (input fixed width), right (warning).
            # The center column has fixed width and is centered by the left/right expanding columns.
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

        # Email
        email_label = QLabel("Email:")
        self.email_input = QLineEdit()
        self.email_input.setFixedWidth(300)
        self.email_warning = QLabel("")
        self.email_warning.setStyleSheet("color: red; font-size: 12px;")
        self.email_input.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        email_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.email_input.textChanged.connect(self._validate_email)
        main_layout.addWidget(row(email_label, self.email_input, self.email_warning))  # Consistent usage of row()

        # Username
        username_label = QLabel("Username:")
        self.username_input = QLineEdit()
        self.username_input.setFixedWidth(300)
        self.username_warning = QLabel("")
        self.username_warning.setStyleSheet("color: red; font-size: 12px;")
        self.username_input.textChanged.connect(self._validate_username)
        main_layout.addWidget(row(username_label, self.username_input, self.username_warning))  # Consistent usage of row()

        # (Phone removed — SMS/2FA disabled for now)

        # Password
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setFixedWidth(225)
        # Show actual letters, not dots while creating account
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.password_warning = QLabel("")
        self.password_warning.setStyleSheet("color: red; font-size: 12px;")
        self.password_warning.setWordWrap(True)
        self.password_input.textChanged.connect(self._validate_password)
        main_layout.addWidget(row(password_label, self.password_input, self.password_warning))

        # Confirm Password
        confirm_label = QLabel("Confirm Password:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setFixedWidth(225)
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.confirm_warning = QLabel("")
        self.confirm_warning.setStyleSheet("color: red; font-size: 12px;")
        self.confirm_warning.setWordWrap(True)
        self.confirm_input.textChanged.connect(self._validate_confirm)
        main_layout.addWidget(row(confirm_label, self.confirm_input, self.confirm_warning))

        # Password requirements below centered
        self.pwd_req_label = QLabel(
            "Password Requirements:\n"
            "• At least 8 characters\n"
            "• One uppercase letter\n"
            "• One number\n"
            "• One special character (!, @, #, etc.)"
        )
        self.pwd_req_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pwd_req_label.setStyleSheet("font-size: 12px; color: gray;")
        main_layout.addWidget(self.pwd_req_label)
        main_layout.addSpacing(15)

        # ---- Buttons ----
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

        # place the form inside a fixed-width content widget so rows are centered as a block
        content = QWidget()
        content.setLayout(main_layout)
        # widen the content area so right-side warnings fit without clipping
        content.setFixedWidth(640)
        content.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        outer = QHBoxLayout()
        outer.addStretch()
        outer.addWidget(content)
        outer.addStretch()
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(outer)

    # --- Validation Functions ---
    def _validate_username(self):
        username = self.username_input.text().strip()
        if DB.username_exists(username):
            self.username_input.setStyleSheet("background-color: #FFCCCC")
            self.username_warning.setText("Username already in use")
        else:
            self.username_input.setStyleSheet("")
            self.username_warning.setText("")

    def _validate_email(self):
        email = self.email_input.text().strip()
        if DB.email_exists(email):
            self.email_input.setStyleSheet("background-color: #FFCCCC")
            self.email_warning.setText("Email already in use!")
        else:
            self.email_input.setStyleSheet("")
            self.email_warning.setText("")

    def _validate_password(self):
        pwd = self.password_input.text()
        palette = self.password_input.palette()
        if password_ok(pwd):
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
            # clear password warning
            try:
                self.password_warning.setText("")
            except Exception:
                pass
        else:
            palette.setColor(QPalette.ColorRole.Base, QColor("#FFCCCC"))
            try:
                self.password_warning.setText("Password does not meet requirements")
            except Exception:
                pass
        self.password_input.setPalette(palette)
        self._validate_confirm()

    def _validate_confirm(self):
        pwd = self.password_input.text()
        confirm = self.confirm_input.text()
        palette = self.confirm_input.palette()
        if confirm == pwd or confirm == "":
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
            try:
                self.confirm_warning.setText("")
            except Exception:
                pass
        else:
            palette.setColor(QPalette.ColorRole.Base, QColor("#FFCCCC"))
            try:
                self.confirm_warning.setText("Passwords do not match")
            except Exception:
                pass
        self.confirm_input.setPalette(palette)

    # --- Create Account ---
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
        created = DB.create_user(username, pwd, email)
        if created:
            QMessageBox.information(self, "Success", "Account created successfully!")
            # show main login and close this window
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

    # --- Back to main login ---
    def _back_to_main(self):
        self.save_geometry_on_close()
        self.close()
        if self.parent_window:
            try:
                self.parent_window.apply_geometry_from(self)
            except Exception:
                pass
            self.parent_window.show()

class RecoverPasswordWindow(QWidget, CenteredWidgetMixin):
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.parent_window = parent
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
        """Show an error message when UI fails to build."""
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
        except Exception as e2:
            self.close()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("Recover Password")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title)
        main_layout.addSpacing(10)

        # Instructions
        instructions = QLabel("Enter your email or username to receive a password reset link")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 12px; color: #c0c0c0;")
        main_layout.addWidget(instructions)
        main_layout.addSpacing(15)

        # Email/Username input
        label = QLabel("Email or Username:")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter your email or username")
        self.input_field.setFixedWidth(300)

        self.input_warning = QLabel("")
        self.input_warning.setStyleSheet("color: red; font-size: 12px;")

        def make_row(label_widget: QLabel, input_widget: QLineEdit, warning: QLabel | None = None):
            label_widget.setFixedWidth(160)
            input_widget.setFixedWidth(225)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
            label_widget.setWordWrap(True)

            left = QWidget()
            left_l = QHBoxLayout()
            left_l.setContentsMargins(0, 0, 0, 0)
            left_l.addWidget(label_widget, 0, Qt.AlignmentFlag.AlignRight)
            left.setLayout(left_l)

            center = QWidget()
            center_l = QHBoxLayout()
            center_l.setContentsMargins(0, 0, 0, 0)
            center_l.addWidget(input_widget, 0, Qt.AlignmentFlag.AlignCenter)
            center.setLayout(center_l)
            center.setFixedWidth(225)

            right = QWidget()
            right_l = QHBoxLayout()
            right_l.setContentsMargins(0, 0, 0, 0)
            if warning:
                warning.setFixedWidth(160)
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

        main_layout.addWidget(make_row(label, self.input_field, self.input_warning))
        main_layout.addSpacing(20)

        # Buttons
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

        # Wrap in centered content widget
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
        """Handle the password recovery request."""
        try:
            input_value = self.input_field.text().strip()
            
            if not input_value:
                self.input_warning.setText("Please enter email or username")
                return

            # Try to find user by username or email
            username = None
            
            if input_value.count('@') > 0:  # Likely an email
                username = DB.get_user_by_email(input_value)
                if not username:
                    self.input_warning.setText("No account found with this email")
                    return
            else:  # Treat as username
                if DB.username_exists(input_value):
                    username = input_value
                else:
                    self.input_warning.setText("Username not found")
                    return

            # Generate reset token
            reset_token = DB.generate_reset_token(username)
            if not reset_token:
                self.input_warning.setText("Error generating reset token")
                return

            # Show the reset token window with the token
            from ui_windows import ResetPasswordWindow
            self.reset_window = ResetPasswordWindow(reset_token, parent=self.parent_window)
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
        else:
            pass


class ResetPasswordWindow(QWidget, CenteredWidgetMixin):
    """Window for resetting password using a valid reset token."""
    def __init__(self, reset_token: str, parent=None):
        super().__init__()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.reset_token = reset_token
        self.parent_window = parent
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
        """Show an error message when UI fails to build."""
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
        except Exception as e2:
            self.close()

    def closeEvent(self, event):
        self.save_geometry_on_close()
        super().closeEvent(event)
        # When closing the reset window, return to the login window
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
                main_login = MainLoginWindow()
                main_login.show()
            except Exception:
                pass

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("Reset Your Password")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title)
        main_layout.addSpacing(10)

        # Instructions
        instructions = QLabel("Enter your new password below")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setStyleSheet("font-size: 12px; color: #c0c0c0;")
        main_layout.addWidget(instructions)
        main_layout.addSpacing(15)

        def make_row(label_widget: QLabel, input_widget: QLineEdit, warning: QLabel | None = None, input_w: int = 225):
            label_widget.setFixedWidth(160)
            input_widget.setFixedWidth(input_w)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
            label_widget.setWordWrap(True)

            left = QWidget()
            left_l = QHBoxLayout()
            left_l.setContentsMargins(0, 0, 0, 0)
            left_l.addWidget(label_widget, 0, Qt.AlignmentFlag.AlignRight)
            left.setLayout(left_l)

            center = QWidget()
            center_l = QHBoxLayout()
            center_l.setContentsMargins(0, 0, 0, 0)
            center_l.addWidget(input_widget, 0, Qt.AlignmentFlag.AlignCenter)
            center.setLayout(center_l)
            center.setFixedWidth(input_w)

            right = QWidget()
            right_l = QHBoxLayout()
            right_l.setContentsMargins(0, 0, 0, 0)
            if warning:
                warning.setFixedWidth(160)
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

        # New Password
        password_label = QLabel("New Password:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter new password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.password_warning = QLabel("")
        self.password_warning.setStyleSheet("color: red; font-size: 12px;")
        self.password_warning.setWordWrap(True)
        self.password_input.textChanged.connect(self._validate_password)
        main_layout.addWidget(make_row(password_label, self.password_input, self.password_warning, input_w=225))

        # Confirm Password
        confirm_label = QLabel("Confirm Password:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm new password")
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.confirm_warning = QLabel("")
        self.confirm_warning.setStyleSheet("color: red; font-size: 12px;")
        self.confirm_warning.setWordWrap(True)
        self.confirm_input.textChanged.connect(self._validate_confirm)
        main_layout.addWidget(make_row(confirm_label, self.confirm_input, self.confirm_warning, input_w=225))

        # Password requirements
        self.pwd_req_label = QLabel(
            "Password Requirements:\n"
            "• At least 10 characters\n"
            "• One uppercase letter\n"
            "• One lowercase letter\n"
            "• One number\n"
            "• One special character (!, @, #, $, %, ^, &, *)"
        )
        self.pwd_req_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pwd_req_label.setStyleSheet("font-size: 12px; color: gray;")
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

        # Wrap in centered content widget
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
        pwd = self.password_input.text()
        palette = self.password_input.palette()
        if password_ok(pwd):
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
            self.password_warning.setText("")
        else:
            palette.setColor(QPalette.ColorRole.Base, QColor("#FFCCCC"))
            self.password_warning.setText("Password does not meet requirements")
        self.password_input.setPalette(palette)
        self._validate_confirm()

    def _validate_confirm(self):
        pwd = self.password_input.text()
        confirm = self.confirm_input.text()
        palette = self.confirm_input.palette()
        if confirm == pwd or confirm == "":
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
            self.confirm_warning.setText("")
        else:
            palette.setColor(QPalette.ColorRole.Base, QColor("#FFCCCC"))
            self.confirm_warning.setText("Passwords do not match")
        self.confirm_input.setPalette(palette)

    def reset_password(self):
        """Reset the password using the token."""
        if not password_ok(self.password_input.text()):
            QMessageBox.warning(self, "Error", "Password does not meet the requirements!")
            return
        if self.password_input.text() != self.confirm_input.text():
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return

        new_password = self.password_input.text()
        
        # Try to reset password with the token
        if DB.reset_password_with_token(self.reset_token, new_password):
            QMessageBox.information(self, "Success", "Password reset successfully! You can now log in with your new password.")
            # Go back to main login
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
        else:
            pass

    def _go_to_main_login(self):
        """Navigate back to the main login window."""
        self.save_geometry_on_close()
        main_login = MainLoginWindow()
        self.transition_to(main_login)
