"""
AppShell -- main application window with persistent navigation bar.

Contains a top nav bar with tab buttons and a QStackedWidget holding
the four main pages: Patient Profile, Imaging, Reconstruction, Export.
Launched after successful login.
"""
from __future__ import annotations

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
from frontend.reconstruction.reconstruction_page import ReconstructionPage
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

        root_layout.addLayout(nav_bar)

        # --- Stacked pages ---
        self._stack = QStackedWidget()

        self._patient_page = PatientProfilePage(db=self._patient_db)
        self._patient_page.navigate_to_imaging.connect(lambda: self._switch_to(1))

        self._imaging_page = ImagingPage()
        self._imaging_page.set_patient_context(
            patient_id=None, patient_db=self._patient_db
        )
        self._imaging_page.navigate_to_reconstruction.connect(lambda: self._switch_to(2))

        self._reconstruction_page = ReconstructionPage()
        self._export_page = ExportPage()

        self._stack.addWidget(self._patient_page)   # 0
        self._stack.addWidget(self._imaging_page)    # 1
        self._stack.addWidget(self._reconstruction_page)  # 2
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
        self._switch_to(idx)

    def _switch_to(self, idx: int):
        """Switch the visible page and update tab highlighting."""
        # When switching TO imaging, push current patient context
        if idx == 1:
            patient = self._patient_page.current_patient
            pid = patient.patient_id if patient else None
            self._imaging_page.set_patient_context(pid, self._patient_db)

        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_buttons):
            if i == idx:
                btn.setStyleSheet(NAV_BAR_ACTIVE_STYLE)
            elif i == 4:
                # Logout button always default style
                btn.setStyleSheet(NAV_BAR_BUTTON_STYLE)
            else:
                btn.setStyleSheet(NAV_BAR_BUTTON_STYLE)

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    def _logout(self):
        # Silent-save current patient
        if self._patient_page.current_patient:
            self._patient_page._save_patient_silently()

        # Cleanup imaging page (serial, etc.)
        self._imaging_page.cleanup()

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
        self._flush_geometry_save()
        super().closeEvent(event)
