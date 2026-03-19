"""
Run SNR Segmentation Test on Megaflap Postoperative Video
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'GUI'))

from test_snr_segmentation import SNRSegmentationTest

if __name__ == "__main__":
    video_path = "Megaflap Postoperative_SM_9.26.25_MX.mp4"

    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

    print(f"Starting SNR Segmentation Test on Megaflap Postoperative Video")
    print(f"Video: {video_path}")

    test = SNRSegmentationTest(
        video_path=video_path,
        output_dir="megaflap_results",
        frames_per_second=2
    )

    success = test.run()
    sys.exit(0 if success else 1)
