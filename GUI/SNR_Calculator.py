import numpy as np
import cv2
import os

snr_threshold = 2.5
sharpness_threshold = 25
brightness_threshold = 220
saturation_threshold = 40
specular_threshold = 0.05

import cv2
import numpy as np

def create_circular_mask(frame):
    """
    Creates a mask to exclude pure black border pixels (intensity 0) from endoscopic video calculations.
    Only pixels with intensity > 0 are considered video content.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Create mask: 255 for video content (any pixel > 0), 0 for pure black border
    mask = np.where(gray > 0, 255, 0).astype(np.uint8)

    return mask


def create_specular_mask(frame):
    """
    Creates a mask to exclude pixels affected by specular reflection.
    Specular pixels are identified as high brightness (V > brightness_threshold) and low saturation (S < saturation_threshold).
    Returns 255 for non-specular pixels, 0 for specular pixels.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)
    
    # Identify specular highlights (high V, low S)
    specular_pixels = np.logical_and(v > brightness_threshold, s < saturation_threshold)
    
    # Create mask: 0 for specular pixels, 255 for others
    mask = np.where(specular_pixels, 0, 255).astype(np.uint8)
    
    return mask


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
    override the placeholder defaults.
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


def calculate_SNR(frame):

    #Convert to gray scale as this SNR caclulation is intensity based
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Apply circular mask to exclude black border
    circular_mask = create_circular_mask(frame)
    # Apply specular mask to exclude specular pixels
    specular_mask = create_specular_mask(frame)
    # Combine masks
    combined_mask = cv2.bitwise_and(circular_mask, specular_mask)
    
    masked_pixels = gray_scale[combined_mask > 0]
    
    if len(masked_pixels) == 0:
        return 0

    mean = np.mean(masked_pixels)
    std = np.std(masked_pixels)

    if std == 0:
        return 0
    
    #Simple no reference SNR estimate in decibles
    snr = 10 * np.log10((mean**2) / (std**2))

    return snr

def calculate_sharpness(frame):
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Apply circular mask to exclude black border
    circular_mask = create_circular_mask(frame)
    # Apply specular mask to exclude specular pixels
    specular_mask = create_specular_mask(frame)
    # Combine masks
    combined_mask = cv2.bitwise_and(circular_mask, specular_mask)
    
    masked_gray = gray_scale.copy()
    masked_gray[combined_mask == 0] = 0
    
    # Compute Laplacian on masked region
    laplacian = cv2.Laplacian(masked_gray, cv2.CV_64F)
    
    # Calculate Laplacian variance only on masked region
    laplacian_masked = laplacian[combined_mask > 0]
    
    if len(laplacian_masked) == 0:
        return {"combined": 0, "laplacian": 0, "texture": 0}
    
    laplacian_var = np.var(laplacian_masked)
    
    # Compute texture sharpness using local variance (5x5 window)
    # Local mean
    local_mean = cv2.boxFilter(gray_scale.astype(np.float64), -1, (5, 5))
    # Local mean of squares
    local_mean_sq = cv2.boxFilter((gray_scale.astype(np.float64))**2, -1, (5, 5))
    # Local variance
    variance_map = local_mean_sq - local_mean**2
    
    # Average variance over valid pixels
    texture_var = np.mean(variance_map[combined_mask > 0])
    
    # Combine Laplacian and texture sharpness
    combined_sharpness = (laplacian_var + texture_var) / 2

    return {
        "combined": combined_sharpness,
        "laplacian": laplacian_var,
        "texture": texture_var
    }

def calculate_specular(frame):
    # correct method name
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    h, s, v = cv2.split(hsv)
    
    # Apply circular mask to exclude black border
    circular_mask = create_circular_mask(frame)
    
    # Identify specular highlights (high V, low S)
    specular_mask = np.logical_and(v > brightness_threshold, s < saturation_threshold)
    
    # Only count specular pixels within the circular field of view
    valid_specular = np.logical_and(specular_mask, circular_mask > 0)
    valid_region = circular_mask > 0
    
    # Calculate ratio of specular pixels within valid region
    num_specular = np.sum(valid_specular)
    num_valid = np.sum(valid_region)
    
    if num_valid == 0:
        return 0
    
    specular_ratio = num_specular / num_valid

    return specular_ratio


def calculate_brightness(frame):
    """Return the mean value of the V channel in HSV space (perceived brightness)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    _, _, v = cv2.split(hsv)
    
    # Apply circular mask to exclude black border
    circular_mask = create_circular_mask(frame)
    # Apply specular mask to exclude specular pixels
    specular_mask = create_specular_mask(frame)
    # Combine masks
    combined_mask = cv2.bitwise_and(circular_mask, specular_mask)
    
    masked_v = v[combined_mask > 0]
    
    if len(masked_v) == 0:
        return 0
    
    return float(np.mean(masked_v))


def calculate_saturation(frame):
    """Return the mean saturation value from the HSV representation."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    _, s, _ = cv2.split(hsv)
    
    # Apply circular mask to exclude black border
    circular_mask = create_circular_mask(frame)
    # Apply specular mask to exclude specular pixels
    specular_mask = create_specular_mask(frame)
    # Combine masks
    combined_mask = cv2.bitwise_and(circular_mask, specular_mask)
    
    masked_s = s[combined_mask > 0]
    
    if len(masked_s) == 0:
        return 0
    
    return float(np.mean(masked_s))

def compute_frame_metrics(frame):
    """Return a dictionary containing all quality metrics for a single frame."""
    sharpness_metrics = calculate_sharpness(frame)
    return {
        "snr": calculate_SNR(frame),
        "sharpness": sharpness_metrics["combined"],
        "laplacian_sharpness": sharpness_metrics["laplacian"],
        "texture_sharpness": sharpness_metrics["texture"],
        "brightness": calculate_brightness(frame),
        "saturation": calculate_saturation(frame),
        "specular": calculate_specular(frame),
    }


def eval_frames(
    output_folder,
    snr_thr=snr_threshold,
    sharpness_thr=sharpness_threshold,
    brightness_thr=brightness_threshold,
    saturation_thr=saturation_threshold,
    specular_thr=specular_threshold,
):
    """Evaluate all image files in a folder and partition into selected/rejected lists.

    Each entry in the returned lists is a tuple:
        (filename, metrics_dict)

    Threshold parameters are optional and default to module globals.
    """

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




