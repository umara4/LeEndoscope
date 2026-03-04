"""
Geometry persistence mixins for PyQt6 windows.

DebouncedGeometryMixin: Debounces geometry saves so that during drag/resize,
only one save happens every GEOMETRY_DEBOUNCE_MS milliseconds instead of ~60/sec.

CenteredWidgetMixin: Original mixin from ui_windows.py with debounced saves.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QEvent, QTimer

from shared.geometry_store import save_geometry, load_geometry, save_start_size, get_start_size
from shared.constants import GEOMETRY_DEBOUNCE_MS, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT


class DebouncedGeometryMixin:
    """Mixin for QWidget/QMainWindow that debounces geometry saves.

    Instead of writing the geometry JSON file on every resize/move event
    (dozens per second while dragging), this uses a single-shot QTimer
    to batch saves. Result: ~3 writes/sec max instead of ~60.
    """
    _geo_timer: QTimer = None

    def _schedule_geometry_save(self):
        """Schedule a debounced geometry save."""
        if self._geo_timer is None:
            self._geo_timer = QTimer()
            self._geo_timer.setSingleShot(True)
            self._geo_timer.timeout.connect(self._do_geometry_save)
        self._geo_timer.start(GEOMETRY_DEBOUNCE_MS)

    def _do_geometry_save(self):
        """Actually write geometry to disk."""
        try:
            geo = self.geometry()
            save_geometry((geo.x(), geo.y(), geo.width(), geo.height()))
        except Exception:
            pass

    def _flush_geometry_save(self):
        """Immediately save geometry (call in closeEvent)."""
        if self._geo_timer is not None:
            self._geo_timer.stop()
        self._do_geometry_save()


class CenteredWidgetMixin(DebouncedGeometryMixin):
    """Mixin providing centered window placement, geometry persistence,
    and smooth window transitions.

    Replaces the original CenteredWidgetMixin from ui_windows.py with
    debounced geometry saves.
    """

    def restore_geometry_if_available(self):
        """Restore saved geometry or center window with default size."""
        g = load_geometry()
        screen = self.screen().availableGeometry()
        # If stored geometry looks like fullscreen, ignore it
        if g:
            gx, gy, gw, gh = g
            try:
                if gw >= int(screen.width() * 0.95) or gh >= int(screen.height() * 0.95):
                    g = None
            except Exception:
                pass
        if g:
            self.setGeometry(*g)
        else:
            start_size = get_start_size()
            if start_size:
                width, height = start_size
            else:
                width = DEFAULT_WINDOW_WIDTH
                height = DEFAULT_WINDOW_HEIGHT
                width = min(width, screen.width())
                height = min(height, screen.height())
                save_start_size(width, height)
            x = (screen.width() - width) // 2
            y = (screen.height() - height) // 2
            self.setGeometry(x, y, width, height)

    def apply_geometry_from(self, other: QWidget):
        """Copy geometry and window state from another widget."""
        try:
            geo = other.geometry()
            self.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
            self.setWindowState(other.windowState())
        except Exception:
            self.restore_geometry_if_available()

    def save_geometry_on_close(self):
        """Save geometry immediately (for use in closeEvent)."""
        self._flush_geometry_save()

    def create_centered_wrapper(self, inner_layout):
        """Wrap a layout in a vertical layout centered in the window."""
        from PyQt6.QtWidgets import QVBoxLayout
        from PyQt6.QtCore import Qt
        wrapper = QVBoxLayout()
        wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper.addLayout(inner_layout)
        return wrapper

    def resizeEvent(self, event):
        self._schedule_geometry_save()
        QWidget.resizeEvent(self, event)

    def moveEvent(self, event):
        self._schedule_geometry_save()
        QWidget.moveEvent(self, event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self._schedule_geometry_save()
        QWidget.changeEvent(self, event)

    def transition_to(self, new_window: QWidget, delay_ms: int = 120):
        """Show new_window with copied geometry and close this window after a delay."""
        try:
            new_window.apply_geometry_from(self)
        except Exception:
            try:
                copy_geometry_state(self, new_window)
            except Exception:
                pass
        new_window.show()

        def _close_old():
            try:
                self.save_geometry_on_close()
            except Exception:
                pass
            try:
                self.close()
            except Exception:
                pass

        QTimer.singleShot(delay_ms, _close_old)


def copy_geometry_state(src: QWidget, dst: QWidget):
    """Copy geometry and window state from src to dst.

    Used for windows that do not include the CenteredWidgetMixin.
    """
    try:
        geo = src.geometry()
        dst.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
        dst.setWindowState(src.windowState())
    except Exception:
        pass
