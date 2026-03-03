"""
patient_profile.py
Patient profile management interface with patient list on left and profile/media view on right.
Similar layout to the Surgical Imaging Interface with left sidebar containing patient tabs.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem, QMessageBox, QFileDialog,
    QScrollArea, QFormLayout, QDateEdit, QComboBox, QSplitter, QTabWidget
)
from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QPixmap, QIcon

from geometry_store import load_geometry, save_geometry
from video_window import VideoWindow

# Path to store patient data
PATIENTS_DB_PATH = Path(__file__).parent / "patients_data.json"


class PatientProfile:
    """Data model for patient information."""
    
    def __init__(self, patient_id: str = None, **kwargs):
        self.patient_id = patient_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Basic Information
        self.first_name = kwargs.get('first_name', '')
        self.last_name = kwargs.get('last_name', '')
        self.date_of_birth = kwargs.get('date_of_birth', '')  # YYYY-MM-DD format
        self.gender = kwargs.get('gender', 'Not specified')
        self.contact_number = kwargs.get('contact_number', '')
        self.email = kwargs.get('email', '')
        
        # Address Information
        self.street_address = kwargs.get('street_address', '')
        self.city = kwargs.get('city', '')
        self.state_province = kwargs.get('state_province', '')
        self.postal_code = kwargs.get('postal_code', '')
        self.country = kwargs.get('country', '')
        
        # Emergency Contact
        self.emergency_contact_name = kwargs.get('emergency_contact_name', '')
        self.emergency_contact_phone = kwargs.get('emergency_contact_phone', '')
        self.emergency_contact_relationship = kwargs.get('emergency_contact_relationship', '')
        
        # Medical Information
        self.medical_history = kwargs.get('medical_history', '')
        self.allergies = kwargs.get('allergies', '')
        self.current_medications = kwargs.get('current_medications', '')
        
        # Tumor Information
        self.tumor_location = kwargs.get('tumor_location', '')
        self.tumor_size = kwargs.get('tumor_size', '')
        self.tumor_type = kwargs.get('tumor_type', '')
        self.tumor_stage = kwargs.get('tumor_stage', '')
        self.tumor_description = kwargs.get('tumor_description', '')
        
        # Surgery Information
        self.surgery_date = kwargs.get('surgery_date', '')  # YYYY-MM-DD format
        self.surgery_type = kwargs.get('surgery_type', '')
        self.surgeon_name = kwargs.get('surgeon_name', '')
        self.surgery_notes = kwargs.get('surgery_notes', '')
        
        # Pre/Post Surgery Notes
        self.pre_surgery_notes = kwargs.get('pre_surgery_notes', '')
        self.post_surgery_notes = kwargs.get('post_surgery_notes', '')
        
        # Media References
        self.associated_videos = kwargs.get('associated_videos', [])  # List of video file paths
        self.associated_images = kwargs.get('associated_images', [])  # List of image file paths
        
        # Timestamps
        self.created_date = kwargs.get('created_date', datetime.now().isoformat())
        self.last_modified = kwargs.get('last_modified', datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert patient profile to dictionary for JSON serialization."""
        return {
            'patient_id': self.patient_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'date_of_birth': self.date_of_birth,
            'gender': self.gender,
            'contact_number': self.contact_number,
            'email': self.email,
            'street_address': self.street_address,
            'city': self.city,
            'state_province': self.state_province,
            'postal_code': self.postal_code,
            'country': self.country,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'emergency_contact_relationship': self.emergency_contact_relationship,
            'medical_history': self.medical_history,
            'allergies': self.allergies,
            'current_medications': self.current_medications,
            'tumor_location': self.tumor_location,
            'tumor_size': self.tumor_size,
            'tumor_type': self.tumor_type,
            'tumor_stage': self.tumor_stage,
            'tumor_description': self.tumor_description,
            'surgery_date': self.surgery_date,
            'surgery_type': self.surgery_type,
            'surgeon_name': self.surgeon_name,
            'surgery_notes': self.surgery_notes,
            'pre_surgery_notes': self.pre_surgery_notes,
            'post_surgery_notes': self.post_surgery_notes,
            'associated_videos': self.associated_videos,
            'associated_images': self.associated_images,
            'created_date': self.created_date,
            'last_modified': self.last_modified,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PatientProfile':
        """Create PatientProfile from dictionary."""
        return PatientProfile(**data)
    
    def get_display_name(self) -> str:
        """Get patient display name."""
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else f"Patient {self.patient_id[:8]}"


class PatientDatabase:
    """Manages patient profile persistence."""
    
    def __init__(self, db_path: Path = PATIENTS_DB_PATH):
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Ensure database file exists."""
        if not self.db_path.exists():
            self.db_path.write_text(json.dumps({}))
    
    def save_patient(self, patient: PatientProfile):
        """Save patient profile to database."""
        patients = self._load_all()
        patient.last_modified = datetime.now().isoformat()
        patients[patient.patient_id] = patient.to_dict()
        self._write_all(patients)
    
    def load_patient(self, patient_id: str) -> Optional[PatientProfile]:
        """Load patient profile by ID."""
        patients = self._load_all()
        if patient_id in patients:
            return PatientProfile.from_dict(patients[patient_id])
        return None
    
    def load_all_patients(self) -> List[PatientProfile]:
        """Load all patient profiles."""
        patients = self._load_all()
        return [PatientProfile.from_dict(data) for data in patients.values()]
    
    def delete_patient(self, patient_id: str):
        """Delete patient profile."""
        patients = self._load_all()
        if patient_id in patients:
            del patients[patient_id]
            self._write_all(patients)
    
    def _load_all(self) -> Dict[str, Dict]:
        """Load all patient data from file."""
        try:
            if self.db_path.exists():
                data = self.db_path.read_text()
                return json.loads(data) if data.strip() else {}
        except Exception:
            pass
        return {}
    
    def _write_all(self, patients: Dict[str, Dict]):
        """Write all patient data to file."""
        try:
            self.db_path.write_text(json.dumps(patients, indent=2))
        except Exception as e:
            print(f"Error writing patient database: {e}")


class PatientListWidget(QFrame):
    """Left sidebar with patient list and new patient button."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #606060;
                border: 0.5px solid #000000;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # New Patient Button
        self.new_patient_btn = QPushButton("+ New Patient")
        self.new_patient_btn.setStyleSheet("""
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
        """)
        layout.addWidget(self.new_patient_btn)
        
        # Patient List
        self.patient_list = QListWidget()
        self.patient_list.setStyleSheet("""
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
        """)
        layout.addWidget(self.patient_list)
        
        # Add stretch to push button to bottom
        layout.addStretch()
        
        # Go to Surgery Button at bottom
        self.go_to_surgery_btn = QPushButton("Go to Surgery")
        self.go_to_surgery_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
        """)
        layout.addWidget(self.go_to_surgery_btn)


class PatientFormWidget(QFrame):
    """Right side form for editing patient information with scrollable sections."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #606060;
                border: 0.5px solid #000000;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Navigation buttons at top
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(10, 10, 10, 5)
        nav_layout.setSpacing(5)
        
        nav_button_style = """
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
        
        self.section_buttons = {}
        section_names = ["Basic Info", "Address", "Emergency", "Medical", "Tumor", "Surgery", "Notes", "Media"]
        
        for section_name in section_names:
            btn = QPushButton(section_name)
            btn.setStyleSheet(nav_button_style)
            btn.clicked.connect(lambda checked, name=section_name: self._scroll_to_section(name))
            nav_layout.addWidget(btn)
            self.section_buttons[section_name] = btn
        
        nav_layout.addStretch()
        layout.addLayout(nav_layout)
        
        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #404040;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #505050;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #708090;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #7a8fa5;
            }
        """)
        
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
        
        # Save Button at bottom
        self.save_btn = QPushButton("Save Patient")
        self.save_btn.setStyleSheet("""
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
        """)
        layout.addWidget(self.save_btn)
        
        self.scroll_area = scroll
    
    def _scroll_to_section(self, section_name: str):
        """Scroll to a specific section."""
        if section_name in self.sections:
            widget = self.sections[section_name]
            self.scroll_area.ensureWidgetVisible(widget, 50, 50)
    
    def _create_collapsible_section(self, title: str, fields_layout) -> QFrame:
        """Create a collapsible section frame with title and fields."""
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
        """)
        
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(10, 10, 10, 10)
        section_layout.setSpacing(5)
        
        # Section title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: transparent;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        section_layout.addWidget(title_label)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #606060;")
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
        self.gender_combo.setStyleSheet("""
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
        """)
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
        
        # Text box styling
        textbox_style = """
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
        
        self.medical_history_text = QTextEdit()
        self.medical_history_text.setPlaceholderText("Medical history and conditions...")
        self.medical_history_text.setMaximumHeight(80)
        self.medical_history_text.setStyleSheet(textbox_style)
        layout.addRow("Medical History:", self.medical_history_text)
        
        self.allergies_text = QTextEdit()
        self.allergies_text.setPlaceholderText("Known allergies...")
        self.allergies_text.setMaximumHeight(80)
        self.allergies_text.setStyleSheet(textbox_style)
        layout.addRow("Allergies:", self.allergies_text)
        
        self.medications_text = QTextEdit()
        self.medications_text.setPlaceholderText("Current medications...")
        self.medications_text.setMaximumHeight(80)
        self.medications_text.setStyleSheet(textbox_style)
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
        textbox_style = """
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
        self.tumor_description_text.setStyleSheet(textbox_style)
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
        textbox_style = """
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
        self.surgery_notes_text.setStyleSheet(textbox_style)
        layout.addRow("Surgery Notes:", self.surgery_notes_text)
        
        return layout
    
    def _create_notes_fields(self) -> QFormLayout:
        """Create pre/post surgery notes form fields."""
        layout = QFormLayout()
        
        # Text box styling
        textbox_style = """
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
        
        self.pre_surgery_text = QTextEdit()
        self.pre_surgery_text.setPlaceholderText("Pre-surgery preparation notes, patient status, etc...")
        self.pre_surgery_text.setMaximumHeight(80)
        self.pre_surgery_text.setStyleSheet(textbox_style)
        layout.addRow("Pre-Surgery Notes:", self.pre_surgery_text)
        
        self.post_surgery_text = QTextEdit()
        self.post_surgery_text.setPlaceholderText("Post-surgery recovery notes, observations, etc...")
        self.post_surgery_text.setMaximumHeight(80)
        self.post_surgery_text.setStyleSheet(textbox_style)
        layout.addRow("Post-Surgery Notes:", self.post_surgery_text)
        
        return layout
    
    def _create_media_fields(self) -> QVBoxLayout:
        """Create media management fields."""
        layout = QVBoxLayout()
        
        # Videos section
        videos_label = QLabel("Associated Videos:")
        videos_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(videos_label)
        
        self.videos_list = QListWidget()
        layout.addWidget(self.videos_list)
        
        videos_btn_layout = QHBoxLayout()
        self.add_video_btn = QPushButton("Add Video")
        self.remove_video_btn = QPushButton("Remove Selected")
        videos_btn_layout.addWidget(self.add_video_btn)
        videos_btn_layout.addWidget(self.remove_video_btn)
        layout.addLayout(videos_btn_layout)
        
        # Images section
        images_label = QLabel("Associated Images:")
        images_label.setStyleSheet("font-weight: bold; color: #ffffff; margin-top: 20px;")
        layout.addWidget(images_label)
        
        self.images_list = QListWidget()
        layout.addWidget(self.images_list)
        
        images_btn_layout = QHBoxLayout()
        self.add_image_btn = QPushButton("Add Image")
        self.remove_image_btn = QPushButton("Remove Selected")
        images_btn_layout.addWidget(self.add_image_btn)
        images_btn_layout.addWidget(self.remove_image_btn)
        layout.addLayout(images_btn_layout)
        
        return layout


class PatientProfileWindow(QMainWindow):
    """Main patient profile management window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Patient Profile Manager")
        self.resize(1400, 800)
        
        # Set dark theme
        self.setStyleSheet("""
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
        """)
        
        # Restore geometry if available
        g = load_geometry()
        if g:
            try:
                self.setGeometry(*g)
            except Exception:
                pass
        
        # Initialize database
        self.db = PatientDatabase()
        self.current_patient: Optional[PatientProfile] = None
        
        # Create main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Content area with patient list and form
        content_layout = QHBoxLayout()
        
        # Left panel - Patient list
        self.patient_list_widget = PatientListWidget()
        self.patient_list_widget.new_patient_btn.clicked.connect(self.new_patient)
        self.patient_list_widget.go_to_surgery_btn.clicked.connect(self.go_to_surgery)
        self.patient_list_widget.patient_list.itemSelectionChanged.connect(self.on_patient_selected)
        content_layout.addWidget(self.patient_list_widget, 1)
        
        # Right panel - Patient form
        self.patient_form_widget = PatientFormWidget()
        self.patient_form_widget.save_btn.clicked.connect(self.save_current_patient)
        self.patient_form_widget.add_video_btn.clicked.connect(self.add_video)
        self.patient_form_widget.remove_video_btn.clicked.connect(self.remove_video)
        self.patient_form_widget.add_image_btn.clicked.connect(self.add_image)
        self.patient_form_widget.remove_image_btn.clicked.connect(self.remove_image)
        content_layout.addWidget(self.patient_form_widget, 2)
        
        main_layout.addLayout(content_layout, 1)
        
        
        self.setCentralWidget(central_widget)
        
        # Load all patients
        self.refresh_patient_list()
    
    def refresh_patient_list(self):
        """Refresh the patient list display."""
        self.patient_list_widget.patient_list.clear()
        patients = self.db.load_all_patients()
        
        for patient in patients:
            item = QListWidgetItem(patient.get_display_name())
            item.setData(Qt.ItemDataRole.UserRole, patient.patient_id)
            self.patient_list_widget.patient_list.addItem(item)
    
    def new_patient(self):
        """Create a new patient profile."""
        self.current_patient = PatientProfile()
        self.clear_form()
        self.patient_list_widget.patient_list.clearSelection()
        QMessageBox.information(self, "New Patient", "New patient profile created. Fill in the information and save.")
    
    def on_patient_selected(self):
        """Handle patient selection from list."""
        item = self.patient_list_widget.patient_list.currentItem()
        if item:
            patient_id = item.data(Qt.ItemDataRole.UserRole)
            self.current_patient = self.db.load_patient(patient_id)
            if self.current_patient:
                self.load_patient_into_form(self.current_patient)
    
    def load_patient_into_form(self, patient: PatientProfile):
        """Load patient data into the form."""
        # Basic Info
        self.patient_form_widget.first_name_input.setText(patient.first_name)
        self.patient_form_widget.last_name_input.setText(patient.last_name)
        self.patient_form_widget.dob_input.setDate(QDate.fromString(patient.date_of_birth, "yyyy-MM-dd") if patient.date_of_birth else QDate.currentDate())
        self.patient_form_widget.gender_combo.setCurrentText(patient.gender)
        self.patient_form_widget.contact_input.setText(patient.contact_number)
        self.patient_form_widget.email_input.setText(patient.email)
        
        # Address
        self.patient_form_widget.street_input.setText(patient.street_address)
        self.patient_form_widget.city_input.setText(patient.city)
        self.patient_form_widget.state_input.setText(patient.state_province)
        self.patient_form_widget.postal_input.setText(patient.postal_code)
        self.patient_form_widget.country_input.setText(patient.country)
        
        # Emergency Contact
        self.patient_form_widget.emergency_name_input.setText(patient.emergency_contact_name)
        self.patient_form_widget.emergency_phone_input.setText(patient.emergency_contact_phone)
        self.patient_form_widget.emergency_relationship_input.setText(patient.emergency_contact_relationship)
        
        # Medical History
        self.patient_form_widget.medical_history_text.setText(patient.medical_history)
        self.patient_form_widget.allergies_text.setText(patient.allergies)
        self.patient_form_widget.medications_text.setText(patient.current_medications)
        
        # Tumor Information
        self.patient_form_widget.tumor_location_input.setText(patient.tumor_location)
        self.patient_form_widget.tumor_size_input.setText(patient.tumor_size)
        self.patient_form_widget.tumor_type_input.setText(patient.tumor_type)
        self.patient_form_widget.tumor_stage_combo.setCurrentText(patient.tumor_stage)
        self.patient_form_widget.tumor_description_text.setText(patient.tumor_description)
        
        # Surgery Information
        self.patient_form_widget.surgery_date_input.setDate(QDate.fromString(patient.surgery_date, "yyyy-MM-dd") if patient.surgery_date else QDate.currentDate())
        self.patient_form_widget.surgery_type_input.setText(patient.surgery_type)
        self.patient_form_widget.surgeon_input.setText(patient.surgeon_name)
        self.patient_form_widget.surgery_notes_text.setText(patient.surgery_notes)
        
        # Pre/Post Surgery Notes
        self.patient_form_widget.pre_surgery_text.setText(patient.pre_surgery_notes)
        self.patient_form_widget.post_surgery_text.setText(patient.post_surgery_notes)
        
        # Media
        self.patient_form_widget.videos_list.clear()
        for video in patient.associated_videos:
            self.patient_form_widget.videos_list.addItem(video)
        
        self.patient_form_widget.images_list.clear()
        for image in patient.associated_images:
            self.patient_form_widget.images_list.addItem(image)
    
    def clear_form(self):
        """Clear all form fields."""
        self.patient_form_widget.first_name_input.clear()
        self.patient_form_widget.last_name_input.clear()
        self.patient_form_widget.dob_input.setDate(QDate.currentDate())
        self.patient_form_widget.gender_combo.setCurrentIndex(0)
        self.patient_form_widget.contact_input.clear()
        self.patient_form_widget.email_input.clear()
        
        self.patient_form_widget.street_input.clear()
        self.patient_form_widget.city_input.clear()
        self.patient_form_widget.state_input.clear()
        self.patient_form_widget.postal_input.clear()
        self.patient_form_widget.country_input.clear()
        
        self.patient_form_widget.emergency_name_input.clear()
        self.patient_form_widget.emergency_phone_input.clear()
        self.patient_form_widget.emergency_relationship_input.clear()
        
        self.patient_form_widget.medical_history_text.clear()
        self.patient_form_widget.allergies_text.clear()
        self.patient_form_widget.medications_text.clear()
        
        self.patient_form_widget.tumor_location_input.clear()
        self.patient_form_widget.tumor_size_input.clear()
        self.patient_form_widget.tumor_type_input.clear()
        self.patient_form_widget.tumor_stage_combo.setCurrentIndex(0)
        self.patient_form_widget.tumor_description_text.clear()
        
        self.patient_form_widget.surgery_date_input.setDate(QDate.currentDate())
        self.patient_form_widget.surgery_type_input.clear()
        self.patient_form_widget.surgeon_input.clear()
        self.patient_form_widget.surgery_notes_text.clear()
        
        self.patient_form_widget.pre_surgery_text.clear()
        self.patient_form_widget.post_surgery_text.clear()
        
        self.patient_form_widget.videos_list.clear()
        self.patient_form_widget.images_list.clear()
    
    def save_current_patient(self):
        """Save current patient data from form."""
        if not self.current_patient:
            QMessageBox.warning(self, "Error", "No patient selected or created.")
            return
        
        # Update patient data from form
        self.current_patient.first_name = self.patient_form_widget.first_name_input.text()
        self.current_patient.last_name = self.patient_form_widget.last_name_input.text()
        self.current_patient.date_of_birth = self.patient_form_widget.dob_input.date().toString("yyyy-MM-dd")
        self.current_patient.gender = self.patient_form_widget.gender_combo.currentText()
        self.current_patient.contact_number = self.patient_form_widget.contact_input.text()
        self.current_patient.email = self.patient_form_widget.email_input.text()
        
        self.current_patient.street_address = self.patient_form_widget.street_input.text()
        self.current_patient.city = self.patient_form_widget.city_input.text()
        self.current_patient.state_province = self.patient_form_widget.state_input.text()
        self.current_patient.postal_code = self.patient_form_widget.postal_input.text()
        self.current_patient.country = self.patient_form_widget.country_input.text()
        
        self.current_patient.emergency_contact_name = self.patient_form_widget.emergency_name_input.text()
        self.current_patient.emergency_contact_phone = self.patient_form_widget.emergency_phone_input.text()
        self.current_patient.emergency_contact_relationship = self.patient_form_widget.emergency_relationship_input.text()
        
        self.current_patient.medical_history = self.patient_form_widget.medical_history_text.toPlainText()
        self.current_patient.allergies = self.patient_form_widget.allergies_text.toPlainText()
        self.current_patient.current_medications = self.patient_form_widget.medications_text.toPlainText()
        
        self.current_patient.tumor_location = self.patient_form_widget.tumor_location_input.text()
        self.current_patient.tumor_size = self.patient_form_widget.tumor_size_input.text()
        self.current_patient.tumor_type = self.patient_form_widget.tumor_type_input.text()
        self.current_patient.tumor_stage = self.patient_form_widget.tumor_stage_combo.currentText()
        self.current_patient.tumor_description = self.patient_form_widget.tumor_description_text.toPlainText()
        
        self.current_patient.surgery_date = self.patient_form_widget.surgery_date_input.date().toString("yyyy-MM-dd")
        self.current_patient.surgery_type = self.patient_form_widget.surgery_type_input.text()
        self.current_patient.surgeon_name = self.patient_form_widget.surgeon_input.text()
        self.current_patient.surgery_notes = self.patient_form_widget.surgery_notes_text.toPlainText()
        
        self.current_patient.pre_surgery_notes = self.patient_form_widget.pre_surgery_text.toPlainText()
        self.current_patient.post_surgery_notes = self.patient_form_widget.post_surgery_text.toPlainText()
        
        # Save to database
        self.db.save_patient(self.current_patient)
        
        # Refresh patient list
        self.refresh_patient_list()
        
        QMessageBox.information(self, "Success", "Patient profile saved successfully.")
    
    def add_video(self):
        """Add video file to patient profile."""
        if not self.current_patient:
            QMessageBox.warning(self, "Error", "No patient selected or created.")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        
        if file_path:
            self.patient_form_widget.videos_list.addItem(file_path)
            if file_path not in self.current_patient.associated_videos:
                self.current_patient.associated_videos.append(file_path)
    
    def remove_video(self):
        """Remove selected video from patient profile."""
        item = self.patient_form_widget.videos_list.currentItem()
        if item:
            video_path = item.text()
            if video_path in self.current_patient.associated_videos:
                self.current_patient.associated_videos.remove(video_path)
            self.patient_form_widget.videos_list.takeItem(self.patient_form_widget.videos_list.row(item))
    
    def add_image(self):
        """Add image file to patient profile."""
        if not self.current_patient:
            QMessageBox.warning(self, "Error", "No patient selected or created.")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)"
        )
        
        if file_path:
            self.patient_form_widget.images_list.addItem(file_path)
            if file_path not in self.current_patient.associated_images:
                self.current_patient.associated_images.append(file_path)
    
    def remove_image(self):
        """Remove selected image from patient profile."""
        item = self.patient_form_widget.images_list.currentItem()
        if item:
            image_path = item.text()
            if image_path in self.current_patient.associated_images:
                self.current_patient.associated_images.remove(image_path)
            self.patient_form_widget.images_list.takeItem(self.patient_form_widget.images_list.row(item))
    
    def go_to_surgery(self):
        """Navigate to surgical imaging interface for the current patient."""
        if not self.current_patient:
            QMessageBox.warning(self, "No Patient", "Please select or create a patient first.")
            return
        try:
            self.surgery_window = VideoWindow(
                patient_id=self.current_patient.patient_id,
                patient_db=self.db
            )
            self.surgery_window.show()
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open surgical interface: {e}")
    
    def closeEvent(self, event):
        """Save geometry on close."""
        geo = self.geometry()
        save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        super().closeEvent(event)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = PatientProfileWindow()
    window.show()
    sys.exit(app.exec())
