"""Frame extraction utilities.

Adds an optional sidecar CSV (frame name -> timestamp) when extracting.
"""

import csv
import cv2
import os


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
            "frame_name",
            "video_frame_index",
            "timestamp_ms",
            "timestamp_s",
            "timestamp_hhmmss_ms",
        ])

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Show preview in GUI
            if preview_callback:
                preview_callback(frame)

            # Save every Nth frame
            if frame_count % interval == 0:
                frame_name = f"frame_{saved_count:05d}.jpg"
                filename = os.path.join(output_folder, frame_name)
                cv2.imwrite(filename, frame)

                if csv_writer is not None:
                    pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    # CAP_PROP_POS_MSEC can be unreliable; fall back to frame_index/fps.
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

            # Update progress
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