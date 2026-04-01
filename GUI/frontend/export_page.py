"""
Export page -- editable document report with patient data and screenshots.

Renders an HTML report inside a white QTextEdit that looks like a paper
document. The user can edit inline and export to PDF.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QImage, QTextDocument

from shared.theme import ACCENT_BUTTON_STYLE, STYLE_PAGE_TITLE, BG_BASE, TEXT_SECONDARY
from backend.patient_model import PatientProfile


class ExportPage(QWidget):
    """Editable document report with patient info and captioned screenshots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._patient: PatientProfile | None = None
        self._export_dir: Path | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_patient(self, patient: PatientProfile | None, export_dir: Path | None = None):
        """Receive the current patient and their export dir, then rebuild the report."""
        self._patient = patient
        self._export_dir = export_dir
        self._rebuild_report()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # -- Toolbar --
        toolbar = QHBoxLayout()
        title = QLabel("Export Report")
        title.setStyleSheet(STYLE_PAGE_TITLE)
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._refresh_btn.clicked.connect(self._rebuild_report)
        toolbar.addWidget(self._refresh_btn)

        self._pdf_btn = QPushButton("Download PDF")
        self._pdf_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self._pdf_btn.clicked.connect(self._export_pdf)
        toolbar.addWidget(self._pdf_btn)

        layout.addLayout(toolbar)

        # -- Document editor (white page on dark background) --
        doc_row = QHBoxLayout()
        doc_row.addStretch()

        self._editor = QTextEdit()
        self._editor.setObjectName("exportDocument")
        self._editor.setStyleSheet(
            "QTextEdit#exportDocument {"
            "  background-color: #FFFFFF;"
            "  color: #1A1A1A;"
            "  border: 1px solid #CCCCCC;"
            "  padding: 40px;"
            f'  font-family: "Segoe UI", sans-serif;'
            "  font-size: 13px;"
            "}"
        )
        self._editor.setMinimumWidth(780)
        self._editor.setMaximumWidth(850)
        doc_row.addWidget(self._editor, 1)

        doc_row.addStretch()
        layout.addLayout(doc_row, 1)

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _rebuild_report(self):
        doc = self._editor.document()
        doc.clear()

        if not self._patient or not self._export_dir:
            self._editor.setHtml(
                f'<p style="color:#999; text-align:center; padding:60px;">'
                f"Select a patient to generate the export report.</p>"
            )
            return

        # Load screenshot captions
        meta_path = self._export_dir / "screenshots.json"
        captions: dict[str, str] = {}
        if meta_path.exists():
            try:
                captions = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        # Discover screenshots
        screenshots = sorted(self._export_dir.glob("screenshot_*.png"))

        # Register images as document resources
        for img_path in screenshots:
            image = QImage(str(img_path))
            if not image.isNull():
                if image.width() > 700:
                    image = image.scaledToWidth(
                        700, Qt.TransformationMode.SmoothTransformation
                    )
                doc.addResource(
                    QTextDocument.ResourceType.ImageResource,
                    QUrl(img_path.name),
                    image,
                )

        html = self._build_html(captions, screenshots)
        self._editor.setHtml(html)

    # ------------------------------------------------------------------
    # HTML builder
    # ------------------------------------------------------------------

    def _build_html(self, captions: dict, screenshots: list) -> str:
        p = self._patient

        def field(value, fallback="N/A"):
            return value if value else fallback

        patient_name = p.get_display_name() if p else "No Patient Loaded"
        now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        parts: list[str] = []

        # Title
        parts.append(
            '<h1 style="color:#1976D2; border-bottom:2px solid #1976D2;'
            f' padding-bottom:8px;">Endoscopy Report</h1>'
            f'<h2 style="color:#333;">{patient_name}</h2>'
            f'<p style="color:#666;">Generated: {now}</p><hr>'
        )

        if p:
            # Patient demographics
            parts.append('<h3 style="color:#1976D2;">Patient Information</h3>')
            parts.append(self._html_table([
                ("Name", f"{field(p.first_name)} {field(p.last_name)}"),
                ("Date of Birth", field(p.date_of_birth)),
                ("Gender", field(p.gender)),
                ("Contact", field(p.contact_number)),
                ("Email", field(p.email)),
                ("Address", ", ".join(filter(None, [
                    p.street_address, p.city, p.state_province,
                    p.postal_code, p.country,
                ])) or "N/A"),
            ]))

            # Medical info
            parts.append('<h3 style="color:#1976D2;">Medical Information</h3>')
            for label, value in [
                ("Medical History", field(p.medical_history)),
                ("Allergies", field(p.allergies)),
                ("Current Medications", field(p.current_medications)),
            ]:
                parts.append(f"<p><b>{label}:</b> {value}</p>")

            # Tumor info
            if any([p.tumor_location, p.tumor_size, p.tumor_type, p.tumor_stage]):
                parts.append('<h3 style="color:#1976D2;">Tumor Information</h3>')
                parts.append(self._html_table([
                    ("Location", field(p.tumor_location)),
                    ("Size", field(p.tumor_size)),
                    ("Type", field(p.tumor_type)),
                    ("Stage", field(p.tumor_stage)),
                ]))
                if p.tumor_description:
                    parts.append(f"<p><b>Description:</b> {p.tumor_description}</p>")

            # Surgery info
            if any([p.surgery_date, p.surgery_type, p.surgeon_name]):
                parts.append('<h3 style="color:#1976D2;">Surgery Information</h3>')
                parts.append(self._html_table([
                    ("Date", field(p.surgery_date)),
                    ("Type", field(p.surgery_type)),
                    ("Surgeon", field(p.surgeon_name)),
                ]))
                if p.surgery_notes:
                    parts.append(f"<p><b>Notes:</b> {p.surgery_notes}</p>")

            # Pre/post surgery notes
            if p.pre_surgery_notes:
                parts.append('<h3 style="color:#1976D2;">Pre-Surgery Notes</h3>')
                parts.append(f"<p>{p.pre_surgery_notes}</p>")
            if p.post_surgery_notes:
                parts.append('<h3 style="color:#1976D2;">Post-Surgery Notes</h3>')
                parts.append(f"<p>{p.post_surgery_notes}</p>")

        # Screenshots
        if screenshots:
            parts.append('<h3 style="color:#1976D2;">Imaging Screenshots</h3>')
            for img_path in screenshots:
                caption = captions.get(img_path.name, "")
                ts_part = img_path.stem.replace("screenshot_", "")
                try:
                    ts_display = datetime.strptime(
                        ts_part, "%Y%m%d_%H%M%S"
                    ).strftime("%B %d, %Y at %I:%M:%S %p")
                except ValueError:
                    ts_display = ts_part

                parts.append(
                    '<div style="margin-bottom:20px; text-align:center;">'
                    f'<img src="{img_path.name}" width="680"><br>'
                    f'<p style="color:#666; font-size:11px;">Captured: {ts_display}</p>'
                    f'<p style="font-style:italic;">'
                    f'{caption if caption else "(No caption)"}</p></div>'
                )
        else:
            parts.append(
                '<p style="color:#999; text-align:center; padding:40px;">'
                "No screenshots have been captured yet.</p>"
            )

        return "".join(parts)

    @staticmethod
    def _html_table(rows: list[tuple[str, str]]) -> str:
        """Build an HTML table from label/value pairs."""
        lines = [
            '<table cellpadding="4" cellspacing="0"'
            ' style="width:100%; border-collapse:collapse;">'
        ]
        for label, value in rows:
            lines.append(
                f'<tr><td style="font-weight:bold; width:160px;'
                f' border-bottom:1px solid #EEE; padding:4px;">{label}</td>'
                f'<td style="border-bottom:1px solid #EEE;'
                f' padding:4px;">{value}</td></tr>'
            )
        lines.append("</table><br>")
        return "".join(lines)

    # ------------------------------------------------------------------
    # PDF export
    # ------------------------------------------------------------------

    def _export_pdf(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from PyQt6.QtPrintSupport import QPrinter

        if not self._export_dir:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Patient", "Select a patient first.")
            return

        default_name = "report"
        if self._patient:
            default_name = self._patient.get_display_name().replace(" ", "_")
        default_name += f"_{datetime.now().strftime('%Y%m%d')}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report as PDF",
            str(self._export_dir / default_name),
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        self._editor.document().print(printer)

        QMessageBox.information(
            self, "Export Complete", f"Report saved to:\n{file_path}"
        )
