"""
Patient form widget (right panel) with scrollable sections.

Split from patient_profile.py PatientFormWidget.
Uses shared theme styles.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLabel,
    QLineEdit, QTextEdit, QListWidget, QScrollArea, QDateEdit, QComboBox, QWidget,
)
from PyQt6.QtCore import QDate

from shared.theme import (
    SIDE_PANEL_STYLE, NAV_BUTTON_STYLE,
    SCROLL_AREA_STYLE, STYLE_SECTION_FRAME, STYLE_SECTION_TITLE,
    STYLE_SEPARATOR, STYLE_BOLD_LABEL,
)


class PatientFormWidget(QFrame):
    """Right side form for editing patient information with scrollable sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SIDE_PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Navigation buttons at top
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(10, 10, 10, 5)
        nav_layout.setSpacing(5)

        self.section_buttons = {}
        section_names = ["Basic Info", "Address", "Emergency", "Medical", "Tumor", "Surgery", "Notes", "Media"]

        for section_name in section_names:
            btn = QPushButton(section_name)
            btn.setStyleSheet(NAV_BUTTON_STYLE)
            btn.clicked.connect(lambda checked, name=section_name: self._scroll_to_section(name))
            nav_layout.addWidget(btn)
            self.section_buttons[section_name] = btn

        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLL_AREA_STYLE)

        # Content widget that holds all sections
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)

        # Store section widgets for scrolling
        self.sections = {}

        # Basic Information Section
        self.basic_info_widget = self._create_collapsible_section("Basic Info", self._create_basic_info_fields())
        content_layout.addWidget(self.basic_info_widget)
        self.sections["Basic Info"] = self.basic_info_widget

        # Address Section
        self.address_widget = self._create_collapsible_section("Address", self._create_address_fields())
        content_layout.addWidget(self.address_widget)
        self.sections["Address"] = self.address_widget

        # Emergency Contact Section
        self.emergency_widget = self._create_collapsible_section("Emergency Contact", self._create_emergency_fields())
        content_layout.addWidget(self.emergency_widget)
        self.sections["Emergency"] = self.emergency_widget

        # Medical History Section
        self.medical_widget = self._create_collapsible_section("Medical History", self._create_medical_fields())
        content_layout.addWidget(self.medical_widget)
        self.sections["Medical"] = self.medical_widget

        # Tumor Information Section
        self.tumor_widget = self._create_collapsible_section("Tumor Information", self._create_tumor_fields())
        content_layout.addWidget(self.tumor_widget)
        self.sections["Tumor"] = self.tumor_widget

        # Surgery Information Section
        self.surgery_widget = self._create_collapsible_section("Surgery Information", self._create_surgery_fields())
        content_layout.addWidget(self.surgery_widget)
        self.sections["Surgery"] = self.surgery_widget

        # Pre/Post Surgery Notes Section
        self.notes_widget = self._create_collapsible_section("Surgery Notes", self._create_notes_fields())
        content_layout.addWidget(self.notes_widget)
        self.sections["Notes"] = self.notes_widget

        # Media Section
        self.media_widget = self._create_collapsible_section("Media", self._create_media_fields())
        content_layout.addWidget(self.media_widget)
        self.sections["Media"] = self.media_widget

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll, 1)

        self.scroll_area = scroll

    def _scroll_to_section(self, section_name: str):
        """Scroll to a specific section."""
        if section_name in self.sections:
            widget = self.sections[section_name]
            self.scroll_area.ensureWidgetVisible(widget, 50, 50)

    def _create_collapsible_section(self, title: str, fields_layout) -> QFrame:
        """Create a collapsible section frame with title and fields."""
        section = QFrame()
        section.setStyleSheet(STYLE_SECTION_FRAME)

        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(10, 10, 10, 10)
        section_layout.setSpacing(5)

        # Section title
        title_label = QLabel(title)
        title_label.setStyleSheet(STYLE_SECTION_TITLE)
        section_layout.addWidget(title_label)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(STYLE_SEPARATOR)
        section_layout.addWidget(line)

        # Content
        section_layout.addLayout(fields_layout)

        return section

    def _create_basic_info_fields(self) -> QFormLayout:
        """Create basic information form fields."""
        layout = QFormLayout()

        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("First name")
        layout.addRow("First Name:", self.first_name_input)

        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Last name")
        layout.addRow("Last Name:", self.last_name_input)

        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDate(QDate.currentDate())
        layout.addRow("Date of Birth:", self.dob_input)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Not specified", "Male", "Female", "Other"])
        layout.addRow("Gender:", self.gender_combo)

        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Phone number")
        layout.addRow("Contact Number:", self.contact_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email address")
        layout.addRow("Email:", self.email_input)

        return layout

    def _create_address_fields(self) -> QFormLayout:
        """Create address form fields."""
        layout = QFormLayout()

        self.street_input = QLineEdit()
        self.street_input.setPlaceholderText("Street address")
        layout.addRow("Street Address:", self.street_input)

        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("City")
        layout.addRow("City:", self.city_input)

        self.state_input = QLineEdit()
        self.state_input.setPlaceholderText("State/Province")
        layout.addRow("State/Province:", self.state_input)

        self.postal_input = QLineEdit()
        self.postal_input.setPlaceholderText("Postal code")
        layout.addRow("Postal Code:", self.postal_input)

        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText("Country")
        layout.addRow("Country:", self.country_input)

        return layout

    def _create_emergency_fields(self) -> QFormLayout:
        """Create emergency contact form fields."""
        layout = QFormLayout()

        self.emergency_name_input = QLineEdit()
        self.emergency_name_input.setPlaceholderText("Full name")
        layout.addRow("Contact Name:", self.emergency_name_input)

        self.emergency_phone_input = QLineEdit()
        self.emergency_phone_input.setPlaceholderText("Phone number")
        layout.addRow("Contact Phone:", self.emergency_phone_input)

        self.emergency_relationship_input = QLineEdit()
        self.emergency_relationship_input.setPlaceholderText("e.g., Spouse, Parent, Child")
        layout.addRow("Relationship:", self.emergency_relationship_input)

        return layout

    def _create_medical_fields(self) -> QFormLayout:
        """Create medical history form fields."""
        layout = QFormLayout()

        self.medical_history_text = QTextEdit()
        self.medical_history_text.setPlaceholderText("Medical history and conditions...")
        self.medical_history_text.setMaximumHeight(80)
        layout.addRow("Medical History:", self.medical_history_text)

        self.allergies_text = QTextEdit()
        self.allergies_text.setPlaceholderText("Known allergies...")
        self.allergies_text.setMaximumHeight(80)
        layout.addRow("Allergies:", self.allergies_text)

        self.medications_text = QTextEdit()
        self.medications_text.setPlaceholderText("Current medications...")
        self.medications_text.setMaximumHeight(80)
        layout.addRow("Current Medications:", self.medications_text)

        return layout

    def _create_tumor_fields(self) -> QFormLayout:
        """Create tumor information form fields."""
        layout = QFormLayout()

        self.tumor_location_input = QLineEdit()
        self.tumor_location_input.setPlaceholderText("e.g., Left lung, Colon, Brain")
        layout.addRow("Tumor Location:", self.tumor_location_input)

        self.tumor_size_input = QLineEdit()
        self.tumor_size_input.setPlaceholderText("e.g., 5cm x 3cm")
        layout.addRow("Tumor Size:", self.tumor_size_input)

        self.tumor_type_input = QLineEdit()
        self.tumor_type_input.setPlaceholderText("e.g., Adenocarcinoma, Squamous cell")
        layout.addRow("Tumor Type:", self.tumor_type_input)

        self.tumor_stage_combo = QComboBox()
        self.tumor_stage_combo.addItems(["Not specified", "Stage I", "Stage II", "Stage III", "Stage IV"])
        layout.addRow("Tumor Stage:", self.tumor_stage_combo)

        self.tumor_description_text = QTextEdit()
        self.tumor_description_text.setPlaceholderText("Detailed tumor description...")
        self.tumor_description_text.setMaximumHeight(80)
        layout.addRow("Description:", self.tumor_description_text)

        return layout

    def _create_surgery_fields(self) -> QFormLayout:
        """Create surgery information form fields."""
        layout = QFormLayout()

        self.surgery_date_input = QDateEdit()
        self.surgery_date_input.setCalendarPopup(True)
        self.surgery_date_input.setDate(QDate.currentDate())
        layout.addRow("Surgery Date:", self.surgery_date_input)

        self.surgery_type_input = QLineEdit()
        self.surgery_type_input.setPlaceholderText("e.g., Endoscopic resection, Lobectomy")
        layout.addRow("Surgery Type:", self.surgery_type_input)

        self.surgeon_input = QLineEdit()
        self.surgeon_input.setPlaceholderText("Surgeon name")
        layout.addRow("Surgeon Name:", self.surgeon_input)

        self.surgery_notes_text = QTextEdit()
        self.surgery_notes_text.setPlaceholderText("Surgery notes and observations...")
        self.surgery_notes_text.setMaximumHeight(80)
        layout.addRow("Surgery Notes:", self.surgery_notes_text)

        return layout

    def _create_notes_fields(self) -> QFormLayout:
        """Create pre/post surgery notes form fields."""
        layout = QFormLayout()

        self.pre_surgery_text = QTextEdit()
        self.pre_surgery_text.setPlaceholderText("Pre-surgery preparation notes, patient status, etc...")
        self.pre_surgery_text.setMaximumHeight(80)
        layout.addRow("Pre-Surgery Notes:", self.pre_surgery_text)

        self.post_surgery_text = QTextEdit()
        self.post_surgery_text.setPlaceholderText("Post-surgery recovery notes, observations, etc...")
        self.post_surgery_text.setMaximumHeight(80)
        layout.addRow("Post-Surgery Notes:", self.post_surgery_text)

        return layout

    def _create_media_fields(self) -> QVBoxLayout:
        """Create media management fields."""
        layout = QVBoxLayout()

        # Session name
        session_label = QLabel("Session Name:")
        session_label.setStyleSheet(STYLE_BOLD_LABEL)
        layout.addWidget(session_label)

        self.session_name_input = QLineEdit()
        self.session_name_input.setPlaceholderText("Enter a session name...")
        layout.addWidget(self.session_name_input)

        # Videos section
        videos_label = QLabel("Associated Videos:")
        videos_label.setStyleSheet(STYLE_BOLD_LABEL + " margin-top: 20px;")
        layout.addWidget(videos_label)

        self.videos_list = QListWidget()
        layout.addWidget(self.videos_list)

        videos_btn_layout = QHBoxLayout()
        self.add_video_btn = QPushButton("Add Video")
        self.remove_video_btn = QPushButton("Remove Selected")
        videos_btn_layout.addWidget(self.add_video_btn)
        videos_btn_layout.addWidget(self.remove_video_btn)
        layout.addLayout(videos_btn_layout)

        # IMU Data section
        images_label = QLabel("IMU Data:")
        images_label.setStyleSheet(STYLE_BOLD_LABEL + " margin-top: 20px;")
        layout.addWidget(images_label)

        self.images_list = QListWidget()
        layout.addWidget(self.images_list)

        images_btn_layout = QHBoxLayout()
        self.add_image_btn = QPushButton("Add IMU Data")
        self.remove_image_btn = QPushButton("Remove Selected")
        images_btn_layout.addWidget(self.add_image_btn)
        images_btn_layout.addWidget(self.remove_image_btn)
        layout.addLayout(images_btn_layout)

        return layout
