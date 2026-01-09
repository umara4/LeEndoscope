import numpy as np
import cv2
import os

snr_threshold = 25
sharpness_threshold = 100
brightness_threshold = 220
saturation_threshold = 40
specular_threshold = 0.05


def calculate_SNR(frame):

    #Convert to gray scale as this SNR caclulation is intensity based
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    mean = np.mean(gray_scale)
    std = np.std(gray_scale)

    if std ==0:
        return 0
    
    #Simple no reference SNR estimate in decibles
    snr = 10 * np.log10((mean**2) / (std**2))

    return snr

def calculate_sharpness(frame):
    gray_scale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    lapacian_variance = cv2.Lapacian(gray_scale, cv2.CV_64f).var()

    return lapacian_variance

def calculate_specular(frame):
    hsv = cv2.cvtcolor(frame, cv2.COLOR_BGR2HSV)

    h, s, v = cv2.split(hsv)

    specular_mask = np.logical_and(v > brightness_threshold, s < saturation_threshold)
    specular_ratio = np.sum(specular_mask) / specular_mask.size

    return specular_ratio

def eval_frames(output_folder, snr_threshold, sharpness_threshold):

    #Initialize empty arrays for selected and rejected frames based on SNR and sharpness
    selected_frames = []
    rejected_frames = []

    for filename in os.listdir(output_folder):

        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.svg', '.webp', '.raw')):

            frame_path = os.path.join(output_folder, filename)
            frame = cv2.imread(frame_path)

            snr = calculate_SNR(frame)
            sharpness = calculate_sharpness(frame)
            specular = calculate_specular(frame)

            if snr >= snr_threshold and sharpness >= sharpness_threshold and specular <= specular_threshold:
                selected_frames.append((filename, snr, sharpness))

            else:
                rejected_frames.append((filename, snr, sharpness))

    return selected_frames, rejected_frames 




