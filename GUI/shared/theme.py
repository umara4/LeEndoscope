"""
Centralized dark medical theme for the LeEndoscope application.

All colors, typography, and spacing are defined as Python constants,
then composed into stylesheet strings. Individual windows should NOT
define inline styles -- everything references these constants or the
stylesheets defined here.
"""

# ===================================================================
# SECTION 1: Design Tokens
# ===================================================================

# 1a. Color Palette — Background Hierarchy (dark-to-light layered surfaces)
BG_BASE = "#1E1E2E"
BG_SURFACE = "#2B2B3C"
BG_ELEVATED = "#353548"
BG_INPUT = "#3A3A4E"
BG_OVERLAY = "#404055"

# 1b. Accent Colors (Medical Blue)
ACCENT_PRIMARY = "#1976D2"
ACCENT_DARK = "#0D47A1"
ACCENT_LIGHT = "#42A5F5"
ACCENT_SURFACE = "#1A3A5C"

# 1c. Text Colors
TEXT_PRIMARY = "#E0E0E0"
TEXT_SECONDARY = "#A0A0B0"
TEXT_MUTED = "#6C6C80"
TEXT_ON_ACCENT = "#FFFFFF"
TEXT_ON_INPUT = "#E0E0E0"

# 1d. Semantic Colors
SUCCESS = "#4CAF50"
SUCCESS_HOVER = "#43A047"
SUCCESS_PRESSED = "#388E3C"
ERROR = "#EF5350"
ERROR_BG = "#5C2B2B"
WARNING = "#FFA726"
RECORDING_RED = "#E53935"

# 1e. Border & Divider Colors
BORDER_DEFAULT = "#4A4A60"
BORDER_FOCUS = ACCENT_PRIMARY
BORDER_SUBTLE = "#3A3A4E"
BORDER_PANEL = "#2B2B3C"

# 1f. Special Purpose
TERMINAL_BG = "#0D0D14"
TERMINAL_TEXT = "#00E676"
TERMINAL_BORDER = "#1A1A28"
SLIDER_GROOVE = "#3A3A4E"
SLIDER_HANDLE = ACCENT_PRIMARY
SLIDER_HANDLE_BORDER = ACCENT_DARK
SEGMENT_HIGHLIGHT = "#4CAF50"
VIEWER_BG = BG_BASE
PYVISTA_BG = BG_BASE

# 1g. Button Default (non-accent standard buttons)
BTN_DEFAULT_BG = "#3A3A4E"
BTN_DEFAULT_HOVER = "#4A4A60"
BTN_DEFAULT_PRESSED = "#2B2B3C"
BTN_DEFAULT_TEXT = TEXT_PRIMARY
BTN_DISABLED_BG = "#2B2B3C"
BTN_DISABLED_TEXT = "#6C6C80"

# 1h. Typography
FONT_FAMILY = '"Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif'
FONT_MONO = 'Consolas, "Courier New", monospace'
FONT_SIZE_HERO = "36px"
FONT_SIZE_H1 = "22px"
FONT_SIZE_H2 = "16px"
FONT_SIZE_BODY = "13px"
FONT_SIZE_SMALL = "11px"
FONT_SIZE_MONO = "12px"

# 1i. Spacing
SPACE_XS = "2px"
SPACE_SM = "4px"
SPACE_MD = "8px"
SPACE_LG = "12px"
SPACE_XL = "16px"
SPACE_XXL = "24px"
RADIUS_SM = "4px"
RADIUS_MD = "6px"
RADIUS_LG = "8px"


# ===================================================================
# SECTION 2: Application-Level Stylesheet (applied once in main.py)
# ===================================================================

APP_STYLESHEET = f"""
    /* --- Global defaults --- */
    * {{
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_BODY};
    }}

    QWidget {{
        background-color: {BG_BASE};
        color: {TEXT_PRIMARY};
    }}

    /* --- Buttons --- */
    QPushButton {{
        background-color: {BTN_DEFAULT_BG};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_MD};
        font-weight: bold;
        color: {BTN_DEFAULT_TEXT};
    }}
    QPushButton:hover {{
        background-color: {BTN_DEFAULT_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {BTN_DEFAULT_PRESSED};
    }}
    QPushButton:disabled {{
        background-color: {BTN_DISABLED_BG};
        color: {BTN_DISABLED_TEXT};
        border: 1px solid {BORDER_SUBTLE};
    }}

    /* --- Frames --- */
    QFrame {{
        background-color: {BG_SURFACE};
        border-radius: {RADIUS_LG};
    }}

    /* --- Labels --- */
    QLabel {{
        color: {TEXT_PRIMARY};
        background-color: transparent;
        font-size: {FONT_SIZE_BODY};
        border: none;
    }}

    /* --- Line edits --- */
    QLineEdit {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_SM};
        color: {TEXT_ON_INPUT};
    }}
    QLineEdit:focus {{
        border: 2px solid {BORDER_FOCUS};
    }}

    /* --- Text edits --- */
    QTextEdit {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_SM};
        color: {TEXT_ON_INPUT};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_BODY};
    }}
    QTextEdit:focus {{
        border: 2px solid {BORDER_FOCUS};
    }}

    /* --- Combo boxes --- */
    QComboBox {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_SM};
        color: {TEXT_ON_INPUT};
    }}
    QComboBox::drop-down {{
        border: none;
        background-color: {BG_INPUT};
    }}
    QComboBox::down-arrow {{
        width: 12px;
        height: 12px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        selection-background-color: {ACCENT_SURFACE};
        selection-color: {TEXT_ON_ACCENT};
        border: 1px solid {BORDER_DEFAULT};
        padding: 0px;
    }}
    QComboBox QAbstractItemView::item {{
        padding: {SPACE_SM} 0px;
    }}

    /* --- Date edits --- */
    QDateEdit {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_SM};
        color: {TEXT_ON_INPUT};
    }}
    QDateEdit:focus {{
        border: 2px solid {BORDER_FOCUS};
    }}

    /* --- Time edits --- */
    QTimeEdit {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_SM};
        color: {TEXT_ON_INPUT};
    }}
    QTimeEdit:focus {{
        border: 2px solid {BORDER_FOCUS};
    }}

    /* --- Sliders --- */
    QSlider::groove:horizontal {{
        border: 1px solid {BORDER_DEFAULT};
        height: 8px;
        background: {SLIDER_GROOVE};
        margin: {SPACE_XS} 0;
        border-radius: {RADIUS_SM};
    }}
    QSlider::handle:horizontal {{
        background: {SLIDER_HANDLE};
        border: 1px solid {SLIDER_HANDLE_BORDER};
        width: 18px;
        margin: -2px 0;
        border-radius: 9px;
    }}

    /* --- List widgets --- */
    QListWidget {{
        background-color: {BG_ELEVATED};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        color: {TEXT_PRIMARY};
    }}
    QListWidget::item {{
        padding: {SPACE_MD};
        border-bottom: 1px solid {BORDER_SUBTLE};
    }}
    QListWidget::item:selected {{
        background-color: {ACCENT_SURFACE};
    }}
    QListWidget::item:hover {{
        background-color: {BG_OVERLAY};
    }}

    /* --- Scroll bars --- */
    QScrollBar:vertical {{
        background-color: {BG_SURFACE};
        width: 12px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {BORDER_DEFAULT};
        border-radius: {RADIUS_MD};
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {ACCENT_LIGHT};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
    }}

    QScrollBar:horizontal {{
        background-color: {BG_SURFACE};
        height: 12px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {BORDER_DEFAULT};
        border-radius: {RADIUS_MD};
        min-width: 20px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {ACCENT_LIGHT};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: none;
    }}

    /* --- Tab widgets --- */
    QTabWidget::pane {{
        border: 1px solid {BORDER_DEFAULT};
        background-color: {BG_BASE};
    }}
    QTabWidget::tab-bar {{
        alignment: left;
    }}
    QTabBar::tab {{
        background-color: {BG_SURFACE};
        color: {TEXT_PRIMARY};
        padding: {SPACE_MD} {SPACE_LG};
        margin-right: {SPACE_XS};
        border-top-left-radius: {RADIUS_SM};
        border-top-right-radius: {RADIUS_SM};
    }}
    QTabBar::tab:selected {{
        background-color: {ACCENT_PRIMARY};
        color: {TEXT_ON_ACCENT};
    }}
    QTabBar::tab:hover {{
        background-color: {BG_ELEVATED};
    }}

    /* --- Check boxes --- */
    QCheckBox {{
        color: {TEXT_PRIMARY};
        spacing: 5px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 3px;
        border: 1px solid {BORDER_DEFAULT};
        background-color: {BG_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background-color: {ACCENT_PRIMARY};
        border-color: {ACCENT_DARK};
    }}

    /* --- Progress bars --- */
    QProgressBar {{
        background-color: {BG_ELEVATED};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        text-align: center;
        color: {TEXT_PRIMARY};
    }}
    QProgressBar::chunk {{
        background-color: {ACCENT_PRIMARY};
        border-radius: {RADIUS_SM};
    }}

    /* --- Scroll areas --- */
    QScrollArea {{
        background-color: {BG_BASE};
        border: none;
    }}

    /* --- Menus --- */
    QMenu {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_DEFAULT};
    }}
    QMenu::item:selected {{
        background-color: {ACCENT_SURFACE};
    }}

    /* --- Message boxes --- */
    QMessageBox {{
        background-color: {BG_BASE};
    }}
    QMessageBox QLabel {{
        color: {TEXT_PRIMARY};
    }}

    /* --- Tool tips --- */
    QToolTip {{
        background-color: {BG_OVERLAY};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_DEFAULT};
        padding: {SPACE_SM};
    }}
"""


# ===================================================================
# SECTION 3: Component-Specific Styles
# ===================================================================

# Side panel (QFrame with distinct border)
SIDE_PANEL_STYLE = f"""
    QFrame {{
        background-color: {BG_SURFACE};
        border: 1px solid {BORDER_PANEL};
        border-radius: {RADIUS_LG};
    }}
"""

# Serial monitor panel (dark terminal theme)
SERIAL_MONITOR_STYLE = f"""
    QFrame {{
        background-color: {TERMINAL_BG};
        border: 1px solid {TERMINAL_BORDER};
        border-radius: {RADIUS_LG};
    }}
    QLabel {{
        font-weight: bold;
        color: {TEXT_PRIMARY};
    }}
    QTextEdit {{
        background-color: {TERMINAL_BG};
        color: {TERMINAL_TEXT};
        border: 1px solid {TERMINAL_BORDER};
        font-family: {FONT_MONO};
        font-size: {FONT_SIZE_MONO};
    }}
"""

# Terminal display (monospace green text)
TERMINAL_DISPLAY_STYLE = f"""
    QTextEdit {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        font-family: {FONT_MONO};
        font-size: {FONT_SIZE_SMALL};
    }}
"""

# Terminal header label
TERMINAL_LABEL_STYLE = f"""
    QLabel {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        font-weight: bold;
        padding: {SPACE_MD};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
    }}
"""

# Video viewer label
VIEWER_LABEL_STYLE = f"""
    QLabel {{
        background-color: {VIEWER_BG};
        border: 1px solid {BORDER_PANEL};
        border-radius: {RADIUS_SM};
        color: {TEXT_SECONDARY};
        font-size: 14px;
    }}
"""

# Patient form text boxes (medical data entry)
# NOTE: Covered by APP_STYLESHEET QTextEdit rules; kept only if needed for override

# Navigation buttons (patient form section navigation)
NAV_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {BG_ELEVATED};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_MD} {SPACE_LG};
        font-weight: bold;
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_SMALL};
    }}
    QPushButton:hover {{
        background-color: {ACCENT_SURFACE};
        color: {TEXT_ON_ACCENT};
    }}
    QPushButton:pressed {{
        background-color: {ACCENT_DARK};
        color: {TEXT_ON_ACCENT};
    }}
"""

# Scroll area with custom scrollbar (patient form)
SCROLL_AREA_STYLE = f"""
    QScrollArea {{
        background-color: {BG_BASE};
        border: none;
    }}
    QScrollBar:vertical {{
        background-color: {BG_SURFACE};
        width: 12px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {BORDER_DEFAULT};
        border-radius: {RADIUS_MD};
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {ACCENT_LIGHT};
    }}
"""

# Slider base style (for VideoViewer reset)
SLIDER_BASE_STYLE = f"""
    QSlider::groove:horizontal {{
        border: 1px solid {BORDER_DEFAULT};
        height: 8px;
        background: {SLIDER_GROOVE};
        margin: {SPACE_XS} 0;
        border-radius: {RADIUS_SM};
    }}
    QSlider::handle:horizontal {{
        background: {SLIDER_HANDLE};
        border: 1px solid {SLIDER_HANDLE_BORDER};
        width: 18px;
        margin: -2px 0;
        border-radius: 9px;
    }}
"""


# ===================================================================
# SECTION 4: Semantic Button Styles
# ===================================================================

# Accent button (primary actions — blue)
ACCENT_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {ACCENT_PRIMARY};
        border: 1px solid {ACCENT_DARK};
        border-radius: {RADIUS_SM};
        padding: 10px;
        font-weight: bold;
        color: {TEXT_ON_ACCENT};
    }}
    QPushButton:hover {{
        background-color: {ACCENT_LIGHT};
    }}
    QPushButton:pressed {{
        background-color: {ACCENT_DARK};
    }}
"""

# Success button (positive actions — green)
SUCCESS_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {SUCCESS};
        border: 1px solid {SUCCESS_HOVER};
        border-radius: {RADIUS_SM};
        padding: 10px;
        font-weight: bold;
        color: {TEXT_ON_ACCENT};
        font-size: {FONT_SIZE_BODY};
    }}
    QPushButton:hover {{
        background-color: {SUCCESS_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {SUCCESS_PRESSED};
    }}
"""


# ===================================================================
# SECTION 5: Inline-Style Constants (for setStyleSheet on individual widgets)
# ===================================================================

STYLE_WARNING_LABEL = f"color: {ERROR}; font-size: {FONT_SIZE_SMALL};"
STYLE_REQUIREMENTS_LABEL = f"color: {TEXT_MUTED}; font-size: {FONT_SIZE_SMALL};"
STYLE_INSTRUCTIONS_LABEL = f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL};"
STYLE_PAGE_TITLE = f"font-size: {FONT_SIZE_H1}; font-weight: bold;"
STYLE_APP_TITLE = f"font-size: {FONT_SIZE_HERO}; font-weight: bold; color: {TEXT_ON_ACCENT};"
STYLE_SECTION_TITLE = f"color: {TEXT_PRIMARY}; background-color: transparent; font-weight: bold; font-size: {FONT_SIZE_H2};"
STYLE_BOLD_LABEL = f"font-weight: bold; color: {TEXT_PRIMARY};"
STYLE_HYPERLINK = f"QLabel a {{ color: {ACCENT_LIGHT}; text-decoration: underline; }}"
STYLE_SEPARATOR = f"color: {BORDER_SUBTLE};"
STYLE_ERROR_INPUT_BG = f"background-color: {ERROR_BG};"
STYLE_SECTION_FRAME = f"QFrame {{ background-color: transparent; border: none; border-radius: 0px; }}"

# Reconstruction viewer container
STYLE_VIEWER_CONTAINER = f"""
    QWidget {{
        background-color: {BG_BASE};
        border: 1px solid {BORDER_PANEL};
        border-radius: {RADIUS_LG};
    }}
"""

# Reconstruction overlay buttons
STYLE_ZOOM_BTN = (
    f"background: rgba(30,30,46,0.85); border-radius: 16px; "
    f"font-weight: bold; font-size: 18px; color: {TEXT_PRIMARY};"
)

STYLE_MANIP_BTN = f"""
    QPushButton {{
        background-color: {BG_BASE};
        color: {TEXT_SECONDARY};
        border: none;
        border-radius: {RADIUS_MD};
    }}
    QPushButton:hover {{
        background-color: {BG_ELEVATED};
    }}
    QPushButton:pressed {{
        background-color: {BG_SURFACE};
    }}
"""

STYLE_MANIP_HOME_BTN = f"""
    QPushButton {{
        background-color: {BG_BASE};
        color: {TEXT_SECONDARY};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_MD};
        font-size: 10px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {BG_ELEVATED};
    }}
    QPushButton:pressed {{
        background-color: {BG_SURFACE};
    }}
"""

STYLE_MANIP_FRAME = f"#manipulator {{ background-color: {BG_BASE}; border-radius: {RADIUS_LG}; }}"

# Playback control buttons (<<, play/pause, >>)
STYLE_PLAYBACK_BTN = f"""
    QPushButton {{
        font-size: 18px;
        font-weight: 900;
        padding: {SPACE_LG};
    }}
"""

# Navigation bar button styles (AppShell top tab bar)
NAV_BAR_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: {SPACE_SM} {SPACE_MD};
        font-weight: bold;
        font-size: {FONT_SIZE_BODY};
    }}
    QPushButton:hover {{
        background-color: {BTN_DEFAULT_HOVER};
    }}
"""

NAV_BAR_ACTIVE_STYLE = f"""
    QPushButton {{
        background-color: {ACCENT_PRIMARY};
        color: {TEXT_ON_ACCENT};
        border: 1px solid {ACCENT_DARK};
        border-radius: {RADIUS_SM};
        padding: {SPACE_SM} {SPACE_MD};
        font-weight: bold;
        font-size: {FONT_SIZE_BODY};
    }}
"""

