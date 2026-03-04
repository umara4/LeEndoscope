"""
Application entrypoint.
"""
import sys
from PyQt6.QtWidgets import QApplication

from shared.theme import APP_STYLESHEET
from backend.user_db import UserDatabase
from frontend.auth.login_window import MainLoginWindow


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    db = UserDatabase()
    main_login = MainLoginWindow(db=db)
    main_login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
