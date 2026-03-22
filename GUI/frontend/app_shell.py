"""
AppShell -- main application window with persistent navigation bar.

Contains a top nav bar with tab buttons and a QStackedWidget holding
the four main pages: Patient Profile, Imaging, Reconstruction, Export.
Launched after successful login.
"""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget,
)

from shared.geometry_mixin import DebouncedGeometryMixin
from shared.geometry_store import load_geometry
from shared.theme import NAV_BAR_BUTTON_STYLE, NAV_BAR_ACTIVE_STYLE

from backend.patient_db import PatientDatabase

from frontend.patient.patient_profile_page import PatientProfilePage
from frontend.video.imaging_page import ImagingPage
from frontend.export_page import ExportPage


class AppShell(QMainWindow, DebouncedGeometryMixin):
    """Single-window shell with tab navigation and stacked pages."""

    _TAB_LABELS = ["Patient Profile", "Imaging", "Reconstruction", "Export", "Log Out"]

    def __init__(self, user_db=None, patient_db=None):
        super().__init__()
        self.setWindowTitle("LeEndoscope")
        self.resize(1400, 800)

        # Restore geometry
        g = load_geometry()
        if g:
            try:
                self.setGeometry(*g)
            except Exception:
                pass

        self._user_db = user_db
        self._patient_db = patient_db if patient_db is not None else PatientDatabase()

        # Page-access gating flags
        self._imaging_unlocked = False
        self._reconstruction_loaded = False

        # --- Central widget ---
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Nav bar ---
        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(4, 4, 4, 4)
        nav_bar.setSpacing(4)

        self._tab_buttons: list[QPushButton] = []
        for i, label in enumerate(self._TAB_LABELS):
            btn = QPushButton(label)
            btn.setFixedHeight(36)
            btn.setStyleSheet(NAV_BAR_BUTTON_STYLE)
            btn.clicked.connect(lambda checked, idx=i: self._on_tab_clicked(idx))
            nav_bar.addWidget(btn, stretch=1)
            self._tab_buttons.append(btn)

        # Imaging and Export tabs start locked; Reconstruction is always available
        self._tab_buttons[1].setEnabled(False)
        self._tab_buttons[3].setEnabled(False)

        root_layout.addLayout(nav_bar)

        # --- Stacked pages ---
        self._stack = QStackedWidget()

        self._patient_page = PatientProfilePage(db=self._patient_db)
        self._patient_page.navigate_to_imaging.connect(self._unlock_and_go_to_imaging)

        self._imaging_page = ImagingPage()
        self._imaging_page.set_patient_context(
            patient_id=None, patient_db=self._patient_db
        )
        self._imaging_page.navigate_to_reconstruction.connect(
            self._unlock_and_go_to_reconstruction
        )
        self._imaging_page.recording_saved.connect(self._on_recording_saved)

        self._reconstruction_placeholder = QWidget()  # lazy-loaded on first visit
        self._export_page = ExportPage()

        self._stack.addWidget(self._patient_page)   # 0
        self._stack.addWidget(self._imaging_page)    # 1
        self._stack.addWidget(self._reconstruction_placeholder)  # 2
        self._stack.addWidget(self._export_page)     # 3

        root_layout.addWidget(self._stack, 1)

        self.setCentralWidget(central)

        # Start on Patient Profile tab
        self._switch_to(0)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_tab_clicked(self, idx: int):
        if idx == 4:
            self._logout()
            return
        if idx == 1 and not self._imaging_unlocked:
            return
        if idx == 2:
            self._ensure_reconstruction_loaded()
        if idx == 3:
            return  # Export not yet implemented
        self._switch_to(idx)

    def _ensure_reconstruction_loaded(self):
        """Lazy-load the ReconstructionPage on first visit."""
        if not self._reconstruction_loaded:
            from frontend.reconstruction.reconstruction_page import ReconstructionPage
            self._reconstruction_page = ReconstructionPage()
            self._stack.removeWidget(self._reconstruction_placeholder)
            self._reconstruction_placeholder.deleteLater()
            self._stack.insertWidget(2, self._reconstruction_page)
            self._reconstruction_loaded = True

    def _unlock_and_go_to_imaging(self):
        self._imaging_unlocked = True
        self._tab_buttons[1].setEnabled(True)

        patient = self._patient_page.current_patient
        pid = patient.patient_id if patient else None

        # Always force-reset imaging state (even for same patient)
        self._imaging_page.patient_id = None  # ensure set_patient_context detects a change
        self._imaging_page.set_patient_context(pid, self._patient_db)

        # Read session media from in-memory patient (not DB)
        # Skip redundant load if the same video is already loaded
        if patient:
            video_path = patient.associated_videos[0] if patient.associated_videos else None
            imu_path = patient.associated_images[0] if patient.associated_images else None
            session_name = self._patient_page.patient_form_widget.session_name_input.text()
            already_loaded = (
                video_path
                and self._imaging_page.video_path
                and os.path.abspath(video_path) == os.path.abspath(self._imaging_page.video_path)
            )
            if not already_loaded:
                self._imaging_page.load_patient_media(video_path, imu_path, session_name)

        self._switch_to(1)

    def _unlock_and_go_to_reconstruction(self, session_info: dict):
        self._ensure_reconstruction_loaded()
        self._reconstruction_page.set_session_info(session_info)
        self._switch_to(2)

    def _switch_to(self, idx: int):
        """Switch the visible page and update tab highlighting."""
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_buttons):
            if i == idx:
                btn.setStyleSheet(NAV_BAR_ACTIVE_STYLE)
            else:
                btn.setStyleSheet(NAV_BAR_BUTTON_STYLE)

    # ------------------------------------------------------------------
    # Recording → Patient Profile relay
    # ------------------------------------------------------------------
    def _on_recording_saved(self, video_path: str, imu_path: str):
        """Push recording paths from imaging page to patient profile media."""
        self._patient_page.receive_recording(video_path, imu_path)

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    def _logout(self):
        # Silent-save current patient
        if self._patient_page.current_patient:
            self._patient_page._save_patient_silently()

        # Cleanup imaging page (serial, etc.)
        self._imaging_page.cleanup()

        # Cleanup reconstruction page (SSH + viewer shutdown)
        if self._reconstruction_loaded and hasattr(self, "_reconstruction_page"):
            try:
                self._reconstruction_page.cleanup()
            except Exception:
                pass

        self._flush_geometry_save()

        from frontend.auth.login_window import MainLoginWindow
        self._login_ref = MainLoginWindow(db=self._user_db)
        geo = self.geometry()
        self._login_ref.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
        self._login_ref.show()
        self.close()

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        try:
            self._imaging_page.cleanup()
        except Exception:
            pass
        if self._reconstruction_loaded and hasattr(self, "_reconstruction_page"):
            try:
                self._reconstruction_page.cleanup()
            except Exception:
                pass
        self._flush_geometry_save()
        super().closeEvent(event)
