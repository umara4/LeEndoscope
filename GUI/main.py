"""
Application entrypoint.
"""
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# Enable shared OpenGL contexts for QWebEngineView (required for WebGL).
# QtWebEngineWidgets must also be imported before QApplication is created.
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
try:
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFont

from shared.theme import APP_STYLESHEET
from backend.user_db import UserDatabase
from frontend.auth.login_window import MainLoginWindow

def main():
    app = QApplication(sys.argv)

    # Set default application font
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    app.setStyleSheet(APP_STYLESHEET)

    db = UserDatabase()
    main_login = MainLoginWindow(db=db)
    main_login.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

