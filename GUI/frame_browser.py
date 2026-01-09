import os
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QScrollArea,
    QWidget, QGridLayout, QLabel, QCheckBox, QPushButton, QMessageBox, QHBoxLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class FrameBrowser(QDialog):
    def __init__(self, segments, video_id=None, parent=None, initial_selection=None):
        """
        segments: list of tuples -> [(segment_name, folder_path), ...]
        video_id: unique identifier for the loaded video (e.g., absolute path)
        initial_selection: optional seed data to merge for this video
        """
        super().__init__(parent)
        self.setWindowTitle("Extracted Frames")
        self.resize(900, 650)
        self.video_id = video_id or "__default__"
        self.initial_selection = initial_selection or {}
        
        # Set dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #404040;
            }
            QWidget {
                background-color: #404040;
                color: #ffffff;
            }
            QFrame {
                background-color: #606060;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
            QLabel {
                color: #ffffff;
                background-color: transparent;
            }
            QTabWidget::pane {
                border: 1px solid #606060;
                background-color: #404040;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #606060;
                color: #ffffff;
                padding: 8px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #808080;
            }
            QTabBar::tab:hover {
                background-color: #707070;
            }
            QScrollArea {
                background-color: #404040;
                border: 1px solid #606060;
            }
            QCheckBox {
                color: #ffffff;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #a0a0a0;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #45a049;
            }
        """)

        self.selection_file = "frame_selection.json"
        self.store, self.selected_frames = self._load_selection()
        self.segment_folders = {folder for _, folder in segments}
        self._merge_initial_selection()

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
                # Filtering algorithm hook (disabled):
                # if not custom_filter(path):
                #     self.selected_frames[folder][img_name]["checked"] = False

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
            self.tabs.addTab(scroll, seg_name)

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
        total_checked, total_images = self._compute_counts()
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
        self.store.setdefault("videos", {})[self.video_id] = self.selected_frames
        self._save_selection()
        total_checked, total_images = self._compute_counts()
        self._update_summary(total_checked, total_images)
        QMessageBox.information(self, "Selection Saved", f"{total_checked} of {total_images} frames marked for use.")
        # Close the browser after saving so caller resumes automatically
        try:
            self.accept()
        except Exception:
            try:
                self.close()
            except Exception:
                pass

    def _update_summary(self, checked, total):
        self.summary_label.setText(f"Selected: {checked} / {total}")

    def closeEvent(self, event):
        # Persist selections automatically when closing the dialog
        try:
            self.store.setdefault("videos", {})[self.video_id] = self.selected_frames
            self._save_selection()
        except Exception:
            pass
        super().closeEvent(event)

    def _load_selection(self):
        # Store shape: {"videos": {video_id: {folder: {img: {...}}}}}
        base = {"videos": {}}
        if os.path.exists(self.selection_file):
            try:
                with open(self.selection_file, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "videos" in data and isinstance(data["videos"], dict):
                    base = {"videos": data["videos"]}
                elif isinstance(data, dict):
                    # Legacy shape: {folder: [imgs] or {img: meta}}
                    migrated = {}
                    for folder, val in data.items():
                        if isinstance(val, list):
                            migrated[folder] = {img: {"checked": True, "modified": False} for img in val}
                        elif isinstance(val, dict):
                            migrated[folder] = {}
                            for img, meta in val.items():
                                if isinstance(meta, dict):
                                    migrated[folder][img] = {
                                        "checked": bool(meta.get("checked", True)),
                                        "modified": bool(meta.get("modified", False))
                                    }
                                else:
                                    migrated[folder][img] = {"checked": bool(meta), "modified": False}
                    base = {"videos": {"__legacy__": migrated}}
            except Exception:
                base = {"videos": {}}
        videos = base.setdefault("videos", {})
        selected = videos.setdefault(self.video_id, {})
        return base, selected

    def _merge_initial_selection(self):
        """Merge any provided seed selection for this video without overwriting saved choices."""
        for folder, images in self.initial_selection.items():
            target = self.selected_frames.setdefault(folder, {})
            for img, meta in images.items():
                if img not in target:
                    checked = meta.get("checked", True) if isinstance(meta, dict) else bool(meta)
                    target[img] = {"checked": bool(checked), "modified": False}

    def _compute_counts(self):
        total_checked, total_images = 0, 0
        for folder_key, images in self.selected_frames.items():
            if self.segment_folders and folder_key not in self.segment_folders:
                continue
            for _, data in images.items():
                total_images += 1
                if data.get("checked"):
                    total_checked += 1
        return total_checked, total_images

    def _save_selection(self):
        try:
            with open(self.selection_file, "w") as f:
                json.dump(self.store, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save selection:\n{e}")
