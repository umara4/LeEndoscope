"""
Recording service: manages camera recording lifecycle.

Extracted from VideoWindow recording methods.
Handles:
- VideoWriter creation and frame writing at fixed FPS
- Frame timestamp CSV logging
- Serial CSV logging coordination
- Post-recording file organization (move to Raw Data/)
"""
from __future__ import annotations
import csv
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from shared.constants import DEFAULT_RECORDING_FPS


class RecordingService:
    """Manages a single recording session.

    Typical lifecycle:
        svc = RecordingService()
        svc.start(cap, session_dir, fps=30)
        while recording:
            svc.write_frame(frame)     # or svc.tick(cap) for auto-read
        svc.stop()
    """

    def __init__(self):
        self.is_recording: bool = False
        self.recording_file_path: Optional[str] = None

        self._writer: Optional[cv2.VideoWriter] = None
        self._out_fps: float = DEFAULT_RECORDING_FPS
        self._frame_interval: float = 1.0 / self._out_fps
        self._start_perf: Optional[float] = None
        self._next_write_t: float = 0.0
        self._latest_frame = None
        self._started_logged: bool = False

        # Frame timestamp CSV
        self._frame_ts_fp = None
        self._frame_ts_writer = None
        self._frame_index: int = 0
        self._last_frame_ts_ms: float = 0.0
        self.frame_csv_path: Optional[str] = None

        # Recording start time (host microseconds)
        self.record_start_host_us: Optional[float] = None

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------
    def start(self, cap: cv2.VideoCapture, session_dir: Path,
              fps: float = DEFAULT_RECORDING_FPS) -> Optional[str]:
        """Begin recording. Returns the output video path or None on failure."""
        ret, frame = cap.read()
        if not ret:
            return None

        h, w = frame.shape[:2]
        session_dir.mkdir(parents=True, exist_ok=True)
        out_path = session_dir / "Recording.mp4"

        self._out_fps = float(fps)
        self._frame_interval = 1.0 / self._out_fps

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, self._out_fps, (w, h))
        if not writer.isOpened():
            return None

        self._writer = writer
        self.is_recording = True
        self.recording_file_path = str(out_path)
        self._start_perf = time.perf_counter()
        self.record_start_host_us = float(self._start_perf * 1_000_000.0)
        self._latest_frame = frame
        self._next_write_t = self._start_perf
        self._started_logged = False
        self._frame_index = 0
        self._last_frame_ts_ms = 0.0

        # Start frame timestamp CSV
        self._start_frame_ts_logging(out_path)

        # Write first frame immediately
        writer.write(frame)
        self._log_frame_timestamp(0.0)
        self._next_write_t = time.perf_counter() + self._frame_interval
        self._started_logged = True

        return str(out_path)

    def stop(self) -> dict:
        """Stop recording and organize files. Returns summary dict."""
        if not self.is_recording:
            return {}

        frame_count = self._frame_index
        frame_last_ms = self._last_frame_ts_ms if frame_count > 0 else None

        # Stop frame timestamp CSV
        self._stop_frame_ts_logging()

        # Release writer
        if self._writer is not None:
            try:
                self._writer.release()
            except Exception:
                pass
            self._writer = None

        self.is_recording = False

        # Move files to Raw Data/
        self._organize_raw_data()

        return {
            "frame_count": frame_count,
            "frame_last_ms": frame_last_ms,
            "recording_file_path": self.recording_file_path,
        }

    # ------------------------------------------------------------------
    # Frame writing
    # ------------------------------------------------------------------
    def tick(self, cap: cv2.VideoCapture) -> Optional[object]:
        """Called from a QTimer. Reads a frame, writes at fixed FPS.
        Returns the latest frame (for preview) or None."""
        if not self.is_recording:
            return None
        if cap is None or not cap.isOpened():
            return None

        ret, frame = cap.read()
        if ret:
            self._latest_frame = frame

        # Write frames at fixed output FPS
        now = time.perf_counter()
        loops = 0
        while now >= self._next_write_t and loops < 5:
            lf = self._latest_frame
            if lf is None:
                break
            try:
                if self._writer is not None:
                    self._writer.write(lf)
                    if self._start_perf is not None:
                        elapsed_ms = (time.perf_counter() - self._start_perf) * 1000.0
                    else:
                        elapsed_ms = 0.0
                    self._log_frame_timestamp(elapsed_ms)
            except Exception:
                break
            self._next_write_t += self._frame_interval
            loops += 1

        return self._latest_frame if ret else None

    # ------------------------------------------------------------------
    # Timeline info
    # ------------------------------------------------------------------
    @property
    def frame_count(self) -> int:
        return self._frame_index

    @property
    def out_fps(self) -> float:
        return self._out_fps

    @property
    def last_frame_ts_ms(self) -> float:
        return self._last_frame_ts_ms

    # ------------------------------------------------------------------
    # Frame timestamp CSV
    # ------------------------------------------------------------------
    def _start_frame_ts_logging(self, out_video_path: Path):
        csv_path = out_video_path.parent / "FrameTimestamp.csv"
        self._frame_index = 0
        self._last_frame_ts_ms = 0.0
        self._frame_ts_writer = None
        self._frame_ts_fp = None
        try:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._frame_ts_fp = open(csv_path, "w", encoding="utf-8", newline="")
            self._frame_ts_writer = csv.writer(self._frame_ts_fp)
            self._frame_ts_writer.writerow(["frame_index", "timestamp_ms", "timestamp_s"])
            self.frame_csv_path = str(csv_path)
        except Exception:
            self.frame_csv_path = None
            self._frame_ts_writer = None
            self._frame_ts_fp = None

    def _log_frame_timestamp(self, timestamp_ms: float):
        if self._frame_ts_writer is None:
            return
        ts_ms = max(0.0, float(timestamp_ms))
        try:
            self._frame_ts_writer.writerow([
                int(self._frame_index),
                f"{ts_ms:.3f}",
                f"{(ts_ms / 1000.0):.6f}",
            ])
            self._frame_index += 1
            self._last_frame_ts_ms = ts_ms
            # Batch flush: once per second instead of every frame
            now = time.perf_counter()
            if now - getattr(self, '_frame_ts_last_flush', 0.0) >= 1.0:
                if self._frame_ts_fp is not None:
                    self._frame_ts_fp.flush()
                self._frame_ts_last_flush = now
        except Exception:
            pass

    def _stop_frame_ts_logging(self):
        try:
            if self._frame_ts_fp is not None:
                self._frame_ts_fp.close()
        except Exception:
            pass
        self._frame_ts_fp = None
        self._frame_ts_writer = None

    # ------------------------------------------------------------------
    # File organization
    # ------------------------------------------------------------------
    def _organize_raw_data(self):
        """Move recording files to Raw Data/ subfolder."""
        if not self.recording_file_path:
            return
        try:
            rec_path = Path(self.recording_file_path)
            session = rec_path.parent
            raw_data_dir = session / "Raw Data"
            raw_data_dir.mkdir(parents=True, exist_ok=True)

            if rec_path.exists():
                new_rec_path = raw_data_dir / rec_path.name
                shutil.move(str(rec_path), str(new_rec_path))
                self.recording_file_path = str(new_rec_path)

            frame_csv = session / "FrameTimestamp.csv"
            if frame_csv.exists():
                shutil.move(str(frame_csv), str(raw_data_dir / "FrameTimestamp.csv"))

            imu_csv = session / "IMUTimeStamp.csv"
            if imu_csv.exists():
                shutil.move(str(imu_csv), str(raw_data_dir / "IMUTimeStamp.csv"))
        except Exception:
            pass
