"""
Segment list widget and controls.

Manages the list of video segments with add/rename/delete functionality
and timeline highlighting.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QMenu, QInputDialog, QLabel, QLineEdit, QPushButton, QTimeEdit,
    QMessageBox, QComboBox,
)
from PyQt6.QtCore import Qt, QTime, QSize, pyqtSignal

from shared.form_helpers import set_button_enabled_style


class SegmentControls(QWidget):
    """Segment data model + list widget + add/rename/delete."""

    segment_added = pyqtSignal()      # emitted after a segment is added
    segment_deleted = pyqtSignal()    # emitted after a segment is deleted
    segment_renamed = pyqtSignal()    # emitted after a segment is renamed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # The segment list (collapsible)
        self.segment_list = QListWidget()
        self.segment_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.segment_list.customContextMenuRequested.connect(self._show_menu)
        self.segment_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.segment_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.segment_list.setVisible(False)
        layout.addWidget(self.segment_list)

    # --- Segment controls row (lives in video_viewer but calls back here) ---

    def add_segment(self, name: str, start: QTime, end: QTime) -> bool:
        """Add a segment. Returns True on success."""
        if start >= end:
            QMessageBox.warning(self.parent(), "Invalid Segment", "Start time must be before end time.")
            return False
        name = name.strip() or f"Segment {len(self.segments) + 1}"
        seg = {"name": name, "start": start, "end": end}

        # Custom row widget: label on top, fps_combo below
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(4, 4, 4, 4)
        row_layout.setSpacing(4)
        label = QLabel(f"{name}: {start.toString('HH:mm:ss')} \u2192 {end.toString('HH:mm:ss')}")
        fps_combo = QComboBox()
        fps_combo.addItem("Low (1/sec)", 1)
        fps_combo.addItem("Standard (2/sec)", 2)
        fps_combo.addItem("High (5/sec)", 5)
        fps_combo.addItem("Max (10/sec)", 10)
        fps_combo.setCurrentIndex(1)  # default: Standard
        row_layout.addWidget(label)
        row_layout.addWidget(fps_combo)

        seg["fps_combo"] = fps_combo
        seg["label"] = label
        self.segments.append(seg)

        item = QListWidgetItem()
        # Ensure enough vertical space for stacked label + combo
        row.adjustSize()
        hint = row.sizeHint()
        item.setSizeHint(QSize(hint.width(), max(hint.height(), 70)))
        self.segment_list.addItem(item)
        self.segment_list.setItemWidget(item, row)
        self.segment_added.emit()
        if self.segment_list.isVisible():
            self._update_height()
        return True

    def toggle_visible(self) -> bool:
        """Toggle segment list visibility. Returns new visibility state."""
        visible = not self.segment_list.isVisible()
        self.segment_list.setVisible(visible)
        if visible:
            self._update_height()
        return visible

    def set_enabled(self, enabled: bool):
        """Enable or disable the segment list."""
        self.segment_list.setEnabled(enabled)
        if not enabled:
            self.segment_list.setVisible(False)

    def _show_menu(self, pos):
        item = self.segment_list.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.segment_list.mapToGlobal(pos))
        index = self.segment_list.row(item)
        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Rename Segment", "New name:")
            if ok and new_name:
                self.segments[index]["name"] = new_name
                seg = self.segments[index]
                label = seg.get("label")
                if label:
                    label.setText(f"{new_name}: {seg['start'].toString('HH:mm:ss')} \u2192 {seg['end'].toString('HH:mm:ss')}")
                self.segment_renamed.emit()
        elif action == delete_action:
            self.segments.pop(index)
            self.segment_list.takeItem(index)
            if self.segment_list.isVisible():
                self._update_height()
            self.segment_deleted.emit()

    def _update_height(self):
        """Adjust segment list height based on item count.

        Zero segments = zero height (no empty gap).
        Grows to fit all items up to 10 segments; scrolls beyond that.
        """
        count = self.segment_list.count()
        if count == 0:
            self.segment_list.setFixedHeight(0)
            return
        item_height = max(self.segment_list.sizeHintForRow(0), 70)
        total_height = item_height * count + 10
        max_height = item_height * 10 + 10
        self.segment_list.setFixedHeight(min(total_height, max_height))

    def clear(self):
        """Clear all segments."""
        self.segments.clear()
        self.segment_list.clear()
