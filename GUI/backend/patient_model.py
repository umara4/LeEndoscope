"""
Pure-Python patient data model.
No Qt dependencies -- can be used by both backend services and frontend widgets.

Extracted from patient_profile.py PatientProfile class.
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List, Optional


class PatientProfile:
    """Data model for patient information."""

    def __init__(self, patient_id: str = None, **kwargs):
        self.patient_id = patient_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        # Basic Information
        self.first_name = kwargs.get('first_name', '')
        self.last_name = kwargs.get('last_name', '')
        self.date_of_birth = kwargs.get('date_of_birth', '')
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
        self.surgery_date = kwargs.get('surgery_date', '')
        self.surgery_type = kwargs.get('surgery_type', '')
        self.surgeon_name = kwargs.get('surgeon_name', '')
        self.surgery_notes = kwargs.get('surgery_notes', '')

        # Pre/Post Surgery Notes
        self.pre_surgery_notes = kwargs.get('pre_surgery_notes', '')
        self.post_surgery_notes = kwargs.get('post_surgery_notes', '')

        # Media References
        self.associated_videos: List[str] = kwargs.get('associated_videos', [])
        self.associated_images: List[str] = kwargs.get('associated_images', [])

        # Timestamps
        self.created_date = kwargs.get('created_date', datetime.now().isoformat())
        self.last_modified = kwargs.get('last_modified', datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert patient profile to dictionary for serialization."""
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
