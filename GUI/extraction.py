# extraction.py
import cv2
import os

def extract_frames(video_path, output_folder, frames_per_second=2, progress_callback=None, preview_callback=None):
    os.makedirs(output_folder, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Cannot open video file.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = int(fps // frames_per_second) if frames_per_second > 0 else 1

    frame_count = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Show preview in GUI
        if preview_callback:
            preview_callback(frame)

        # Save every Nth frame
        if frame_count % interval == 0:
            filename = os.path.join(output_folder, f"frame_{saved_count:05d}.jpg")
            cv2.imwrite(filename, frame)
            saved_count += 1

        # Update progress
        if progress_callback:
            progress_value = int((frame_count / total_frames) * 100)
            progress_callback(progress_value)

        frame_count += 1

    cap.release()
    print(f"Saved {saved_count} frames to {output_folder}")