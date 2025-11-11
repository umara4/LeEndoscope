import os
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QScrollArea,
    QWidget, QGridLayout, QLabel, QCheckBox, QPushButton, QMessageBox, QHBoxLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class FrameBrowser(QDialog):
    def __init__(self, segments, parent=None):
        """
        segments: list of tuples -> [(segment_name, folder_path), ...]
        """
        super().__init__(parent)
        self.setWindowTitle("Extracted Frames")
        self.resize(900, 650)

        self.selection_file = "frame_selection.json"
        self.selected_frames = self._load_selection()

        main_layout = QVBoxLayout(self)

        # Summary label
        self.summary_label = QLabel("")
        main_layout.addWidget(self.summary_label)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        total_checked, total_images = 0, 0

        # Build tabs per segment
        for seg_name, folder in segments:
            if not os.path.exists(folder):
                continue

            if folder not in self.selected_frames:
                self.selected_frames[folder] = {}

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            container = QWidget()
            grid = QGridLayout(container)

            images = sorted([f for f in os.listdir(folder) if f.lower().endswith(".jpg")])
            for i, img_name in enumerate(images):
                path = os.path.join(folder, img_name)

                # Ensure image entry exists with defaults
                if img_name not in self.selected_frames[folder]:
                    self.selected_frames[folder][img_name] = {"checked": True, "modified": False}

                # Thumbnail
                thumb = QPixmap(path).scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio)
                thumb_label = QLabel()
                thumb_label.setPixmap(thumb)
                thumb_label.setToolTip(path)

                # Checkbox
                checkbox = QCheckBox("Use")
                checkbox.setChecked(self.selected_frames[folder][img_name]["checked"])
                checkbox.stateChanged.connect(
                    lambda state, f=folder, img=img_name: self.toggle_selection(f, img, state)
                )

                # Layout cell
                cell_layout = QVBoxLayout()
                cell_layout.addWidget(thumb_label)
                cell_layout.addWidget(checkbox)

                cell = QWidget()
                cell.setLayout(cell_layout)
                grid.addWidget(cell, i // 4, i % 4)

                # Double-click preview
                thumb_label.mouseDoubleClickEvent = lambda event, p=path: self.open_full_preview(p)

                total_images += 1
                if self.selected_frames[folder][img_name]["checked"]:
                    total_checked += 1

            scroll.setWidget(container)
            self.tabs.addTab(scroll, seg_name)  # ✅ clean segment name

        # Footer with actions
        action_bar = QHBoxLayout()
        save_btn = QPushButton("Save Selection")
        save_btn.clicked.connect(self.save_selection)
        action_bar.addWidget(save_btn)
        main_layout.addLayout(action_bar)

        self._update_summary(total_checked, total_images)

    def toggle_selection(self, folder, img_name, state):
        prev_checked = self.selected_frames[folder][img_name]["checked"]
        new_checked = (state == Qt.CheckState.Checked.value)

        self.selected_frames[folder][img_name]["checked"] = new_checked
        if new_checked != prev_checked:
            self.selected_frames[folder][img_name]["modified"] = True

        # Update summary live
        total_checked, total_images = 0, 0
        for folder_key, images in self.selected_frames.items():
            for _, data in images.items():
                total_images += 1
                if data["checked"]:
                    total_checked += 1
        self._update_summary(total_checked, total_images)

    def open_full_preview(self, path):
        preview = QDialog(self)
        preview.setWindowTitle(os.path.basename(path))
        preview.resize(800, 600)

        layout = QVBoxLayout(preview)
        pixmap = QPixmap(path).scaled(760, 560, Qt.AspectRatioMode.KeepAspectRatio)
        label = QLabel()
        label.setPixmap(pixmap)
        layout.addWidget(label)

        preview.exec()

    def save_selection(self):
        self._save_selection(self.selected_frames)
        total_checked, total_images = 0, 0
        for folder_key, images in self.selected_frames.items():
            for _, data in images.items():
                total_images += 1
                if data["checked"]:
                    total_checked += 1
        self._update_summary(total_checked, total_images)
        QMessageBox.information(self, "Selection Saved", f"{total_checked} of {total_images} frames marked for use.")

    def _update_summary(self, checked, total):
        self.summary_label.setText(f"Selected: {checked} / {total}")

    def _load_selection(self):
        if os.path.exists(self.selection_file):
            try:
                with open(self.selection_file, "r") as f:
                    data = json.load(f)
                # 🔧 Migration: convert old list format to dict
                for folder, val in data.items():
                    if isinstance(val, list):
                        data[folder] = {img: {"checked": True, "modified": False} for img in val}
                return data
            except Exception:
                return {}
        return {}

    def _save_selection(self, data):
        try:
            with open(self.selection_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save selection:\n{e}")