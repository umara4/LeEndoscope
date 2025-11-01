# main.py
import sys
from PyQt6.QtWidgets import QApplication
from login import MainLoginWindow

def main():
    app = QApplication(sys.argv)

    # Start with the splash screen
    splash = MainLoginWindow()
    splash.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()