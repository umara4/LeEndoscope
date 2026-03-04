"""
Session directory management.

Handles creation and organization of data session directories:

  Patient case:
    Data/PATIENT-FirstLast/SessionName-Timestamp/
      Raw Data/
        Recording.mp4
        FrameTimestamp.csv
        IMUTimeStamp.csv
      SegmentName1/
        Frame1.png, Frame2.png, ...
        averaged_imu.csv
      SegmentName2/
        Frame1.png, Frame2.png, ...
        averaged_imu.csv

  Non-patient case:
    Data/SessionName-Timestamp/
      Raw Data/ ...
      SegmentName/ ...

Extracted from VideoWindow._get_session_dir, _segment_frames_output_dir,
_segment_folder_name, _sanitize_filename_component.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional

from shared.constants import DATA_DIR


def sanitize_filename_component(value: str) -> str:
    """Windows-safe filename component; keep it minimal."""
    return "".join(
        ch if ch.isalnum() or ch in ("-", "_", ".") else "_"
        for ch in value
    ).strip(" _")


def patient_folder_name(patient_db, patient_id: str) -> Optional[str]:
    """Build 'PATIENT-FirstLast' folder name from patient DB record."""
    if not patient_id or not patient_db:
        return None
    try:
        p = patient_db.load_patient(patient_id)
        if not p:
            return None
        first = (p.first_name or "").strip()
        last = (p.last_name or "").strip()
        name_part = sanitize_filename_component(f"{first}{last}") or patient_id[:12]
        return f"PATIENT-{name_part}"
    except Exception:
        return None


class SessionManager:
    """Manages a recording/extraction session directory."""

    def __init__(self, patient_id: Optional[str] = None, patient_db=None):
        self.patient_id = patient_id
        self.patient_db = patient_db
        self._session_dir: Optional[Path] = None
        self._session_base_name: str = ""

    def get_session_dir(self, session_name: str = "") -> Path:
        """Return (and lazily create) the session directory.

        Re-uses the same directory if the base name has not changed.
        When a patient_id is set, nests under Data/PATIENT-FirstLast/.
        """
        name = session_name.strip() or "Session"

        if (self._session_dir is not None
                and self._session_base_name
                and name == self._session_base_name):
            return self._session_dir

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = sanitize_filename_component(name) or "Session"
        safe = f"{base}-{timestamp}"

        self._session_base_name = name
        folder = patient_folder_name(self.patient_db, self.patient_id)
        if folder:
            patient_dir = DATA_DIR / folder
            patient_dir.mkdir(parents=True, exist_ok=True)
            self._session_dir = patient_dir / safe
        else:
            self._session_dir = DATA_DIR / safe
        self._session_dir.mkdir(parents=True, exist_ok=True)
        return self._session_dir

    @property
    def session_dir(self) -> Optional[Path]:
        return self._session_dir

    @session_dir.setter
    def session_dir(self, value: Optional[Path]):
        self._session_dir = value

    def segment_frames_output_dir(self, seg: dict) -> str:
        """Return folder path where extracted frames for a segment are stored.

        Segment folders go directly in the session directory.
        """
        name = str(seg.get("name", "segment")).strip() or "segment"
        safe_name = sanitize_filename_component(name.replace(" ", "_")) or "segment"

        session_dir = self.get_session_dir()
        frames_dir = session_dir / safe_name
        frames_dir.mkdir(parents=True, exist_ok=True)
        return str(frames_dir)

    @staticmethod
    def segment_folder_name(seg: dict) -> str:
        """Build a filesystem-safe segment folder name from segment dict."""
        name = str(seg.get("name", "segment")).strip() or "segment"
        safe_name = sanitize_filename_component(name.replace(" ", "_")) or "segment"
        try:
            start_str = seg["start"].toString("HH-mm-ss")
            end_str = seg["end"].toString("HH-mm-ss")
        except Exception:
            start_str = "00-00-00"
            end_str = "00-00-00"
        return f"{safe_name}__{start_str}__{end_str}"
