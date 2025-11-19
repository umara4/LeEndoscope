"""
Application entrypoint.
"""
import sys
from PyQt6.QtWidgets import QApplication
from ui_windows import MainLoginWindow

def main():
    app = QApplication(sys.argv)
    main_login = MainLoginWindow()
    main_login.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
