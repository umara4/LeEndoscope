from __future__ import annotations

import re
import time
import threading
from typing import Callable, Optional, Tuple, Iterator

try:
    import serial
    import serial.tools.list_ports
except Exception as e:  # pragma: no cover - informative runtime error
    raise ImportError("pyserial is required. Install with: pip install pyserial") from e

NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


class ArduinoReader:
    def __init__(self, port: Optional[str] = None, baud: int = 115200, timeout: float = 1.0,
                 callback: Optional[Callable[[Tuple[float, float, float, float]], None]] = None,
                 line_callback: Optional[Callable[[str], None]] = None,
                 auto_connect: bool = True) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.callback = callback
        # optional raw line callback receives each line read from serial
        self.line_callback = line_callback
        self.ser: Optional[serial.Serial] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if auto_connect:
            self.connect()

    @staticmethod
    def autodetect_port() -> Optional[str]:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            return None
        # prefer ports with common Arduino/USB hints
        for p in ports:
            desc = (p.description or "").lower()
            if "arduino" in desc or "usb" in desc or "cp210x" in desc or "ch340" in desc:
                return p.device
        # fallback to first port
        return ports[0].device

    def connect(self) -> None:
        if self.port is None:
            self.port = self.autodetect_port()
        if self.port is None:
            raise ConnectionError("No serial ports found for Arduino connection")
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        # toggle DTR to reset Arduino (common behavior on many boards)
        try:
            # setDTR(False) then True to generate a reset pulse
            self.ser.setDTR(False)
            time.sleep(0.05)
            self.ser.setDTR(True)
            # wait briefly for MCU to restart and begin sending data
            time.sleep(0.2)
        except Exception:
            # not all serial implementations support DTR control; ignore failures
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
        """Extract first four numeric values from a line and return as (w,x,y,z).

        Raises ValueError if fewer than four numbers are found.
        """
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
        """Blocking read until a valid quaternion line is received or optional timeout occurs."""
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
        # Read raw lines continuously. For each line, invoke line_callback (if any)
        # and also attempt to parse a quaternion and invoke callback(quaternion) when successful.
        while not self._stop_event.is_set():
            try:
                line = self.read_line()
            except Exception:
                continue
            if not line:
                continue
            # emit raw line first
            if self.line_callback:
                try:
                    self.line_callback(line)
                except Exception:
                    pass
            # try parse quaternion and notify quaternion callback
            try:
                q = self.parse_quaternion(line)
                if self.callback:
                    try:
                        self.callback(q)
                    except Exception:
                        pass
            except ValueError:
                # not a quaternion line; ignore
                pass

    def start_background(self) -> None:
        """Start a background thread that calls `line_callback(line)` for each line and
        `callback(quaternion)` when a quaternion is parsed. At least one of the callbacks
        must be provided.
        """
        if self.callback is None and self.line_callback is None:
            raise RuntimeError("No callback provided for background reading")
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Read quaternion data from an Arduino over serial")
    parser.add_argument("--port", help="Serial port (auto-detected if omitted)", default=None)
    parser.add_argument("--baud", help="Baud rate", type=int, default=115200)
    args = parser.parse_args()

    port_display = args.port or ArduinoReader.autodetect_port()
    print(f"Using port: {port_display}  (baud {args.baud})")

    try:
        with ArduinoReader(port=args.port, baud=args.baud) as reader:
            print("Reading quaternions (press Ctrl-C to stop)...")
            for q in reader.iter_quaternions():
                print(f"Quaternion: w={q[0]:.6f}, x={q[1]:.6f}, y={q[2]:.6f}, z={q[3]:.6f}")
    except KeyboardInterrupt:
        print("Stopped by user")
    except Exception as e:
        print(f"Error: {e}")
