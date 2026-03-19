"""
Usage Examples for SNR Segmentation Test

This file demonstrates various ways to use the SNR segmentation test
for different testing scenarios and use cases.
"""

import os
import sys
from test_snr_segmentation import SNRSegmentationTest


# Example 1: Basic test with default settings
def example_basic_test():
    """Run a basic test with default settings."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Test with Default Settings")
    print("="*70)

    test = SNRSegmentationTest(
        video_path="camera_capture.mp4",
        output_dir="test_extraction",
        frames_per_second=2
    )

    test.run()


# Example 2: Test with different extraction rates
def example_different_extraction_rates():
    """Compare results at different extraction rates."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Testing Different Extraction Rates")
    print("="*70)

    extraction_rates = [1, 2, 5]  # 1 fps, 2 fps, 5 fps

    for fps in extraction_rates:
        print(f"\n--- Testing at {fps} fps ---")
        test = SNRSegmentationTest(
            video_path="camera_capture.mp4",
            output_dir=f"test_extraction_{fps}fps",
            frames_per_second=fps
        )
        test.run()


# Example 3: Test multiple videos and compare results
def example_compare_multiple_videos():
    """Test multiple video files and compare results."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Comparing Multiple Video Files")
    print("="*70)

    video_files = [
        "camera_capture.mp4",
        "camera_capture_20260109_151135.mp4",
    ]

    for video_file in video_files:
        if os.path.exists(video_file):
            print(f"\nTesting: {video_file}")
            test = SNRSegmentationTest(
                video_path=video_file,
                output_dir=f"test_extraction_{os.path.splitext(video_file)[0]}",
                frames_per_second=2
            )
            test.run()
        else:
            print(f"⚠️  Video file not found: {video_file}")


# Example 4: Test with custom frame extraction and manual evaluation
def example_custom_evaluation():
    """Manually control extraction and evaluation steps."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Custom Evaluation with Step-by-Step Control")
    print("="*70)

    test = SNRSegmentationTest(
        video_path="camera_capture.mp4",
        output_dir="test_extraction_custom",
        frames_per_second=3
    )

    # Step 1: Extract frames
    print("\n[Step 1] Extracting frames...")
    frame_count = test.extract_frames_from_video()
    print(f"✓ Extracted {frame_count} frames")

    # Step 2: Evaluate quality
    print("\n[Step 2] Evaluating quality...")
    selection_rate = test.evaluate_frame_quality()
    print(f"✓ Selection rate: {selection_rate:.1f}%")

    # Step 3: Segment frames
    print("\n[Step 3] Segmenting frames...")
    test.segment_frames()

    # Step 4: Generate reports
    print("\n[Step 4] Generating reports...")
    test.generate_metrics_report()

    # Step 5: Print summary
    print("\n[Step 5] Summary:")
    test.print_summary()

    # Additional analysis: Find the best and worst frames
    print("\n[Analysis] Frame Quality Distribution:")
    if test.frame_metrics:
        snr_values = sorted(
            [(f, m['snr']) for f, m in test.frame_metrics.items()],
            key=lambda x: x[1],
            reverse=True
        )
        print("\nTop 5 Best Frames (by SNR):")
        for i, (frame, snr) in enumerate(snr_values[:5], 1):
            print(f"  {i}. {frame}: {snr:.2f} dB")

        print("\nTop 5 Worst Frames (by SNR):")
        for i, (frame, snr) in enumerate(reversed(snr_values[-5:]), 1):
            print(f"  {i}. {frame}: {snr:.2f} dB")


# Example 5: Batch testing with analysis
def example_batch_analysis():
    """Run batch testing and analyze patterns."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Batch Analysis with Pattern Recognition")
    print("="*70)

    test = SNRSegmentationTest(
        video_path="camera_capture.mp4",
        output_dir="test_extraction_batch",
        frames_per_second=2
    )

    test.run()

    # Analyze results
    if test.frame_metrics:
        print("\n📊 Quality Analysis:")

        # Count frames by quality buckets
        excellent = sum(1 for m in test.frame_metrics.values()
                       if m['snr'] >= 30 and m['sharpness'] >= 150)
        good = sum(1 for m in test.frame_metrics.values()
                  if 25 <= m['snr'] < 30 and 100 <= m['sharpness'] < 150)
        poor = sum(1 for m in test.frame_metrics.values()
                  if m['snr'] < 25 or m['sharpness'] < 100)

        total = len(test.frame_metrics)
        print(f"\nFrame Quality Distribution:")
        print(f"  Excellent (SNR≥30, Sharp≥150): {excellent} ({excellent/total*100:.1f}%)")
        print(f"  Good (SNR≥25, Sharp≥100):     {good} ({good/total*100:.1f}%)")
        print(f"  Poor (SNR<25 or Sharp<100):   {poor} ({poor/total*100:.1f}%)")

        # Identify problem areas
        low_snr_frames = [f for f, m in test.frame_metrics.items() if m['snr'] < 20]
        blurry_frames = [f for f, m in test.frame_metrics.items() if m['sharpness'] < 80]

        if low_snr_frames:
            print(f"\n⚠️  Low SNR Frames ({len(low_snr_frames)}):")
            for frame in low_snr_frames[:5]:
                snr = test.frame_metrics[frame]['snr']
                print(f"   - {frame}: {snr:.2f} dB (noisy)")

        if blurry_frames:
            print(f"\n⚠️  Blurry Frames ({len(blurry_frames)}):")
            for frame in blurry_frames[:5]:
                sharpness = test.frame_metrics[frame]['sharpness']
                print(f"   - {frame}: {sharpness:.2f} (out of focus)")


# Example 6: Test output verification
def example_verify_outputs():
    """Verify that all test outputs are created correctly."""
    print("\n" + "="*70)
    print("EXAMPLE 6: Output Verification")
    print("="*70)

    output_dir = "test_extraction_verify"
    test = SNRSegmentationTest(
        video_path="camera_capture.mp4",
        output_dir=output_dir,
        frames_per_second=2
    )

    test.run()

    # Verify directory structure
    print(f"\n✓ Verifying output structure in {output_dir}/")

    required_dirs = [
        test.frames_dir,
        test.selected_dir,
        test.rejected_dir,
    ]

    required_files = [
        os.path.join(output_dir, "frame_timestamps.csv"),
        os.path.join(output_dir, "frame_metrics.csv"),
        os.path.join(output_dir, "segmentation_summary.json"),
    ]

    # Check directories
    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            file_count = len(os.listdir(dir_path))
            print(f"  ✓ {os.path.basename(dir_path)}/: {file_count} files")
        else:
            print(f"  ✗ {dir_path}: NOT FOUND")

    # Check files
    for file_path in required_files:
        if os.path.isfile(file_path):
            file_size_kb = os.path.getsize(file_path) / 1024
            print(f"  ✓ {os.path.basename(file_path)}: {file_size_kb:.1f} KB")
        else:
            print(f"  ✗ {file_path}: NOT FOUND")


# Main menu
def main():
    """Run the examples."""
    print("\n" + "="*70)
    print("SNR Segmentation Test - Usage Examples")
    print("="*70)
    print("\nAvailable Examples:")
    print("  1. Basic test with default settings")
    print("  2. Test with different extraction rates")
    print("  3. Compare multiple video files")
    print("  4. Custom evaluation with step-by-step control")
    print("  5. Batch analysis with pattern recognition")
    print("  6. Output verification")
    print("  0. Exit")

    choice = input("\nSelect example (0-6): ").strip()

    examples = {
        '1': example_basic_test,
        '2': example_different_extraction_rates,
        '3': example_compare_multiple_videos,
        '4': example_custom_evaluation,
        '5': example_batch_analysis,
        '6': example_verify_outputs,
    }

    if choice in examples:
        try:
            examples[choice]()
            print("\n✓ Example completed!")
        except Exception as e:
            print(f"\n✗ Error running example: {e}")
            import traceback
            traceback.print_exc()
    elif choice != '0':
        print("Invalid choice!")


if __name__ == "__main__":
    main()
