"""
Frame quality metrics: SNR, sharpness, specular highlight detection.

Consolidates:
- New improved implementations with masking for circular field-of-view and specular highlights (primary)
- Legacy implementations for backwards compatibility (suffixed with _legacy)
- Original (buggy) functions from SNR_Calculator.py preserved exactly as-is (eval_frames_original)
"""
import os
import numpy as np
import cv2

from shared.constants import (
    SNR_THRESHOLD, SHARPNESS_THRESHOLD,
    BRIGHTNESS_THRESHOLD, SATURATION_THRESHOLD, SPECULAR_THRESHOLD,
)

# For convenience, initialize threshold globals from constants
snr_threshold = SNR_THRESHOLD
sharpness_threshold = SHARPNESS_THRESHOLD
brightness_threshold = BRIGHTNESS_THRESHOLD
saturation_threshold = SATURATION_THRESHOLD
specular_threshold = SPECULAR_THRESHOLD


# ---------------------------------------------------------------------------
# Helper functions for masking and metrics
# ---------------------------------------------------------------------------
def get_frame_masks(frame):
    """
    Pre-compute all masks and grayscale for a frame.
    Returns: (gray, circular_mask_bool, specular_mask_bool, combined_mask_bool)

    All masks are boolean arrays for efficiency.
    This avoids redundant conversions across multiple metric calculations.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    circular_mask = gray > 0

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)

    # True for non-specular pixels, False for specular
    specular_mask = ~np.logical_and(v > brightness_threshold, s < saturation_threshold)

    combined_mask = circular_mask & specular_mask
    return gray, circular_mask, specular_mask, combined_mask


def create_circular_mask(frame):
    """
    Creates a mask to exclude pure black border pixels (intensity 0).
    Returns uint8 mask (255 for video content, 0 for black border).
    Legacy function - use get_frame_masks for better performance.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return (gray > 0).astype(np.uint8) * 255


def create_specular_mask(frame):
    """
    Creates a mask to exclude pixels affected by specular reflection.
    Returns uint8 mask (255 for non-specular, 0 for specular).
    Legacy function - use get_frame_masks for better performance.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)
    specular_pixels = np.logical_and(v > brightness_threshold, s < saturation_threshold)
    return (~specular_pixels).astype(np.uint8) * 255


def set_thresholds(
    snr: float | None = None,
    sharpness: float | None = None,
    brightness: float | None = None,
    saturation: float | None = None,
    specular: float | None = None,
):
    """Update global threshold values used for quality decisions.

    These are only used by eval_frames and calculate_specular; metrics
    themselves are unaffected. Call from outside code if you want to
    override the defaults.
    """
    global snr_threshold, sharpness_threshold, brightness_threshold, saturation_threshold, specular_threshold

    if snr is not None:
        snr_threshold = snr
    if sharpness is not None:
        sharpness_threshold = sharpness
    if brightness is not None:
        brightness_threshold = brightness
    if saturation is not None:
        saturation_threshold = saturation
    if specular is not None:
        specular_threshold = specular


# ---------------------------------------------------------------------------
# Primary implementations (used by extraction pipeline)
# Includes masking for circular field-of-view and specular highlights
# ---------------------------------------------------------------------------
def calculate_SNR(frame, gray=None, combined_mask=None):
    """
    Signal-to-noise ratio estimate (intensity-based, in dB).
    Applies masking to exclude black borders and specular highlights.

    Args:
        frame: Input frame or precomputed grayscale
        gray: (optional) Precomputed grayscale frame to avoid reconversion
        combined_mask: (optional) Precomputed combined mask to avoid recomputation
    """
    if gray is None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if combined_mask is None:
        circular_mask = gray > 0
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        _, s, v = cv2.split(hsv)
        specular_mask = ~np.logical_and(v > brightness_threshold, s < saturation_threshold)
        combined_mask = circular_mask & specular_mask

    masked_pixels = gray[combined_mask]

    if len(masked_pixels) == 0:
        return 0

    mean = np.mean(masked_pixels)
    std = np.std(masked_pixels)

    if std == 0:
        return 0

    snr = 10 * np.log10((mean**2) / (std**2))
    return snr


def calculate_sharpness(frame, gray=None, combined_mask=None):
    """
    Sharpness metric combining Laplacian and texture variance.
    Applies masking to exclude black borders and specular highlights.
    Returns dict with combined, laplacian, and texture sharpness values.

    Args:
        frame: Input frame
        gray: (optional) Precomputed grayscale frame
        combined_mask: (optional) Precomputed combined mask
    """
    if gray is None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if combined_mask is None:
        circular_mask = gray > 0
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        _, s, v = cv2.split(hsv)
        specular_mask = ~np.logical_and(v > brightness_threshold, s < saturation_threshold)
        combined_mask = circular_mask & specular_mask

    # Laplacian sharpness
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    laplacian_masked = laplacian[combined_mask]

    if len(laplacian_masked) == 0:
        return {"combined": 0, "laplacian": 0, "texture": 0}

    laplacian_var = np.var(laplacian_masked)

    # Texture sharpness using local variance (5x5 window)
    gray_float = gray.astype(np.float64)
    local_mean = cv2.boxFilter(gray_float, -1, (5, 5))
    local_mean_sq = cv2.boxFilter(gray_float * gray_float, -1, (5, 5))
    variance_map = local_mean_sq - local_mean * local_mean

    texture_var = np.mean(variance_map[combined_mask])

    # Combine metrics
    combined_sharpness = (laplacian_var + texture_var) / 2

    return {
        "combined": combined_sharpness,
        "laplacian": laplacian_var,
        "texture": texture_var
    }


def calculate_specular(frame, center_fraction: float | None = None, circular_mask=None, s=None, v=None):
    """
    Return the fraction of pixels suffering specular reflection.

    By default the calculation considers all valid pixels inside the circular
    field of view (i.e. pixels where ``create_circular_mask`` is nonzero).
    ``center_fraction`` may be used to restrict the measurement to a smaller
    circular region centred on the frame. For example, ``center_fraction=
    0.5`` evaluates only the middle half of the diameter, which is handy when
    specular highlights appear at the edges and you want to give the frame a
    second chance.

    The return value is the ratio of specular pixels to all valid pixels in
    the chosen region, or ``0`` if the region contains no valid pixels.

    Args:
        frame: Input frame
        center_fraction: (optional) Restrict evaluation to center fraction
        circular_mask: (optional) Precomputed circular mask
        s, v: (optional) Precomputed S and V from HSV
    """
    if circular_mask is None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        circular_mask = gray > 0

    if s is None or v is None:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        _, s, v = cv2.split(hsv)

    # Identify specular highlights (high V, low S)
    specular_mask = np.logical_and(v > brightness_threshold, s < saturation_threshold)

    if center_fraction is not None and 0 < center_fraction < 1.0:
        # Build central circular ROI mask
        rows, cols = frame.shape[:2]
        crow, ccol = rows / 2.0, cols / 2.0
        r = (min(rows, cols) / 2.0) * center_fraction
        y, x = np.ogrid[:rows, :cols]
        roi_mask = (x - ccol) ** 2 + (y - crow) ** 2 <= r ** 2
        valid_region = circular_mask & roi_mask
    else:
        valid_region = circular_mask

    valid_specular = specular_mask & valid_region

    num_specular = np.sum(valid_specular)
    num_valid = np.sum(valid_region)

    if num_valid == 0:
        return 0.0

    return float(num_specular / num_valid)


def calculate_brightness(frame, v=None, combined_mask=None):
    """
    Return the mean value of the V channel in HSV space (perceived brightness).

    Args:
        frame: Input frame
        v: (optional) Precomputed V channel from HSV
        combined_mask: (optional) Precomputed combined mask
    """
    if v is None or combined_mask is None:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        if v is None:
            _, _, v = cv2.split(hsv)

        if combined_mask is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            circular_mask = gray > 0
            _, s, _ = cv2.split(hsv)
            specular_mask = ~np.logical_and(v > brightness_threshold, s < saturation_threshold)
            combined_mask = circular_mask & specular_mask

    masked_v = v[combined_mask]

    if len(masked_v) == 0:
        return 0

    return float(np.mean(masked_v))


def calculate_saturation(frame, s=None, combined_mask=None):
    """
    Return the mean saturation value from the HSV representation.

    Args:
        frame: Input frame
        s: (optional) Precomputed S channel from HSV
        combined_mask: (optional) Precomputed combined mask
    """
    if s is None or combined_mask is None:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        if s is None:
            _, s, _ = cv2.split(hsv)

        if combined_mask is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            circular_mask = gray > 0
            _, _, v = cv2.split(hsv)
            specular_mask = ~np.logical_and(v > brightness_threshold, s < saturation_threshold)
            combined_mask = circular_mask & specular_mask

    masked_s = s[combined_mask]

    if len(masked_s) == 0:
        return 0

    return float(np.mean(masked_s))


def compute_frame_metrics(frame):
    """
    Return a dictionary containing all quality metrics for a single frame.

    Optimized to compute masks once and reuse them across all metric functions.
    This is significantly faster than computing masks independently in each function.
    """
    # Compute all necessary data once
    gray, circular_mask, specular_mask, combined_mask = get_frame_masks(frame)

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)

    # Compute all metrics with pre-computed masks and data
    sharpness_metrics = calculate_sharpness(frame, gray=gray, combined_mask=combined_mask)

    return {
        "snr": calculate_SNR(frame, gray=gray, combined_mask=combined_mask),
        "sharpness": sharpness_metrics["combined"],
        "laplacian_sharpness": sharpness_metrics["laplacian"],
        "texture_sharpness": sharpness_metrics["texture"],
        "brightness": calculate_brightness(frame, v=v, combined_mask=combined_mask),
        "saturation": calculate_saturation(frame, s=s, combined_mask=combined_mask),
        "specular": calculate_specular(frame, circular_mask=circular_mask, s=s, v=v),
    }


def eval_frames(
    output_folder,
    snr_thr=None,
    sharpness_thr=None,
    brightness_thr=None,
    saturation_thr=None,
    specular_thr=None,
):
    """Evaluate all image files in a folder and partition into selected/rejected lists.

    Each entry in the returned lists is a tuple:
        (filename, metrics_dict)

    Threshold parameters are optional and default to module globals.
    """
    # Use global thresholds if not provided
    if snr_thr is None:
        snr_thr = snr_threshold
    if sharpness_thr is None:
        sharpness_thr = sharpness_threshold
    if brightness_thr is None:
        brightness_thr = brightness_threshold
    if saturation_thr is None:
        saturation_thr = saturation_threshold
    if specular_thr is None:
        specular_thr = specular_threshold

    selected_frames = []
    rejected_frames = []

    for filename in os.listdir(output_folder):
        if not filename.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.svg', '.webp', '.raw')
        ):
            continue

        frame_path = os.path.join(output_folder, filename)
        frame = cv2.imread(frame_path)
        if frame is None:
            continue

        metrics = compute_frame_metrics(frame)

        ok = (
            metrics['snr'] >= snr_thr
            and metrics['sharpness'] >= sharpness_thr
            and metrics['specular'] <= specular_thr
        )
        if ok:
            selected_frames.append((filename, metrics))
        else:
            rejected_frames.append((filename, metrics))

    return selected_frames, rejected_frames


# ---------------------------------------------------------------------------
# Legacy implementations (for backwards compatibility)
# These are the original simple implementations without masking
# ---------------------------------------------------------------------------
def calculate_snr(frame) -> float:
    """LEGACY: Signal-to-noise ratio estimate (intensity-based, in dB). No masking."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray_scale)
    std = np.std(gray_scale)
    if std == 0:
        return 0
    snr = 10 * np.log10((mean ** 2) / (std ** 2))
    return snr


def calculate_sharpness_simple(frame) -> float:
    """LEGACY: Laplacian variance as a sharpness proxy. No masking."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian_variance = cv2.Laplacian(gray_scale, cv2.CV_64F).var()
    return laplacian_variance


def eval_frames_legacy(output_folder: str, snr_thresh: float = SNR_THRESHOLD,
                       sharpness_thresh: float = SHARPNESS_THRESHOLD):
    """LEGACY: Evaluate extracted frames without masking."""
    selected_frames = []
    rejected_frames = []

    for filename in os.listdir(output_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.svg', '.webp', '.raw')):
            frame_path = os.path.join(output_folder, filename)
            frame = cv2.imread(frame_path)

            snr = calculate_snr(frame)
            sharpness = calculate_sharpness_simple(frame)

            if snr >= snr_thresh and sharpness >= sharpness_thresh:
                selected_frames.append((filename, snr, sharpness))
            else:
                rejected_frames.append((filename, snr, sharpness))

    return selected_frames, rejected_frames


# ---------------------------------------------------------------------------
# Original (buggy) implementations from SNR_Calculator.py -- preserved as-is
# These contain intentional bugs that the user requested NOT to fix:
#   - cv2.Lapacian  (should be cv2.Laplacian)
#   - cv2.CV_64f    (should be cv2.CV_64F)
#   - cv2.cvtcolor  (should be cv2.cvtColor)
# ---------------------------------------------------------------------------
def calculate_SNR_original(frame):
    """ORIGINAL: SNR calculation from SNR_Calculator.py (correct)."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray_scale)
    std = np.std(gray_scale)
    if std == 0:
        return 0
    snr = 10 * np.log10((mean ** 2) / (std ** 2))
    return snr


def calculate_sharpness_buggy(frame):
    """ORIGINAL: Sharpness from SNR_Calculator.py (HAS BUGS -- preserved per user request)."""
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    lapacian_variance = cv2.Lapacian(gray_scale, cv2.CV_64f).var()
    return lapacian_variance


def calculate_specular_original(frame):
    """ORIGINAL: Specular from SNR_Calculator.py (HAS BUG -- preserved per user request)."""
    hsv = cv2.cvtcolor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    specular_mask = np.logical_and(v > BRIGHTNESS_THRESHOLD, s < SATURATION_THRESHOLD)
    specular_ratio = np.sum(specular_mask) / specular_mask.size
    return specular_ratio


def eval_frames_original(output_folder, snr_threshold=SNR_THRESHOLD,
                         sharpness_threshold=SHARPNESS_THRESHOLD):
    """ORIGINAL: eval_frames from SNR_Calculator.py (uses buggy functions)."""
    selected_frames = []
    rejected_frames = []

    for filename in os.listdir(output_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.svg', '.webp', '.raw')):
            frame_path = os.path.join(output_folder, filename)
            frame = cv2.imread(frame_path)

            snr = calculate_SNR_original(frame)
            sharpness = calculate_sharpness_buggy(frame)
            specular = calculate_specular_original(frame)

            if snr >= snr_threshold and sharpness >= sharpness_threshold and specular <= SPECULAR_THRESHOLD:
                selected_frames.append((filename, snr, sharpness))
            else:
                rejected_frames.append((filename, snr, sharpness))

    return selected_frames, rejected_frames