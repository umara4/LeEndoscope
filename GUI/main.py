"""
Application entrypoint.
"""
import sys
from PyQt6.QtWidgets import QApplication
from ui_windows import MainLoginWindow

def main():
    app = QApplication(sys.argv)
    
    # Set global dark theme
    app.setStyleSheet("""
        QWidget {
            background-color: #404040;
            color: #ffffff;
        }
        QPushButton {
            background-color: #c0c0c0;
            border: 1px solid #a0a0a0;
            border-radius: 4px;
            padding: 8px;
            font-weight: bold;
            color: #000000;
        }
        QPushButton:hover {
            background-color: #d0d0d0;
        }
        QPushButton:pressed {
            background-color: #b0b0b0;
        }
        QFrame {
            background-color: #606060;
            border-radius: 8px;
        }
        QLabel {
            color: #ffffff;
            background-color: transparent;
            font-size: 16px;
            border: none;
        }
        QLineEdit {
            background-color: #ffffff;
            border: 1px solid #a0a0a0;
            border-radius: 4px;
            padding: 4px;
            color: #000000;
        }
    """)
    
    main_login = MainLoginWindow()
    main_login.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
