"""
Patient profile management window (coordinator).

Split from patient_profile.py PatientProfileWindow.
Uses backend PatientDatabase (SQLite) and PatientProfile model.
Uses DebouncedGeometryMixin for geometry persistence.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidgetItem, QMessageBox, QFileDialog, QPushButton,
)
from PyQt6.QtCore import Qt, QDate

from backend.patient_model import PatientProfile
from backend.patient_db import PatientDatabase
from shared.geometry_mixin import DebouncedGeometryMixin
from shared.geometry_store import load_geometry

from frontend.patient.patient_list_widget import PatientListWidget
from frontend.patient.patient_form_widget import PatientFormWidget


class PatientProfileWindow(QMainWindow, DebouncedGeometryMixin):
    """Main patient profile management window."""

    def __init__(self, db=None):
        super().__init__()
        self.setWindowTitle("Patient Profile Manager")
        self.resize(1400, 800)

        # Restore geometry if available
        g = load_geometry()
        if g:
            try:
                self.setGeometry(*g)
            except Exception:
                pass

        # Initialize database
        self.db = db if db is not None else PatientDatabase()
        self.current_patient: Optional[PatientProfile] = None

        # Create main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # Top bar with logout button
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.logout_btn = QPushButton("Log Out")
        self.logout_btn.setFixedWidth(100)
        self.logout_btn.clicked.connect(self.logout)
        top_bar.addWidget(self.logout_btn)
        main_layout.addLayout(top_bar)

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
        f = self.patient_form_widget

        # Basic Info
        f.first_name_input.setText(patient.first_name)
        f.last_name_input.setText(patient.last_name)
        f.dob_input.setDate(QDate.fromString(patient.date_of_birth, "yyyy-MM-dd") if patient.date_of_birth else QDate.currentDate())
        f.gender_combo.setCurrentText(patient.gender)
        f.contact_input.setText(patient.contact_number)
        f.email_input.setText(patient.email)

        # Address
        f.street_input.setText(patient.street_address)
        f.city_input.setText(patient.city)
        f.state_input.setText(patient.state_province)
        f.postal_input.setText(patient.postal_code)
        f.country_input.setText(patient.country)

        # Emergency Contact
        f.emergency_name_input.setText(patient.emergency_contact_name)
        f.emergency_phone_input.setText(patient.emergency_contact_phone)
        f.emergency_relationship_input.setText(patient.emergency_contact_relationship)

        # Medical History
        f.medical_history_text.setText(patient.medical_history)
        f.allergies_text.setText(patient.allergies)
        f.medications_text.setText(patient.current_medications)

        # Tumor Information
        f.tumor_location_input.setText(patient.tumor_location)
        f.tumor_size_input.setText(patient.tumor_size)
        f.tumor_type_input.setText(patient.tumor_type)
        f.tumor_stage_combo.setCurrentText(patient.tumor_stage)
        f.tumor_description_text.setText(patient.tumor_description)

        # Surgery Information
        f.surgery_date_input.setDate(QDate.fromString(patient.surgery_date, "yyyy-MM-dd") if patient.surgery_date else QDate.currentDate())
        f.surgery_type_input.setText(patient.surgery_type)
        f.surgeon_input.setText(patient.surgeon_name)
        f.surgery_notes_text.setText(patient.surgery_notes)

        # Pre/Post Surgery Notes
        f.pre_surgery_text.setText(patient.pre_surgery_notes)
        f.post_surgery_text.setText(patient.post_surgery_notes)

        # Media
        f.videos_list.clear()
        for video in patient.associated_videos:
            f.videos_list.addItem(video)

        f.images_list.clear()
        for image in patient.associated_images:
            f.images_list.addItem(image)

    def clear_form(self):
        """Clear all form fields."""
        f = self.patient_form_widget

        f.first_name_input.clear()
        f.last_name_input.clear()
        f.dob_input.setDate(QDate.currentDate())
        f.gender_combo.setCurrentIndex(0)
        f.contact_input.clear()
        f.email_input.clear()

        f.street_input.clear()
        f.city_input.clear()
        f.state_input.clear()
        f.postal_input.clear()
        f.country_input.clear()

        f.emergency_name_input.clear()
        f.emergency_phone_input.clear()
        f.emergency_relationship_input.clear()

        f.medical_history_text.clear()
        f.allergies_text.clear()
        f.medications_text.clear()

        f.tumor_location_input.clear()
        f.tumor_size_input.clear()
        f.tumor_type_input.clear()
        f.tumor_stage_combo.setCurrentIndex(0)
        f.tumor_description_text.clear()

        f.surgery_date_input.setDate(QDate.currentDate())
        f.surgery_type_input.clear()
        f.surgeon_input.clear()
        f.surgery_notes_text.clear()

        f.pre_surgery_text.clear()
        f.post_surgery_text.clear()

        f.videos_list.clear()
        f.images_list.clear()

    def _copy_form_to_patient(self):
        """Copy all form field values into self.current_patient."""
        p = self.current_patient
        f = self.patient_form_widget

        p.first_name = f.first_name_input.text()
        p.last_name = f.last_name_input.text()
        p.date_of_birth = f.dob_input.date().toString("yyyy-MM-dd")
        p.gender = f.gender_combo.currentText()
        p.contact_number = f.contact_input.text()
        p.email = f.email_input.text()

        p.street_address = f.street_input.text()
        p.city = f.city_input.text()
        p.state_province = f.state_input.text()
        p.postal_code = f.postal_input.text()
        p.country = f.country_input.text()

        p.emergency_contact_name = f.emergency_name_input.text()
        p.emergency_contact_phone = f.emergency_phone_input.text()
        p.emergency_contact_relationship = f.emergency_relationship_input.text()

        p.medical_history = f.medical_history_text.toPlainText()
        p.allergies = f.allergies_text.toPlainText()
        p.current_medications = f.medications_text.toPlainText()

        p.tumor_location = f.tumor_location_input.text()
        p.tumor_size = f.tumor_size_input.text()
        p.tumor_type = f.tumor_type_input.text()
        p.tumor_stage = f.tumor_stage_combo.currentText()
        p.tumor_description = f.tumor_description_text.toPlainText()

        p.surgery_date = f.surgery_date_input.date().toString("yyyy-MM-dd")
        p.surgery_type = f.surgery_type_input.text()
        p.surgeon_name = f.surgeon_input.text()
        p.surgery_notes = f.surgery_notes_text.toPlainText()

        p.pre_surgery_notes = f.pre_surgery_text.toPlainText()
        p.post_surgery_notes = f.post_surgery_text.toPlainText()

    def save_current_patient(self):
        """Save current patient data from form."""
        if not self.current_patient:
            QMessageBox.warning(self, "Error", "No patient selected or created.")
            return

        self._copy_form_to_patient()
        self.db.save_patient(self.current_patient)
        self.refresh_patient_list()
        QMessageBox.information(self, "Success", "Patient profile saved successfully.")

    def _save_patient_silently(self):
        """Save current patient without showing a success dialog."""
        try:
            self._copy_form_to_patient()
            self.db.save_patient(self.current_patient)
        except Exception:
            pass

    def logout(self):
        """Save patient silently, then return to the login screen."""
        if self.current_patient:
            self._save_patient_silently()
        self._flush_geometry_save()
        from frontend.auth.login_window import MainLoginWindow
        from backend.user_db import UserDatabase
        login = MainLoginWindow(db=UserDatabase())
        geo = self.geometry()
        login.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
        login.show()
        self.close()

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
            from frontend.video.video_main_window import VideoWindow
            self.surgery_window = VideoWindow(
                patient_id=self.current_patient.patient_id,
                patient_db=self.db
            )
            geo = self.geometry()
            self.surgery_window.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
            self._flush_geometry_save()
            self.surgery_window.show()
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open surgical interface: {e}")

    def closeEvent(self, event):
        """Save geometry on close."""
        self._flush_geometry_save()
        super().closeEvent(event)
