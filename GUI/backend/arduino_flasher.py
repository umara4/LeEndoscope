"""
ArduinoFlasher QThread for async compile and upload.

Extracted from video_window.py ArduinoFlasher class (lines 288-362).
Keeps UI responsive while flashing firmware to Arduino/ESP32.
"""
from __future__ import annotations
import subprocess
import time

from PyQt6.QtCore import QThread, pyqtSignal


class ArduinoFlasher(QThread):
    """Async Arduino flashing in a separate thread to keep UI responsive."""
    output_line = pyqtSignal(str)        # Emits output lines in real-time
    finished = pyqtSignal(int, str)      # (return_code, final_message)

    def __init__(self, cmd: list[str], timeout_s: float = 180.0):
        super().__init__()
        self.cmd = cmd
        self.timeout_s = timeout_s

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
        except Exception as e:
            self.finished.emit(1, f"Failed to start command: {e}")
            return

        collected = []
        start_t = time.time()
        try:
            while True:
                if proc.stdout is not None:
                    try:
                        line = proc.stdout.readline()
                    except Exception:
                        break
                else:
                    line = ""

                if line:
                    collected.append(line)
                    self.output_line.emit(line.rstrip("\r\n"))

                ret = proc.poll()
                if ret is not None:
                    break

                if (time.time() - start_t) > float(self.timeout_s):
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    self.finished.emit(1, "Command timed out")
                    return

                time.sleep(0.01)

            # Read any remaining output
            try:
                if proc.stdout is not None:
                    remaining = proc.stdout.read() or ""
                    if remaining:
                        collected.append(remaining)
                        for remaining_line in remaining.split("\n"):
                            if remaining_line:
                                self.output_line.emit(remaining_line.rstrip("\r\n"))
            except Exception:
                pass

            output_text = "".join(collected).strip()
            self.finished.emit(int(proc.returncode or 0), output_text)
        finally:
            try:
                if proc.stdout is not None:
                    proc.stdout.close()
            except Exception:
                pass
