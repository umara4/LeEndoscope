"""
Centralized dark theme stylesheets for the LeEndoscope application.
All windows share from these base styles. Individual windows may override
specific selectors as needed.
"""

# ---------------------------------------------------------------------------
# Global application stylesheet (applied once in main.py)
# ---------------------------------------------------------------------------
APP_STYLESHEET = """
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
"""

# ---------------------------------------------------------------------------
# Side panel (used in VideoWindow and ReconstructionWindow)
# ---------------------------------------------------------------------------
SIDE_PANEL_STYLESHEET = """
    QFrame {
        background-color: #606060;
        border: 0.5px solid #000000;
        border-radius: 8px;
    }
"""

# ---------------------------------------------------------------------------
# Patient Profile Window
# ---------------------------------------------------------------------------
PATIENT_WINDOW_STYLESHEET = """
    QMainWindow {
        background-color: #404040;
    }
    QWidget {
        background-color: #404040;
        color: #ffffff;
    }
    QLabel {
        color: #ffffff;
        background-color: transparent;
        border: none;
    }
    QLineEdit {
        background-color: #ffffff;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
        padding: 4px;
        color: #000000;
    }
    QLineEdit:focus {
        border: 2px solid #2196F3;
    }
    QTextEdit {
        background-color: #ffffff;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
        padding: 4px;
        color: #000000;
    }
    QTextEdit:focus {
        border: 2px solid #2196F3;
    }
    QComboBox {
        background-color: #ffffff;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
        padding: 4px;
        color: #000000;
    }
    QDateEdit {
        background-color: #ffffff;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
        padding: 4px;
        color: #000000;
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
"""

# ---------------------------------------------------------------------------
# Video Window
# ---------------------------------------------------------------------------
VIDEO_WINDOW_STYLESHEET = """
    QMainWindow {
        background-color: #404040;
    }
    QWidget {
        background-color: #404040;
        color: #ffffff;
    }
    QFrame {
        background-color: #606060;
        border-radius: 8px;
    }
    QPushButton {
        background-color: #c0c0c0;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
        padding: 8px;
        font-weight: bold;
        color: #000000;
    }
    QPushButton[objectName="play_pause_button"],
    QPushButton[objectName="back_button"],
    QPushButton[objectName="forward_button"] {
        font-size: 20px;
        font-weight: 900;
        padding: 12px;
    }
    QPushButton:hover {
        background-color: #d0d0d0;
    }
    QPushButton:pressed {
        background-color: #b0b0b0;
    }
    QLabel {
        color: #ffffff;
        background-color: transparent;
        border: none;
    }
    QSlider::groove:horizontal {
        border: 1px solid #999999;
        height: 8px;
        background: #606060;
        margin: 2px 0;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: #c0c0c0;
        border: 1px solid #5c5c5c;
        width: 18px;
        margin: -2px 0;
        border-radius: 9px;
    }
    QListWidget {
        background-color: #505050;
        border: 1px solid #606060;
        border-radius: 4px;
        color: #ffffff;
    }
    QListWidget::item {
        padding: 4px;
        border-bottom: 1px solid #606060;
    }
    QListWidget::item:selected {
        background-color: #708090;
    }
    QLineEdit {
        background-color: #ffffff;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
        padding: 4px;
        color: #000000;
    }
"""

# ---------------------------------------------------------------------------
# Serial Monitor Panel
# ---------------------------------------------------------------------------
SERIAL_MONITOR_STYLESHEET = """
    QFrame {
        background-color: #303030;
        border: 0.5px solid #000000;
        border-radius: 8px;
    }
    QLabel {
        font-weight: bold;
        color: #ffffff;
    }
    QTextEdit {
        background-color: #111111;
        color: #00ff66;
        border: 1px solid #2a2a2a;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 12px;
    }
"""

# ---------------------------------------------------------------------------
# Frame Browser Dialog
# ---------------------------------------------------------------------------
FRAME_BROWSER_STYLESHEET = """
    QDialog {
        background-color: #404040;
    }
    QWidget {
        background-color: #404040;
        color: #ffffff;
    }
    QFrame {
        background-color: #606060;
        border-radius: 8px;
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
    QLabel {
        color: #ffffff;
        background-color: transparent;
    }
    QTabWidget::pane {
        border: 1px solid #606060;
        background-color: #404040;
    }
    QTabWidget::tab-bar {
        alignment: left;
    }
    QTabBar::tab {
        background-color: #606060;
        color: #ffffff;
        padding: 8px 12px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background-color: #808080;
    }
    QTabBar::tab:hover {
        background-color: #707070;
    }
    QScrollArea {
        background-color: #404040;
        border: 1px solid #606060;
    }
    QCheckBox {
        color: #ffffff;
        spacing: 5px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 3px;
        border: 1px solid #a0a0a0;
        background-color: #ffffff;
    }
    QCheckBox::indicator:checked {
        background-color: #4CAF50;
        border-color: #45a049;
    }
"""

# ---------------------------------------------------------------------------
# Reconstruction Window
# ---------------------------------------------------------------------------
RECONSTRUCTION_STYLESHEET = """
    QMainWindow {
        background-color: #404040;
    }
    QWidget {
        background-color: #404040;
        color: #ffffff;
    }
"""

# ---------------------------------------------------------------------------
# Common widget styles (reusable snippets)
# ---------------------------------------------------------------------------
GREEN_BUTTON_STYLE = """
    QPushButton {
        background-color: #4CAF50;
        border: 1px solid #45a049;
        border-radius: 4px;
        padding: 10px;
        font-weight: bold;
        color: #ffffff;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QPushButton:pressed {
        background-color: #3d8b40;
    }
"""

BLUE_BUTTON_STYLE = """
    QPushButton {
        background-color: #2196F3;
        border: 1px solid #1976D2;
        border-radius: 4px;
        padding: 10px;
        font-weight: bold;
        color: #ffffff;
    }
    QPushButton:hover {
        background-color: #1976D2;
    }
    QPushButton:pressed {
        background-color: #1565C0;
    }
"""

NAV_BUTTON_STYLE = """
    QPushButton {
        background-color: #505050;
        border: 1px solid #404040;
        border-radius: 4px;
        padding: 8px 12px;
        font-weight: bold;
        color: #ffffff;
        font-size: 11px;
    }
    QPushButton:hover {
        background-color: #5a6f7d;
    }
    QPushButton:pressed {
        background-color: #708090;
    }
"""

PATIENT_LIST_STYLE = """
    QListWidget {
        background-color: #505050;
        border: 1px solid #606060;
        border-radius: 4px;
        color: #ffffff;
    }
    QListWidget::item {
        padding: 8px;
        border-bottom: 1px solid #606060;
    }
    QListWidget::item:selected {
        background-color: #708090;
    }
    QListWidget::item:hover {
        background-color: #5a6f7d;
    }
"""

COMBOBOX_DARK_DROPDOWN_STYLE = """
    QComboBox {
        background-color: #ffffff;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
        padding: 4px;
        color: #000000;
    }
    QComboBox::drop-down {
        border: none;
        background-color: #ffffff;
    }
    QComboBox::down-arrow {
        width: 12px;
        height: 12px;
    }
    QComboBox QAbstractItemView {
        background-color: #000000;
        color: #ffffff;
        selection-background-color: #333333;
        selection-color: #ffffff;
        border: 1px solid #a0a0a0;
        padding: 0px;
    }
    QComboBox QAbstractItemView::item {
        padding: 4px 0px;
    }
"""

TEXTBOX_STYLE = """
    QTextEdit {
        background-color: #ffffff;
        color: #000000;
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 5px;
        font-family: 'Segoe UI', Arial;
        font-size: 10px;
    }
"""

TERMINAL_STYLE = """
    QTextEdit {
        background-color: #404040;
        color: #ffffff;
        border: 1px solid #606060;
        border-radius: 4px;
        font-family: Consolas, monospace;
        font-size: 10px;
    }
"""

TERMINAL_LABEL_STYLE = """
    QLabel {
        background-color: #c0c0c0;
        color: #000000;
        font-weight: bold;
        padding: 8px;
        border: 1px solid #a0a0a0;
        border-radius: 4px;
    }
"""

VIEWER_LABEL_STYLE = """
    QLabel {
        background-color: #404040;
        border: 0.5px solid #000000;
        border-radius: 4px;
        color: #c0c0c0;
        font-size: 14px;
    }
"""
