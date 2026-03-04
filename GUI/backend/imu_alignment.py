"""
IMU CSV alignment logic.

Extracted from VideoWindow._align_imu_csv_duration.
Scales IMU timestamp column so first=0 and last ~= target_end_ms.
"""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Optional


def align_imu_csv_duration(
    csv_path: Optional[str],
    target_end_ms: Optional[float],
) -> tuple[int, Optional[float], bool]:
    """Scale IMU timestamp column so first=0 and last ~= target_end_ms.

    Returns: (row_count, aligned_last_ms, changed)
    """
    if not csv_path or target_end_ms is None:
        return 0, None, False

    path = Path(csv_path)
    if not path.exists() or target_end_ms < 0:
        return 0, None, False

    try:
        with open(path, "r", encoding="utf-8", newline="") as fp:
            rows = list(csv.reader(fp))
    except Exception:
        return 0, None, False

    if len(rows) <= 1:
        return 0, None, False

    header = rows[0]
    data_rows = rows[1:]

    parsed_ts = []
    for row in data_rows:
        if not row:
            continue
        try:
            parsed_ts.append(float(row[0]))
        except Exception:
            continue

    if not parsed_ts:
        return 0, None, False

    first_ts = float(parsed_ts[0])
    rel_ts = [max(0.0, t - first_ts) for t in parsed_ts]
    src_end = float(rel_ts[-1]) if rel_ts else 0.0

    if src_end <= 0.0:
        scale = 1.0
    else:
        scale = float(target_end_ms) / src_end

    changed = abs(scale - 1.0) > 0.001

    aligned_ts = [max(0.0, t * scale) for t in rel_ts]

    ts_idx = 0
    for row in data_rows:
        if not row:
            continue
        try:
            _ = float(row[0])
        except Exception:
            continue
        row[0] = str(int(round(aligned_ts[ts_idx])))
        ts_idx += 1

    try:
        with open(path, "w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(header)
            writer.writerows(data_rows)
    except Exception:
        return len(parsed_ts), None, False

    aligned_last = float(aligned_ts[-1]) if aligned_ts else None
    return len(parsed_ts), aligned_last, changed
