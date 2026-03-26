"""
Serial port communication service.

Consolidates:
- SerialPortReader from video_window.py (lines 590-773)
- ArduinoReader from Arduino.py

SerialPortReader is the primary class used during recording.
ArduinoReader is preserved for standalone use and backward compatibility.

Thread safety: _ser_lock protects all serial port operations.
"""
from __future__ import annotations

import re
import time
import threading
from collections import deque
from pathlib import Path
from typing import Callable, Optional, Tuple, Iterator, List

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    SERIAL_AVAILABLE = False

from shared.constants import SERIAL_BAUD_RATE, SERIAL_TIMEOUT

NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


# ---------------------------------------------------------------------------
# SerialPortReader  (from video_window.py)
# ---------------------------------------------------------------------------
class SerialPortReader:
    """Single shared serial reader.

    - Always reads lines into a buffer for UI consumption.
    - Optionally logs CSV-like lines to a file when enabled.
    - Thread-safe via _ser_lock on all serial port operations.
    """

    def __init__(self, port: str, baud: int = SERIAL_BAUD_RATE,
                 timeout: float = SERIAL_TIMEOUT) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ser = None
        self._ser_lock = threading.Lock()  # Protects all serial port access

        self._buffer: deque = deque(maxlen=5000)
        self._buf_lock = threading.Lock()

        # Dedicated buffer for SYNC responses so they aren't stolen by
        # pop_lines() (serial monitor) or lost during flush_input().
        self._sync_buffer: deque = deque(maxlen=20)
        self._sync_lock = threading.Lock()

        self._log_fp = None
        self._log_lock = threading.Lock()

        # Time sync (Arduino micros -> host perf_counter micros -> recording-relative ms)
        self._ts_lock = threading.Lock()
        self._sync_offset_us: Optional[float] = None
        self._record_start_host_us: Optional[float] = None
        self._last_logged_ms: Optional[float] = None
        self._logged_rows: int = 0

    def set_time_sync(self, sync_offset_us: Optional[float],
                      record_start_host_us: Optional[float]) -> None:
        with self._ts_lock:
            self._sync_offset_us = sync_offset_us
            self._record_start_host_us = record_start_host_us
            self._last_logged_ms = None
            self._logged_rows = 0

    def get_sync_offset(self) -> Optional[float]:
        with self._ts_lock:
            return self._sync_offset_us

    def update_sync_offset(self, sync_offset_us: Optional[float]) -> None:
        with self._ts_lock:
            self._sync_offset_us = sync_offset_us

    def flush_input(self) -> None:
        """Clear both pyserial RX buffer and in-memory buffer."""
        with self._ser_lock:
            try:
                if self._ser is not None:
                    self._ser.reset_input_buffer()
            except Exception:
                pass
        with self._buf_lock:
            self._buffer.clear()

    def send_line(self, text: str) -> None:
        with self._ser_lock:
            try:
                if self._ser is None:
                    return
                payload = (text.rstrip("\r\n") + "\n").encode("utf-8", errors="ignore")
                self._ser.write(payload)
                self._ser.flush()
            except Exception:
                pass

    def start(self) -> None:
        if not SERIAL_AVAILABLE:
            raise RuntimeError("pyserial is not installed")
        if self._thread and self._thread.is_alive():
            return
        # Open serial WITHOUT toggling DTR/RTS to prevent ESP32 auto-reset
        ser = serial.Serial()
        ser.port = self.port
        ser.baudrate = self.baud
        ser.timeout = self.timeout
        ser.dtr = False
        ser.rts = False
        ser.open()
        with self._ser_lock:
            self._ser = ser
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.disable_logging()
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        with self._ser_lock:
            try:
                if self._ser is not None and getattr(self._ser, "is_open", False):
                    self._ser.close()
            except Exception:
                pass
            self._ser = None

    def enable_logging(self, csv_path: Path, header: str) -> None:
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_lock:
            self._log_fp = open(csv_path, "w", encoding="utf-8", newline="\n")
            self._log_fp.write(header.rstrip("\n") + "\n")
            self._log_fp.flush()
        with self._ts_lock:
            self._last_logged_ms = None
            self._logged_rows = 0

    def disable_logging(self) -> None:
        with self._log_lock:
            try:
                if self._log_fp is not None:
                    self._log_fp.close()
            except Exception:
                pass
            self._log_fp = None

    def pop_lines(self) -> List[str]:
        with self._buf_lock:
            if not self._buffer:
                return []
            lines = list(self._buffer)
            self._buffer.clear()
            return lines

    def pop_sync_lines(self) -> List[str]:
        """Drain only the dedicated SYNC response buffer.

        This prevents the serial monitor (pop_lines) from stealing SYNC
        responses needed by the sync handshake code.
        """
        with self._sync_lock:
            if not self._sync_buffer:
                return []
            lines = list(self._sync_buffer)
            self._sync_buffer.clear()
            return lines

    def get_logging_stats(self) -> tuple[int, Optional[float]]:
        with self._ts_lock:
            return int(self._logged_rows), self._last_logged_ms

    def _maybe_log_line(self, line: str, host_perf_s: float) -> None:
        """Log an IMU data line using the host clock for the timestamp.

        Args:
            line: Raw serial line from Arduino (format: arduino_us,ax,ay,az,wx,wy,wz)
            host_perf_s: time.perf_counter() captured when line was received
        """
        if not line:
            return
        low = line.strip().lower()
        if low.startswith("timestamp") or low.startswith("t_us"):
            return
        if "," not in line:
            return
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            return

        try:
            # Use host clock (same clock as frame timestamps) to avoid
            # drift between Arduino crystal and PC clock.
            with self._ts_lock:
                if self._record_start_host_us is not None:
                    host_us = host_perf_s * 1_000_000.0
                    rel_ms = (host_us - float(self._record_start_host_us)) / 1000.0
                else:
                    # Fallback: use Arduino timestamp as raw microseconds
                    rel_ms = float(parts[0]) / 1000.0

                if rel_ms < 0:
                    rel_ms = 0.0

                parts[0] = f"{rel_ms:.3f}"
                self._last_logged_ms = float(rel_ms)
                self._logged_rows += 1
        except Exception:
            pass

        with self._log_lock:
            if self._log_fp is None:
                return
            try:
                self._log_fp.write(",".join(parts[:7]) + "\n")
                self._log_fp.flush()
            except Exception:
                pass

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._ser_lock:
                ser = self._ser
            try:
                raw = ser.readline() if ser is not None else b""
            except Exception:
                continue
            if not raw:
                continue

            # Capture host clock immediately after receiving data —
            # same clock source as frame timestamps (time.perf_counter)
            host_perf_s = time.perf_counter()

            try:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            except Exception:
                line = str(raw).rstrip("\r\n")

            # Route SYNC responses to dedicated buffer (not consumed by pop_lines/serial monitor)
            stripped = line.strip()
            if stripped.startswith("SYNC,"):
                with self._sync_lock:
                    self._sync_buffer.append(line)

            with self._buf_lock:
                self._buffer.append(line)

            self._maybe_log_line(line, host_perf_s)


# ---------------------------------------------------------------------------
# ArduinoReader  (from Arduino.py)
# ---------------------------------------------------------------------------
class ArduinoReader:
    """Standalone Arduino serial reader with quaternion parsing.

    Preserved from Arduino.py for backward compatibility and standalone use.
    """

    def __init__(self, port: Optional[str] = None, baud: int = SERIAL_BAUD_RATE,
                 timeout: float = 1.0,
                 callback: Optional[Callable[[Tuple[float, float, float, float]], None]] = None,
                 line_callback: Optional[Callable[[str], None]] = None,
                 auto_connect: bool = True) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.callback = callback
        self.line_callback = line_callback
        self.ser: Optional[serial.Serial] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if auto_connect:
            self.connect()

    @staticmethod
    def autodetect_port() -> Optional[str]:
        if not SERIAL_AVAILABLE:
            return None
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            return None
        for p in ports:
            desc = (p.description or "").lower()
            if "arduino" in desc or "usb" in desc or "cp210x" in desc or "ch340" in desc:
                return p.device
        return ports[0].device

    def connect(self) -> None:
        if not SERIAL_AVAILABLE:
            raise ImportError("pyserial is required. Install with: pip install pyserial")
        if self.port is None:
            self.port = self.autodetect_port()
        if self.port is None:
            raise ConnectionError("No serial ports found for Arduino connection")
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        try:
            self.ser.setDTR(False)
            time.sleep(0.05)
            self.ser.setDTR(True)
            time.sleep(0.2)
        except Exception:
            pass

    def close(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass

    def __enter__(self) -> "ArduinoReader":
        if self.ser is None:
            self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def parse_quaternion(line: str) -> Tuple[float, float, float, float]:
        """Extract first four numeric values from a line and return as (w,x,y,z)."""
        nums = NUM_RE.findall(line)
        if len(nums) < 4:
            raise ValueError("Line does not contain 4 numeric values")
        w, x, y, z = (float(n) for n in nums[:4])
        return w, x, y, z

    def read_line(self) -> str:
        if self.ser is None or not self.ser.is_open:
            self.connect()
        raw = self.ser.readline()
        try:
            return raw.decode("utf-8", errors="replace").strip()
        except Exception:
            return str(raw).strip()

    def read_quaternion(self, timeout: Optional[float] = None) -> Tuple[float, float, float, float]:
        """Blocking read until a valid quaternion line is received or timeout."""
        start = time.time()
        while True:
            line = self.read_line()
            if not line:
                if timeout is not None and (time.time() - start) > timeout:
                    raise TimeoutError("Timeout while waiting for quaternion data")
                continue
            try:
                return self.parse_quaternion(line)
            except ValueError:
                continue

    def iter_quaternions(self) -> Iterator[Tuple[float, float, float, float]]:
        """Generator that yields quaternions as they are read."""
        while True:
            try:
                yield self.read_quaternion()
            except Exception:
                break

    def _background_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                line = self.read_line()
            except Exception:
                continue
            if not line:
                continue
            if self.line_callback:
                try:
                    self.line_callback(line)
                except Exception:
                    pass
            try:
                q = self.parse_quaternion(line)
                if self.callback:
                    try:
                        self.callback(q)
                    except Exception:
                        pass
            except ValueError:
                pass

    def start_background(self) -> None:
        """Start a background thread for continuous reading."""
        if self.callback is None and self.line_callback is None:
            raise RuntimeError("No callback provided for background reading")
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()
