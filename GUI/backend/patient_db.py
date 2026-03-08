"""
SQLite-backed patient database.

Replaces the JSON-based PatientDatabase from patient_profile.py.
On first use, auto-migrates data from patients_data.json if it exists.
"""
from __future__ import annotations
import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from backend.patient_model import PatientProfile
from shared.constants import PATIENT_DB_PATH, PATIENTS_JSON_PATH


class PatientDatabase:
    """SQLite-backed patient profile persistence."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else PATIENT_DB_PATH
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()
        self._auto_migrate_json()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                date_of_birth TEXT DEFAULT '',
                gender TEXT DEFAULT 'Not specified',
                contact_number TEXT DEFAULT '',
                email TEXT DEFAULT '',
                street_address TEXT DEFAULT '',
                city TEXT DEFAULT '',
                state_province TEXT DEFAULT '',
                postal_code TEXT DEFAULT '',
                country TEXT DEFAULT '',
                emergency_contact_name TEXT DEFAULT '',
                emergency_contact_phone TEXT DEFAULT '',
                emergency_contact_relationship TEXT DEFAULT '',
                medical_history TEXT DEFAULT '',
                allergies TEXT DEFAULT '',
                current_medications TEXT DEFAULT '',
                tumor_location TEXT DEFAULT '',
                tumor_size TEXT DEFAULT '',
                tumor_type TEXT DEFAULT '',
                tumor_stage TEXT DEFAULT '',
                tumor_description TEXT DEFAULT '',
                surgery_date TEXT DEFAULT '',
                surgery_type TEXT DEFAULT '',
                surgeon_name TEXT DEFAULT '',
                surgery_notes TEXT DEFAULT '',
                pre_surgery_notes TEXT DEFAULT '',
                post_surgery_notes TEXT DEFAULT '',
                created_date TEXT NOT NULL,
                last_modified TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patient_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
                video_path TEXT NOT NULL,
                added_date TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patient_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
                image_path TEXT NOT NULL,
                added_date TEXT NOT NULL
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # JSON migration
    # ------------------------------------------------------------------
    def _auto_migrate_json(self):
        """If patients_data.json exists and the patients table is empty,
        migrate all records and rename JSON to .bak."""
        json_path = PATIENTS_JSON_PATH
        if not json_path.exists():
            return
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM patients")
        if cur.fetchone()[0] > 0:
            return  # already have data
        try:
            count = self.migrate_from_json(json_path)
            if count > 0:
                bak = json_path.with_suffix(".json.bak")
                json_path.rename(bak)
        except Exception:
            pass

    @staticmethod
    def _patient_from_json_dict(data: dict) -> PatientProfile:
        """Create PatientProfile from a JSON dict (handles legacy shapes)."""
        return PatientProfile(**data)

    def migrate_from_json(self, json_path: Path) -> int:
        """Read patients_data.json and insert all patients into SQLite.
        Returns the number of patients migrated."""
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return 0
        count = 0
        for _pid, pdata in data.items():
            if not isinstance(pdata, dict):
                continue
            patient = self._patient_from_json_dict(pdata)
            self._upsert_patient(patient)
            count += 1
        self._conn.commit()
        return count

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def save_patient(self, patient: PatientProfile):
        """Save (insert or update) a patient profile."""
        patient.last_modified = datetime.now().isoformat()
        self._upsert_patient(patient)
        self._conn.commit()

    def load_patient(self, patient_id: str) -> Optional[PatientProfile]:
        """Load a single patient by ID."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        row = cur.fetchone()
        if not row:
            return None
        patient = self._row_to_profile(cur.description, row)
        patient.associated_videos = self._load_videos(patient_id)
        patient.associated_images = self._load_images(patient_id)
        return patient

    def load_all_patients(self) -> List[PatientProfile]:
        """Load all patient profiles using batch queries (3 total)."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM patients ORDER BY last_modified DESC")
        desc = cur.description
        rows = cur.fetchall()

        # Batch-load all videos and images in 2 queries instead of 2*N
        videos_by_pid: dict[str, list[str]] = defaultdict(list)
        for pid, path in self._conn.execute(
            "SELECT patient_id, video_path FROM patient_videos ORDER BY id"
        ):
            videos_by_pid[pid].append(path)

        images_by_pid: dict[str, list[str]] = defaultdict(list)
        for pid, path in self._conn.execute(
            "SELECT patient_id, image_path FROM patient_images ORDER BY id"
        ):
            images_by_pid[pid].append(path)

        patients = []
        for row in rows:
            p = self._row_to_profile(desc, row)
            p.associated_videos = videos_by_pid.get(p.patient_id, [])
            p.associated_images = images_by_pid.get(p.patient_id, [])
            patients.append(p)
        return patients

    def delete_patient(self, patient_id: str):
        """Delete a patient and all associated media references."""
        with self._conn:
            self._conn.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _upsert_patient(self, p: PatientProfile):
        """Insert or replace patient row, plus update video/image refs."""
        self._conn.execute("""
            INSERT OR REPLACE INTO patients (
                patient_id, first_name, last_name, date_of_birth, gender,
                contact_number, email,
                street_address, city, state_province, postal_code, country,
                emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                medical_history, allergies, current_medications,
                tumor_location, tumor_size, tumor_type, tumor_stage, tumor_description,
                surgery_date, surgery_type, surgeon_name, surgery_notes,
                pre_surgery_notes, post_surgery_notes,
                created_date, last_modified
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?
            )
        """, (
            p.patient_id, p.first_name, p.last_name, p.date_of_birth, p.gender,
            p.contact_number, p.email,
            p.street_address, p.city, p.state_province, p.postal_code, p.country,
            p.emergency_contact_name, p.emergency_contact_phone, p.emergency_contact_relationship,
            p.medical_history, p.allergies, p.current_medications,
            p.tumor_location, p.tumor_size, p.tumor_type, p.tumor_stage, p.tumor_description,
            p.surgery_date, p.surgery_type, p.surgeon_name, p.surgery_notes,
            p.pre_surgery_notes, p.post_surgery_notes,
            p.created_date, p.last_modified,
        ))

        # Sync video references
        now_iso = datetime.now().isoformat()
        self._conn.execute("DELETE FROM patient_videos WHERE patient_id = ?", (p.patient_id,))
        for vpath in (p.associated_videos or []):
            self._conn.execute(
                "INSERT INTO patient_videos (patient_id, video_path, added_date) VALUES (?, ?, ?)",
                (p.patient_id, vpath, now_iso),
            )

        # Sync image references
        self._conn.execute("DELETE FROM patient_images WHERE patient_id = ?", (p.patient_id,))
        for ipath in (p.associated_images or []):
            self._conn.execute(
                "INSERT INTO patient_images (patient_id, image_path, added_date) VALUES (?, ?, ?)",
                (p.patient_id, ipath, now_iso),
            )

    def _load_videos(self, patient_id: str) -> List[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT video_path FROM patient_videos WHERE patient_id = ? ORDER BY id", (patient_id,))
        return [row[0] for row in cur.fetchall()]

    def _load_images(self, patient_id: str) -> List[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT image_path FROM patient_images WHERE patient_id = ? ORDER BY id", (patient_id,))
        return [row[0] for row in cur.fetchall()]

    @staticmethod
    def _row_to_profile(description, row) -> PatientProfile:
        """Convert a sqlite3 row+description into a PatientProfile."""
        col_names = [d[0] for d in description]
        data = dict(zip(col_names, row))
        return PatientProfile(**data)

    def close(self):
        self._conn.close()
