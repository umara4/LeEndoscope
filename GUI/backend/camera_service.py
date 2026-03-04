"""
Camera probe and initialization services.

Moves blocking camera operations off the UI thread:
- CameraProbeWorker: Discovers available camera indices
- CameraInitWorker: Opens a specific camera (cv2.VideoCapture)

Both run in QThread so the GUI remains responsive.
"""
from __future__ import annotations

import cv2
from PyQt6.QtCore import QThread, pyqtSignal

from shared.constants import CAMERA_PROBE_MAX


class CameraProbeWorker(QThread):
    """Probe for available cameras in a background thread.

    Emits finished(list[int]) with the indices of cameras that could be opened.
    """
    finished = pyqtSignal(list)

    def __init__(self, max_index: int = CAMERA_PROBE_MAX):
        super().__init__()
        self._max_index = max_index

    def run(self):
        available = []
        for i in range(self._max_index):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    available.append(i)
                    cap.release()
            except Exception:
                pass
        self.finished.emit(available)


class CameraInitWorker(QThread):
    """Open a specific camera in a background thread.

    Emits finished(cap_or_None, success_bool).
    The caller is responsible for releasing the returned VideoCapture.
    """
    finished = pyqtSignal(object, bool)

    def __init__(self, camera_index: int, width: int = 640, height: int = 480,
                 fps: int = 30):
        super().__init__()
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._fps = fps

    def run(self):
        try:
            cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                self.finished.emit(None, False)
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            cap.set(cv2.CAP_PROP_FPS, self._fps)
            self.finished.emit(cap, True)
        except Exception:
            self.finished.emit(None, False)


def probe_cameras(max_index: int = CAMERA_PROBE_MAX) -> list[int]:
    """Synchronous camera probe (legacy, blocks the calling thread).

    Prefer CameraProbeWorker for UI contexts.
    """
    available = []
    for i in range(max_index):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                available.append(i)
                cap.release()
        except Exception:
            pass
    return available
