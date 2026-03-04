"""
Frame quality metrics: SNR, sharpness, specular highlight detection.

Consolidates:
- SegmentExtractor.calculate_SNR / calculate_sharpness (correct implementations)
- SNR_Calculator.py calculate_SNR / calculate_sharpness / calculate_specular
  (bugs intentionally preserved per user request)

The "correct" functions are used by the extraction pipeline.
The "original" (buggy) functions from SNR_Calculator.py are preserved
exactly as-is for backward compatibility.
"""
import os
import numpy as np
import cv2

from shared.constants import (
    SNR_THRESHOLD, SHARPNESS_THRESHOLD,
    BRIGHTNESS_THRESHOLD, SATURATION_THRESHOLD, SPECULAR_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Correct implementations (used by extraction pipeline)
# ---------------------------------------------------------------------------
def calculate_snr(frame) -> float:
    """Signal-to-noise ratio estimate (intensity-based, in dB)."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray_scale)
    std = np.std(gray_scale)
    if std == 0:
        return 0
    snr = 10 * np.log10((mean ** 2) / (std ** 2))
    return snr


def calculate_sharpness(frame) -> float:
    """Laplacian variance as a sharpness proxy."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian_variance = cv2.Laplacian(gray_scale, cv2.CV_64F).var()
    return laplacian_variance


def eval_frames(output_folder: str, snr_thresh: float = SNR_THRESHOLD,
                sharpness_thresh: float = SHARPNESS_THRESHOLD):
    """Evaluate extracted frames and split into selected/rejected lists."""
    selected_frames = []
    rejected_frames = []

    for filename in os.listdir(output_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.svg', '.webp', '.raw')):
            frame_path = os.path.join(output_folder, filename)
            frame = cv2.imread(frame_path)

            snr = calculate_snr(frame)
            sharpness = calculate_sharpness(frame)

            if snr >= snr_thresh and sharpness >= sharpness_thresh:
                selected_frames.append((filename, snr, sharpness))
            else:
                rejected_frames.append((filename, snr, sharpness))

    return selected_frames, rejected_frames


# ---------------------------------------------------------------------------
# Original (buggy) implementations from SNR_Calculator.py -- preserved as-is.
# These contain intentional bugs that the user requested NOT to fix:
#   - cv2.Lapacian  (should be cv2.Laplacian)
#   - cv2.CV_64f    (should be cv2.CV_64F)
#   - cv2.cvtcolor  (should be cv2.cvtColor)
# ---------------------------------------------------------------------------
def calculate_SNR(frame):
    """Original SNR calculation from SNR_Calculator.py (correct)."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray_scale)
    std = np.std(gray_scale)
    if std == 0:
        return 0
    snr = 10 * np.log10((mean ** 2) / (std ** 2))
    return snr


def calculate_sharpness_buggy(frame):
    """Original sharpness from SNR_Calculator.py (HAS BUGS -- preserved per user request)."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    lapacian_variance = cv2.Lapacian(gray_scale, cv2.CV_64f).var()
    return lapacian_variance


def calculate_specular(frame):
    """Original specular from SNR_Calculator.py (HAS BUG -- preserved per user request)."""
    hsv = cv2.cvtcolor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    specular_mask = np.logical_and(v > BRIGHTNESS_THRESHOLD, s < SATURATION_THRESHOLD)
    specular_ratio = np.sum(specular_mask) / specular_mask.size
    return specular_ratio


def eval_frames_original(output_folder, snr_threshold=SNR_THRESHOLD,
                         sharpness_threshold=SHARPNESS_THRESHOLD):
    """Original eval_frames from SNR_Calculator.py (uses buggy functions)."""
    selected_frames = []
    rejected_frames = []

    for filename in os.listdir(output_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.svg', '.webp', '.raw')):
            frame_path = os.path.join(output_folder, filename)
            frame = cv2.imread(frame_path)

            snr = calculate_SNR(frame)
            sharpness = calculate_sharpness_buggy(frame)
            specular = calculate_specular(frame)

            if snr >= snr_threshold and sharpness >= sharpness_threshold and specular <= SPECULAR_THRESHOLD:
                selected_frames.append((filename, snr, sharpness))
            else:
                rejected_frames.append((filename, snr, sharpness))

    return selected_frames, rejected_frames
