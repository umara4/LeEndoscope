#!/usr/bin/env python3
"""
Quick-start script to run the SNR segmentation test with an interactive menu.
This script helps you easily test frame extraction and segmentation with different video files.
"""

import os
import sys
import argparse
from pathlib import Path


def find_video_files():
    """Find all video files in the current directory."""
    video_extensions = ('.mp4', '.avi', '.mov', '.flv', '.mkv', '.webm', '.m4v')
    videos = []
    for file in os.listdir('.'):
        if file.lower().endswith(video_extensions):
            videos.append(file)
    return sorted(videos)


def run_interactive_menu():
    """Interactive menu to select video and configure test parameters."""
    print("\n" + "="*70)
    print("LED Endoscope - SNR Segmentation Test Launcher")
    print("="*70)

    # Find available videos
    videos = find_video_files()

    if not videos:
        print("\n❌ No video files found in current directory!")
        print("\nSupported formats: .mp4, .avi, .mov, .flv, .mkv, .webm, .m4v")
        print("Place a video file in the current directory and try again.")
        return False

    print("\n📽️  Available Video Files:")
    for i, video in enumerate(videos, 1):
        file_size_mb = os.path.getsize(video) / (1024 * 1024)
        print(f"  {i}. {video} ({file_size_mb:.1f} MB)")

    # Select video
    while True:
        try:
            choice = input(f"\nSelect video file (1-{len(videos)}): ").strip()
            video_index = int(choice) - 1
            if 0 <= video_index < len(videos):
                selected_video = videos[video_index]
                break
        except ValueError:
            pass
        print(f"❌ Please enter a number between 1 and {len(videos)}")

    print(f"✅ Selected: {selected_video}")

    # Configure extraction rate
    print("\n⚙️  Frame Extraction Rate")
    print("  1 fps = 1 frame per second (slower extraction, fewer frames)")
    print("  2 fps = 2 frames per second (balanced, recommended)")
    print("  5 fps = 5 frames per second (faster extraction, more frames)")

    while True:
        try:
            fps_choice = input("\nFrame extraction rate (1/2/5 fps) [default: 2]: ").strip() or "2"
            extraction_fps = int(fps_choice)
            if extraction_fps > 0:
                break
        except ValueError:
            pass
        print("❌ Please enter a positive number")

    print(f"✅ Extraction rate: {extraction_fps} fps")

    # Confirm and run
    output_dir = "test_extraction"
    print(f"\n📁 Output directory: {output_dir}/")

    proceed = input("\nProceed with test? (yes/no) [default: yes]: ").strip().lower()
    if proceed == 'no':
        print("❌ Test cancelled")
        return False

    # Run the test
    print("\n" + "="*70)
    print("Starting SNR Segmentation Test...")
    print("="*70 + "\n")

    # Import and run the test
    sys.path.insert(0, os.path.dirname(__file__))
    from test_snr_segmentation import SNRSegmentationTest

    try:
        test = SNRSegmentationTest(
            video_path=selected_video,
            output_dir=output_dir,
            frames_per_second=extraction_fps
        )
        success = test.run()

        if success:
            print("\n✅ Test completed successfully!")
            print(f"\n📊 View results in the '{output_dir}/' directory:")
            print(f"   - frame_metrics.csv: Detailed frame quality metrics")
            print(f"   - segmentation_summary.json: Summary statistics")
            print(f"   - selected/ directory: High-quality frames")
            print(f"   - rejected/ directory: Low-quality frames")
        else:
            print("\n❌ Test failed! Check the error messages above.")

        return success

    except Exception as e:
        print(f"\n❌ Error running test: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_with_arguments():
    """Run test with command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Test SNR Calculator with frame extraction and segmentation"
    )
    parser.add_argument(
        "video",
        nargs='?',
        help="Path to video file (optional, will prompt if not provided)"
    )
    parser.add_argument(
        "-o", "--output",
        default="test_extraction",
        help="Output directory (default: test_extraction)"
    )
    parser.add_argument(
        "-fps", "--frames-per-second",
        type=int,
        default=2,
        help="Frame extraction rate in fps (default: 2)"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run interactive menu"
    )

    args = parser.parse_args()

    # Use interactive mode if requested or no video provided
    if args.interactive or not args.video:
        return run_interactive_menu()

    # Run with provided arguments
    if not os.path.exists(args.video):
        print(f"❌ Video file not found: {args.video}")
        return False

    print(f"📽️  Video: {args.video}")
    print(f"📁 Output: {args.output}")
    print(f"⚙️  Extraction rate: {args.frames_per_second} fps")

    from test_snr_segmentation import SNRSegmentationTest

    try:
        test = SNRSegmentationTest(
            video_path=args.video,
            output_dir=args.output,
            frames_per_second=args.frames_per_second
        )
        return test.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run interactive menu if called directly
    success = run_interactive_menu()
    sys.exit(0 if success else 1)
