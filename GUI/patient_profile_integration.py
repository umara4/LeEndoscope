"""
Integration example for Patient Profile Manager.

This file demonstrates how to integrate the Patient Profile Manager into your
main LeEndoscope application. You can adapt these patterns to your specific UI flow.
"""

# Example 1: Add to existing menu in ui_windows.py
# ================================================

# In your MainWindow or equivalent class, add this import at the top:
# from patient_profile import PatientProfileWindow

# Then add this method to your main window class:
def open_patient_profiles(self):
    """Open the Patient Profile Manager window."""
    self.patient_profile_window = PatientProfileWindow()
    self.patient_profile_window.show()


# Example 2: Add navigation button in main application
# ====================================================

# In your main UI setup (e.g., MainLoginWindow or similar):

def create_main_menu(self):
    """Create main application menu with Patient Profiles option."""
    menu_layout = QVBoxLayout()
    
    # ... existing menu items ...
    
    patient_profiles_btn = QPushButton("Patient Profiles")
    patient_profiles_btn.setMinimumHeight(50)
    patient_profiles_btn.clicked.connect(self.open_patient_profiles)
    menu_layout.addWidget(patient_profiles_btn)
    
    # ... rest of menu ...
    
    return menu_layout


# Example 3: Integration with VideoWindow
# ========================================

# In video_window.py, add this to link videos to patient profiles:

from patient_profile import PatientDatabase, PatientProfile

class VideoWindow(QMainWindow):
    def __init__(self):
        # ... existing code ...
        self.patient_db = PatientDatabase()
        self.current_patient = None  # Track current patient if needed
    
    def link_recording_to_patient(self, video_path: str, patient_id: str):
        """Link a recorded video to a patient profile."""
        patient = self.patient_db.load_patient(patient_id)
        if patient:
            if video_path not in patient.associated_videos:
                patient.associated_videos.append(video_path)
                self.patient_db.save_patient(patient)
                QMessageBox.information(
                    self, "Success",
                    f"Video linked to patient: {patient.get_display_name()}"
                )


# Example 4: Launch Patient Profile Manager on startup
# ====================================================

# In main.py, add this to show patient profile manager as part of your workflow:

def main():
    app = QApplication(sys.argv)
    
    # ... apply styles ...
    
    # Check if you want to show patient profiles manager first
    show_patient_manager = True  # Can be controlled by user preference
    
    if show_patient_manager:
        patient_window = PatientProfileWindow()
        patient_window.show()
    
    main_login = MainLoginWindow()
    main_login.show()
    
    sys.exit(app.exec())


# Example 5: Quick patient search and selection dialog
# ====================================================

from PyQt6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
from PyQt6.QtCore import Qt

class PatientSelectorDialog(QDialog):
    """Quick patient selector for use within other windows."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Patient")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Search bar
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search by name...")
        layout.addWidget(search_bar)
        
        # Patient list
        self.patient_list = QListWidget()
        layout.addWidget(self.patient_list)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Load patients
        db = PatientDatabase()
        patients = db.load_all_patients()
        
        for patient in patients:
            item = QListWidgetItem(patient.get_display_name())
            item.setData(Qt.ItemDataRole.UserRole, patient.patient_id)
            self.patient_list.addItem(item)
        
        # Connect search
        search_bar.textChanged.connect(self.filter_patients)
        
        self.db = db
        self.all_patients = patients
    
    def filter_patients(self, text: str):
        """Filter patient list by search text."""
        self.patient_list.clear()
        
        search_lower = text.lower()
        for patient in self.all_patients:
            if (search_lower in patient.first_name.lower() or
                search_lower in patient.last_name.lower() or
                search_lower in patient.get_display_name().lower()):
                
                item = QListWidgetItem(patient.get_display_name())
                item.setData(Qt.ItemDataRole.UserRole, patient.patient_id)
                self.patient_list.addItem(item)
    
    def get_selected_patient_id(self) -> str:
        """Get the selected patient ID."""
        item = self.patient_list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None


# Example 6: Context menu in VideoWindow for linking videos
# ==========================================================

def add_video_linking_menu(video_window: VideoWindow):
    """Add context menu option to link videos to patients."""
    
    def link_current_video_to_patient():
        if not video_window.current_file:
            QMessageBox.warning(
                video_window,
                "Error",
                "No video loaded."
            )
            return
        
        dialog = PatientSelectorDialog(video_window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            patient_id = dialog.get_selected_patient_id()
            if patient_id:
                video_window.link_recording_to_patient(
                    video_window.current_file,
                    patient_id
                )
    
    # Add button to video window
    link_button = QPushButton("Link to Patient")
    link_button.clicked.connect(link_current_video_to_patient)
    # Add this button to your video window's control panel
    
    return link_button


# Example 7: Batch import patients
# ================================

def import_patients_from_csv(csv_file: str):
    """
    Import multiple patients from a CSV file.
    CSV format: first_name, last_name, dob, contact, email, ...
    """
    import csv
    from pathlib import Path
    
    db = PatientDatabase()
    imported_count = 0
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                patient = PatientProfile(
                    first_name=row.get('first_name', ''),
                    last_name=row.get('last_name', ''),
                    date_of_birth=row.get('dob', ''),
                    contact_number=row.get('contact', ''),
                    email=row.get('email', ''),
                    # ... other fields ...
                )
                db.save_patient(patient)
                imported_count += 1
        
        QMessageBox.information(
            None,
            "Import Complete",
            f"Successfully imported {imported_count} patients."
        )
    except Exception as e:
        QMessageBox.critical(
            None,
            "Import Error",
            f"Error importing patients: {str(e)}"
        )


# Example 8: Export patient data
# ==============================

def export_patients_to_csv(output_file: str):
    """Export all patient data to CSV."""
    import csv
    
    db = PatientDatabase()
    patients = db.load_all_patients()
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'patient_id', 'first_name', 'last_name', 'date_of_birth',
                'gender', 'contact_number', 'email', 'city', 'country',
                'tumor_location', 'tumor_type', 'tumor_stage',
                'surgery_date', 'surgery_type', 'created_date'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for patient in patients:
                writer.writerow({
                    'patient_id': patient.patient_id,
                    'first_name': patient.first_name,
                    'last_name': patient.last_name,
                    'date_of_birth': patient.date_of_birth,
                    'gender': patient.gender,
                    'contact_number': patient.contact_number,
                    'email': patient.email,
                    'city': patient.city,
                    'country': patient.country,
                    'tumor_location': patient.tumor_location,
                    'tumor_type': patient.tumor_type,
                    'tumor_stage': patient.tumor_stage,
                    'surgery_date': patient.surgery_date,
                    'surgery_type': patient.surgery_type,
                    'created_date': patient.created_date,
                })
        
        QMessageBox.information(
            None,
            "Export Complete",
            f"Successfully exported patients to {output_file}"
        )
    except Exception as e:
        QMessageBox.critical(
            None,
            "Export Error",
            f"Error exporting patients: {str(e)}"
        )


# Example 9: Minimal standalone test
# ==================================

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Test PatientProfileWindow
    window = PatientProfileWindow()
    window.show()
    
    sys.exit(app.exec())
