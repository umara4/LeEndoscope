"""
Application entrypoint.
"""
import sys
from PyQt6.QtWidgets import QApplication
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

