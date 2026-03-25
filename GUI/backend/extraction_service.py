"""
Segment extraction service with cooperative shutdown.

Extracted from video_window.py SegmentExtractor (lines 364-588)
and extraction.py extract_frames().

Key improvements:
- Cooperative shutdown via threading.Event (replaces worker.terminate())
- Progress signal throttled to integer-% changes only
"""
from __future__ import annotations
import csv
import os
import threading
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from backend.frame_quality import calculate_snr, calculate_sharpness, eval_frames
from shared.constants import SNR_THRESHOLD, SHARPNESS_THRESHOLD


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _load_frame_timestamps(session_dir) -> dict:
    """Load frame timestamps from Raw Data/FrameTimestamp.csv.

    Returns dict mapping frame_index -> timestamp_ms.
    """
    frame_ts = {}
    if not session_dir:
        return frame_ts
    try:
        ts_path = Path(session_dir) / "Raw Data" / "FrameTimestamp.csv"
        if not ts_path.exists():
            return frame_ts
        with open(ts_path, "r", encoding="utf-8") as fp:
            reader = csv.reader(fp)
            next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    try:
                        frame_ts[int(row[0])] = float(row[1])
                    except Exception:
                        pass
    except Exception:
        pass
    return frame_ts


def _load_imu_data(session_dir) -> list:
    """Load IMU data from Raw Data/IMUTimeStamp.csv.

    Returns list of (timestamp_ms, [sensor values]).
    """
    imu_data = []
    if not session_dir:
        return imu_data
    try:
        imu_path = Path(session_dir) / "Raw Data" / "IMUTimeStamp.csv"
        if not imu_path.exists():
            return imu_data
        with open(imu_path, "r", encoding="utf-8") as fp:
            reader = csv.reader(fp)
            next(reader, None)
            for row in reader:
                if len(row) >= 7:
                    try:
                        ts_ms = float(row[0].strip())
                        vals = [float(row[i].strip()) for i in range(1, len(row))]
                        imu_data.append((ts_ms, vals))
                    except Exception:
                        pass
    except Exception:
        pass
    return imu_data


def _get_averaged_imu(target_ts_ms, imu_data, k=10):
    """Find k closest IMU samples by timestamp and return their average."""
    if not imu_data:
        return None
    distances = [(abs(ts - target_ts_ms), idx) for idx, (ts, _) in enumerate(imu_data)]
    distances.sort()
    closest_indices = [idx for _, idx in distances[:k]]
    if not closest_indices:
        return None
    num_vals = len(imu_data[0][1])
    sums = [0.0] * num_vals
    for idx in closest_indices:
        _, vals = imu_data[idx]
        for i in range(num_vals):
            sums[i] += vals[i]
    count = len(closest_indices)
    return [s / count for s in sums]


class SegmentExtractor(QThread):
    """Extract frames from a video segment with IMU averaging.

    Emits progress as (segment_name, 0-100) and finished_parsing(segment_name).
    Supports cooperative shutdown via request_stop().
    """
    progress = pyqtSignal(tuple)          # (segment_name, progress_value)
    finished_parsing = pyqtSignal(str)     # segment name when done

    def __init__(
        self,
        video_path: str,
        frames_output_folder: str,
        start_frame: int,
        end_frame: int,
        fps: int = 2,
        name: str = "",
        session_dir=None,
    ):
        super().__init__()
        self.video_path = video_path
        self.output_folder = frames_output_folder
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.fps = fps
        self.name = name
        self.session_dir = session_dir
        self._stop_event = threading.Event()

    def request_stop(self):
        """Request cooperative shutdown (replaces terminate())."""
        self._stop_event.set()

    def run(self):
        os.makedirs(self.output_folder, exist_ok=True)

        recording_frame_ts = _load_frame_timestamps(self.session_dir)
        recording_imu_data = _load_imu_data(self.session_dir)

        # Prepare averaged IMU CSV in the segment folder alongside frames
        imu_output_fp = None
        imu_output_writer = None
        if recording_imu_data:
            try:
                imu_output_path = Path(self.output_folder) / "averaged_imu.csv"
                imu_output_fp = open(imu_output_path, "w", encoding="utf-8", newline="")
                imu_output_writer = csv.writer(imu_output_fp)
                imu_output_writer.writerow([
                    "frame_name", "frame_timestamp_ms",
                    "avg_AX", "avg_AY", "avg_AZ",
                    "avg_WX", "avg_WY", "avg_WZ"
                ])
            except Exception:
                imu_output_fp = None
                imu_output_writer = None

        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

        video_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        interval = max(1, int(video_fps // self.fps)) if self.fps > 0 and video_fps > 0 else 1
        frame_count, saved_count = self.start_frame, 0
        last_emitted_pct = -1

        try:
            total_span = max(1, self.end_frame - self.start_frame)
            while frame_count < self.end_frame:
                if self._stop_event.is_set():
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % interval == 0:
                    frame_name = f"Frame{saved_count + 1}.png"
                    filename = os.path.join(self.output_folder, frame_name)
                    cv2.imwrite(filename, frame)

                    pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if (not pos_msec or pos_msec <= 0) and video_fps > 0:
                        pos_msec = (frame_count * 1000.0) / video_fps

                    recording_ts_ms = recording_frame_ts.get(frame_count, pos_msec)

                    if imu_output_writer and recording_imu_data:
                        try:
                            avg_imu = _get_averaged_imu(recording_ts_ms, recording_imu_data, k=10)
                            if avg_imu:
                                imu_output_writer.writerow([
                                    frame_name, f"{recording_ts_ms:.3f}",
                                ] + [f"{v:.6f}" for v in avg_imu])
                        except Exception:
                            pass

                    saved_count += 1

                # Throttle progress: emit only when integer % changes
                progress_val = int(((frame_count - self.start_frame) / total_span) * 100)
                if progress_val != last_emitted_pct:
                    self.progress.emit((self.name, progress_val))
                    last_emitted_pct = progress_val

                frame_count += 1
        finally:
            try:
                if imu_output_fp is not None:
                    imu_output_fp.close()
            except Exception:
                pass

        cap.release()

        if not self._stop_event.is_set():
            selected, rejected = eval_frames(self.output_folder)
            self.finished_parsing.emit(self.name)


# ---------------------------------------------------------------------------
# WholeVideoExtractor -- extracts every frame from the entire video
# ---------------------------------------------------------------------------
class WholeVideoExtractor(QThread):
    """Extract ALL frames from a video (every single frame).

    Saves Frame1.png, Frame2.png, ... into the output folder.
    Creates frame_index.csv mapping frame number -> frame name -> timestamp_ms.
    Emits progress(int 0-100) and finished(bool success).
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool)

    def __init__(self, video_path: str, output_folder: str, session_dir=None):
        super().__init__()
        self.video_path = video_path
        self.output_folder = output_folder
        self.session_dir = session_dir
        self._stop_event = threading.Event()

    def request_stop(self):
        self._stop_event.set()

    def run(self):
        os.makedirs(self.output_folder, exist_ok=True)

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.finished.emit(False)
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        recording_frame_ts = _load_frame_timestamps(self.session_dir)

        index_csv_path = os.path.join(self.output_folder, "frame_index.csv")
        csv_fp = open(index_csv_path, "w", encoding="utf-8", newline="")
        csv_writer = csv.writer(csv_fp)
        csv_writer.writerow(["frame_number", "frame_name", "timestamp_ms"])

        frame_idx = 0
        last_emitted_pct = -1

        try:
            while True:
                if self._stop_event.is_set():
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                frame_name = f"Frame{frame_idx + 1}.png"
                filepath = os.path.join(self.output_folder, frame_name)
                cv2.imwrite(filepath, frame)

                pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                if (not pos_msec or pos_msec <= 0) and video_fps > 0:
                    pos_msec = (frame_idx * 1000.0) / video_fps
                recording_ts_ms = recording_frame_ts.get(frame_idx, pos_msec)

                csv_writer.writerow([frame_idx, frame_name, f"{recording_ts_ms:.3f}"])

                if total_frames > 0:
                    pct = int((frame_idx / total_frames) * 100)
                    if pct != last_emitted_pct:
                        self.progress.emit(pct)
                        last_emitted_pct = pct

                frame_idx += 1
        finally:
            csv_fp.close()
            cap.release()

        if not self._stop_event.is_set():
            eval_frames(self.output_folder)
            self.finished.emit(True)
        else:
            self.finished.emit(False)


# ---------------------------------------------------------------------------
# SegmentCSVGenerator -- creates per-segment CSV referencing extracted frames
# ---------------------------------------------------------------------------
class SegmentCSVGenerator:
    """Generate a CSV for a segment mapping to already-extracted whole-video frames.

    Filters frames within the segment's time range and subsamples at the
    segment's extraction FPS. Includes averaged IMU data per selected frame.
    """

    def __init__(
        self,
        frames_index_csv: str,
        segment_output_dir: str,
        start_frame: int,
        end_frame: int,
        extraction_fps: int,
        video_fps: float,
        segment_name: str,
        session_dir=None,
    ):
        self.frames_index_csv = frames_index_csv
        self.segment_output_dir = segment_output_dir
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.extraction_fps = extraction_fps
        self.video_fps = video_fps
        self.segment_name = segment_name
        self.session_dir = session_dir

    def generate(self) -> int:
        """Generate segment_frames.csv. Returns number of selected frames."""
        os.makedirs(self.segment_output_dir, exist_ok=True)

        # Load the whole-video frame index
        frame_index = []
        with open(self.frames_index_csv, "r", encoding="utf-8") as fp:
            reader = csv.reader(fp)
            next(reader, None)
            for row in reader:
                if len(row) >= 3:
                    frame_index.append((int(row[0]), row[1], float(row[2])))

        # Filter to segment range
        segment_frames = [
            (fn, name, ts) for fn, name, ts in frame_index
            if self.start_frame <= fn < self.end_frame
        ]

        # Subsample at extraction FPS
        interval = max(1, int(self.video_fps / self.extraction_fps)) \
            if self.extraction_fps > 0 and self.video_fps > 0 else 1

        selected = []
        for fn, name, ts in segment_frames:
            relative_frame = fn - self.start_frame
            if relative_frame % interval == 0:
                selected.append((fn, name, ts))

        # Load IMU data
        imu_data = _load_imu_data(self.session_dir)

        # Write segment CSV
        frames_dir = str(Path(self.frames_index_csv).parent)
        csv_path = os.path.join(self.segment_output_dir, "segment_frames.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp)
            header = ["frame_number", "frame_name", "timestamp_ms", "frames_dir_path"]
            if imu_data:
                header.extend([
                    "avg_AX", "avg_AY", "avg_AZ",
                    "avg_WX", "avg_WY", "avg_WZ",
                ])
            writer.writerow(header)

            for fn, name, ts in selected:
                row = [fn, name, f"{ts:.3f}", frames_dir]
                if imu_data:
                    avg = _get_averaged_imu(ts, imu_data, k=10)
                    if avg:
                        row.extend([f"{v:.6f}" for v in avg])
                    else:
                        row.extend([""] * len(imu_data[0][1]))
                writer.writerow(row)

        return len(selected)


# ---------------------------------------------------------------------------
# Standalone extract_frames (from extraction.py)
# ---------------------------------------------------------------------------
def _format_timestamp_ms(ms: float) -> str:
    if ms is None:
        return ""
    try:
        total_ms = int(round(float(ms)))
    except Exception:
        return ""
    if total_ms < 0:
        total_ms = 0
    hours, rem = divmod(total_ms, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def extract_frames(
    video_path,
    output_folder,
    frames_per_second=2,
    progress_callback=None,
    preview_callback=None,
    timestamps_csv_name: str = "frame_timestamps.csv",
):
    """Extract frames from a video at the given rate.

    Standalone version (from extraction.py) with optional CSV sidecar.
    """
    os.makedirs(output_folder, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Cannot open video file.")
        return

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = int(fps // frames_per_second) if frames_per_second > 0 and fps > 0 else 1

    frame_count = 0
    saved_count = 0

    timestamps_path = os.path.join(output_folder, timestamps_csv_name) if timestamps_csv_name else None

    csv_fp = None
    csv_writer = None
    if timestamps_path:
        csv_fp = open(timestamps_path, "w", encoding="utf-8", newline="")
        csv_writer = csv.writer(csv_fp)
        csv_writer.writerow([
            "frame_name", "video_frame_index",
            "timestamp_ms", "timestamp_s", "timestamp_hhmmss_ms",
        ])

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if preview_callback:
                preview_callback(frame)

            if frame_count % interval == 0:
                frame_name = f"frame_{saved_count:05d}.jpg"
                filename = os.path.join(output_folder, frame_name)
                cv2.imwrite(filename, frame)

                if csv_writer is not None:
                    pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if (not pos_msec or pos_msec <= 0) and fps > 0:
                        pos_msec = (frame_count * 1000.0) / fps
                    timestamp_s = (pos_msec / 1000.0) if pos_msec is not None else ""
                    csv_writer.writerow([
                        frame_name,
                        frame_count,
                        f"{pos_msec:.3f}" if pos_msec is not None else "",
                        f"{timestamp_s:.6f}" if timestamp_s != "" else "",
                        _format_timestamp_ms(pos_msec),
                    ])

                saved_count += 1

            if progress_callback and total_frames > 0:
                progress_value = int((frame_count / total_frames) * 100)
                progress_callback(progress_value)

            frame_count += 1
    finally:
        if csv_fp is not None:
            try:
                csv_fp.close()
            except Exception:
                pass

    cap.release()
    print(f"Saved {saved_count} frames to {output_folder}")
    if timestamps_path:
        print(f"Wrote timestamps CSV to {timestamps_path}")
