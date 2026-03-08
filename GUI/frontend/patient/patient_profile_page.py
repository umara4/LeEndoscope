"""
Patient profile management page (QWidget for embedding in AppShell).

Adapted from patient_profile_window.py. All patient CRUD logic is preserved.
Navigation and geometry are handled by the parent AppShell.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidgetItem, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal

from backend.patient_model import PatientProfile
from backend.patient_db import PatientDatabase

from frontend.patient.patient_list_widget import PatientListWidget
from frontend.patient.patient_form_widget import PatientFormWidget
from shared.theme import ACCENT_BUTTON_STYLE


class PatientProfilePage(QWidget):
    """Patient profile management page."""

    navigate_to_imaging = pyqtSignal()

    def __init__(self, db=None, parent=None):
        super().__init__(parent)

        self.db = db if db is not None else PatientDatabase()
        self.current_patient: Optional[PatientProfile] = None

        main_layout = QVBoxLayout(self)

        # Content area with patient list and form
        content_layout = QHBoxLayout()

        # Left panel - Patient list
        self.patient_list_widget = PatientListWidget()
        self.patient_list_widget.new_patient_btn.clicked.connect(self.new_patient)
        self.patient_list_widget.patient_list.itemSelectionChanged.connect(self.on_patient_selected)
        content_layout.addWidget(self.patient_list_widget, 1)

        # Right panel - Patient form
        self.patient_form_widget = PatientFormWidget()
        self.patient_form_widget.add_video_btn.clicked.connect(self.add_video)
        self.patient_form_widget.remove_video_btn.clicked.connect(self.remove_video)
        self.patient_form_widget.add_image_btn.clicked.connect(self.add_imu_data)
        self.patient_form_widget.remove_image_btn.clicked.connect(self.remove_imu_data)
        content_layout.addWidget(self.patient_form_widget, 2)

        main_layout.addLayout(content_layout, 1)

        # Bottom row — Load Patient and Save Patient buttons side by side
        bottom_row = QHBoxLayout()
        self._load_patient_btn = QPushButton("Load Patient")
        self._load_patient_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._load_patient_btn.setFixedHeight(40)
        self._load_patient_btn.clicked.connect(self._on_go_to_imaging)
        bottom_row.addWidget(self._load_patient_btn, 1)

        self._save_patient_btn = QPushButton("Save Patient")
        self._save_patient_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._save_patient_btn.setFixedHeight(40)
        self._save_patient_btn.clicked.connect(self.save_current_patient)
        bottom_row.addWidget(self._save_patient_btn, 2)

        main_layout.addLayout(bottom_row)

        # Load all patients
        self.refresh_patient_list()

    # ------------------------------------------------------------------
    # Patient list
    # ------------------------------------------------------------------
    def refresh_patient_list(self):
        lst = self.patient_list_widget.patient_list
        lst.blockSignals(True)
        lst.clear()
        patients = self.db.load_all_patients()
        for patient in patients:
            item = QListWidgetItem(patient.get_display_name())
            item.setData(Qt.ItemDataRole.UserRole, patient.patient_id)
            lst.addItem(item)
        lst.blockSignals(False)

    def new_patient(self):
        # Block signals so clearSelection doesn't trigger on_patient_selected
        # and reload the old patient's data over our new blank patient.
        self.patient_list_widget.patient_list.blockSignals(True)
        self.patient_list_widget.patient_list.clearSelection()
        self.patient_list_widget.patient_list.setCurrentItem(None)
        self.patient_list_widget.patient_list.blockSignals(False)

        self.current_patient = PatientProfile()
        self.clear_form()
        QMessageBox.information(self, "New Patient", "New patient profile created. Fill in the information and save.")

    def on_patient_selected(self):
        item = self.patient_list_widget.patient_list.currentItem()
        if item:
            patient_id = item.data(Qt.ItemDataRole.UserRole)
            self.current_patient = self.db.load_patient(patient_id)
            if self.current_patient:
                self.load_patient_into_form(self.current_patient)
                # Media is session-only; clear DB-loaded media references
                self.current_patient.associated_videos = []
                self.current_patient.associated_images = []

    # ------------------------------------------------------------------
    # Form load / clear
    # ------------------------------------------------------------------
    def load_patient_into_form(self, patient: PatientProfile):
        f = self.patient_form_widget

        f.first_name_input.setText(patient.first_name)
        f.last_name_input.setText(patient.last_name)
        f.dob_input.setDate(QDate.fromString(patient.date_of_birth, "yyyy-MM-dd") if patient.date_of_birth else QDate.currentDate())
        f.gender_combo.setCurrentText(patient.gender)
        f.contact_input.setText(patient.contact_number)
        f.email_input.setText(patient.email)

        f.street_input.setText(patient.street_address)
        f.city_input.setText(patient.city)
        f.state_input.setText(patient.state_province)
        f.postal_input.setText(patient.postal_code)
        f.country_input.setText(patient.country)

        f.emergency_name_input.setText(patient.emergency_contact_name)
        f.emergency_phone_input.setText(patient.emergency_contact_phone)
        f.emergency_relationship_input.setText(patient.emergency_contact_relationship)

        f.medical_history_text.setText(patient.medical_history)
        f.allergies_text.setText(patient.allergies)
        f.medications_text.setText(patient.current_medications)

        f.tumor_location_input.setText(patient.tumor_location)
        f.tumor_size_input.setText(patient.tumor_size)
        f.tumor_type_input.setText(patient.tumor_type)
        f.tumor_stage_combo.setCurrentText(patient.tumor_stage)
        f.tumor_description_text.setText(patient.tumor_description)

        f.surgery_date_input.setDate(QDate.fromString(patient.surgery_date, "yyyy-MM-dd") if patient.surgery_date else QDate.currentDate())
        f.surgery_type_input.setText(patient.surgery_type)
        f.surgeon_input.setText(patient.surgeon_name)
        f.surgery_notes_text.setText(patient.surgery_notes)

        f.pre_surgery_text.setText(patient.pre_surgery_notes)
        f.post_surgery_text.setText(patient.post_surgery_notes)

        # Media is session-only; always start with empty lists
        f.videos_list.clear()
        f.images_list.clear()
        f.session_name_input.clear()

    def clear_form(self):
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
        f.session_name_input.clear()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _copy_form_to_patient(self):
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
        if not self.current_patient:
            QMessageBox.warning(self, "Error", "No patient selected or created.")
            return
        self._copy_form_to_patient()
        self._save_patient_without_media()

        # Refresh list and re-select the saved patient
        saved_id = self.current_patient.patient_id
        self.refresh_patient_list()
        self._select_patient_in_list(saved_id)

        QMessageBox.information(self, "Success", "Patient profile saved successfully.")

    def _select_patient_in_list(self, patient_id: str):
        """Select a patient in the list widget by ID without triggering a reload."""
        lst = self.patient_list_widget.patient_list
        for i in range(lst.count()):
            item = lst.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == patient_id:
                lst.blockSignals(True)
                lst.setCurrentItem(item)
                lst.blockSignals(False)
                return

    def _save_patient_silently(self):
        try:
            self._copy_form_to_patient()
            self._save_patient_without_media()
        except Exception:
            pass

    def _save_patient_without_media(self):
        """Save patient to DB without media references (media is session-only)."""
        p = self.current_patient
        videos_backup = p.associated_videos
        images_backup = p.associated_images
        p.associated_videos = []
        p.associated_images = []
        try:
            self.db.save_patient(p)
        finally:
            p.associated_videos = videos_backup
            p.associated_images = images_backup

    def receive_recording(self, video_path: str, imu_path: str):
        """Called by AppShell when imaging page finishes a recording."""
        if not self.current_patient:
            return
        if video_path and video_path not in self.current_patient.associated_videos:
            self.current_patient.associated_videos.append(video_path)
            self.patient_form_widget.videos_list.addItem(video_path)
        if imu_path and imu_path not in self.current_patient.associated_images:
            self.current_patient.associated_images.append(imu_path)
            self.patient_form_widget.images_list.addItem(imu_path)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_go_to_imaging(self):
        if not self.current_patient:
            QMessageBox.warning(self, "No Patient", "Please select or create a patient first.")
            return
        self._save_patient_silently()
        self.navigate_to_imaging.emit()

    # ------------------------------------------------------------------
    # Media management
    # ------------------------------------------------------------------
    def add_video(self):
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
        item = self.patient_form_widget.videos_list.currentItem()
        if item:
            video_path = item.text()
            if video_path in self.current_patient.associated_videos:
                self.current_patient.associated_videos.remove(video_path)
            self.patient_form_widget.videos_list.takeItem(self.patient_form_widget.videos_list.row(item))

    def add_imu_data(self):
        if not self.current_patient:
            QMessageBox.warning(self, "Error", "No patient selected or created.")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select IMU Data", "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            self.patient_form_widget.images_list.addItem(file_path)
            if file_path not in self.current_patient.associated_images:
                self.current_patient.associated_images.append(file_path)

    def remove_imu_data(self):
        item = self.patient_form_widget.images_list.currentItem()
        if item:
            image_path = item.text()
            if image_path in self.current_patient.associated_images:
                self.current_patient.associated_images.remove(image_path)
            self.patient_form_widget.images_list.takeItem(self.patient_form_widget.images_list.row(item))
