"""
Test file for SNR Calculator with frame extraction and segmentation.

This module demonstrates:
1. Extracting frames from a video file
2. Running SNR, sharpness, and specular calculations on extracted frames
3. Segmenting frames into selected/rejected categories based on quality thresholds
4. Generating detailed quality metrics and statistics
"""

import os
import sys
import csv
import json
from pathlib import Path
from typing import Tuple, List, Dict
import cv2
import numpy as np

# Add GUI directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'GUI'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'GUI', 'backend'))

from backend.extraction_service import extract_frames
from SNR_Calculator import (
    calculate_SNR,
    calculate_sharpness,
    calculate_specular,
    snr_threshold,
    sharpness_threshold,
    specular_threshold
)


class SNRSegmentationTest:
    """Test harness for SNR-based frame segmentation."""

    def __init__(
        self,
        video_path: str,
        output_dir: str = "test_extraction",
        frames_per_second: int = 2
    ):
        """
        Initialize the SNR Segmentation test.

        Args:
            video_path: Path to the video file to extract frames from
            output_dir: Directory to save extracted frames and results
            frames_per_second: Frame extraction rate (default: 2 fps)
        """
        self.video_path = video_path
        self.output_dir = output_dir
        self.frames_per_second = frames_per_second
        self.frames_dir = os.path.join(output_dir, "frames")
        self.selected_dir = os.path.join(output_dir, "selected")
        self.rejected_dir = os.path.join(output_dir, "rejected")

        # Create output directories
        for dir_path in [self.frames_dir, self.selected_dir, self.rejected_dir]:
            os.makedirs(dir_path, exist_ok=True)

        self.extraction_progress = 0
        self.frame_metrics = {}  # filename -> {snr, sharpness, specular, decision}
        self.selected_frames = []
        self.rejected_frames = []

    def _on_extraction_progress(self, progress: int):
        """Callback for frame extraction progress."""
        self.extraction_progress = progress
        print(f"  Extraction progress: {progress}%", end='\r')

    def _on_preview(self, frame):
        """Callback for preview frames during extraction."""
        pass

    def extract_frames_from_video(self):
        """Extract frames from the video file."""
        print(f"\n[1] Extracting frames from: {self.video_path}")
        print(f"    Output directory: {self.frames_dir}")
        print(f"    Extraction rate: {self.frames_per_second} fps")

        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"Video file not found: {self.video_path}")

        # Extract frames
        extract_frames(
            self.video_path,
            self.frames_dir,
            frames_per_second=self.frames_per_second,
            progress_callback=self._on_extraction_progress,
            preview_callback=self._on_preview,
            timestamps_csv_name="frame_timestamps.csv"
        )

        frame_count = len([f for f in os.listdir(self.frames_dir) if f.endswith('.jpg')])
        print(f"\n    ✓ Extracted {frame_count} frames")

        return frame_count

    def evaluate_frame_quality(self) -> float:
        """
        Evaluate SNR, sharpness, and specular for all extracted frames.

        Returns:
            Percentage of frames meeting quality thresholds
        """
        print(f"\n[2] Evaluating frame quality")
        print(f"    SNR threshold: >= {snr_threshold} dB")
        print(f"    Sharpness threshold: >= {sharpness_threshold}")
        print(f"    Specular threshold: <= {specular_threshold}")

        frame_files = sorted([
            f for f in os.listdir(self.frames_dir)
            if f.lower().endswith(('.jpg', '.png', '.jpeg'))
        ])

        if not frame_files:
            print("    ⚠ No frames found to evaluate")
            return 0.0

        for filename in frame_files:
            frame_path = os.path.join(self.frames_dir, filename)
            frame = cv2.imread(frame_path)

            if frame is None:
                print(f"    ⚠ Failed to read frame: {filename}")
                continue

            snr = calculate_SNR(frame)
            sharpness_metrics = calculate_sharpness(frame)
            sharpness = sharpness_metrics["combined"] if isinstance(sharpness_metrics, dict) else sharpness_metrics
            specular = calculate_specular(frame)

            # Determine selection based on thresholds
            is_selected = (
                snr >= snr_threshold and
                sharpness >= sharpness_threshold and
                specular <= specular_threshold
            )

            self.frame_metrics[filename] = {
                'snr': float(snr),
                'sharpness': float(sharpness),
                'sharpness_details': sharpness_metrics if isinstance(sharpness_metrics, dict) else {},
                'specular': float(specular),
                'selected': is_selected
            }

            if is_selected:
                self.selected_frames.append(filename)
            else:
                self.rejected_frames.append(filename)

            print(f"    {filename}: SNR={snr:.2f}dB, Sharp={sharpness:.2f}, Spec={specular:.4f} "
                  f"→ {'✓ SELECTED' if is_selected else '✗ REJECTED'}", end='\r')

        selection_rate = (len(self.selected_frames) / len(frame_files) * 100) if frame_files else 0.0
        print(f"\n    ✓ Processed {len(frame_files)} frames | "
              f"Selected: {len(self.selected_frames)} | "
              f"Rejected: {len(self.rejected_frames)} | "
              f"Rate: {selection_rate:.1f}%")

        return selection_rate

    def segment_frames(self):
        """Segment frames into selected and rejected directories."""
        print(f"\n[3] Segmenting frames")

        # Copy selected frames
        for filename in self.selected_frames:
            src = os.path.join(self.frames_dir, filename)
            dst = os.path.join(self.selected_dir, filename)
            try:
                cv2.imwrite(dst, cv2.imread(src))
            except Exception as e:
                print(f"    ⚠ Error copying selected frame {filename}: {e}")

        # Copy rejected frames
        for filename in self.rejected_frames:
            src = os.path.join(self.frames_dir, filename)
            dst = os.path.join(self.rejected_dir, filename)
            try:
                cv2.imwrite(dst, cv2.imread(src))
            except Exception as e:
                print(f"    ⚠ Error copying rejected frame {filename}: {e}")

        print(f"    ✓ Selected frames: {self.selected_dir} ({len(self.selected_frames)} files)")
        print(f"    ✓ Rejected frames: {self.rejected_dir} ({len(self.rejected_frames)} files)")

    def generate_metrics_report(self):
        """Generate detailed metrics CSV and JSON reports."""
        print(f"\n[4] Generating reports")

        # Generate CSV report
        csv_path = os.path.join(self.output_dir, "frame_metrics.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['frame_name', 'snr_db', 'sharpness_combined', 'sharpness_laplacian', 'sharpness_texture', 'specular_ratio', 'selected'])

            for filename in sorted(self.frame_metrics.keys()):
                metrics = self.frame_metrics[filename]
                writer.writerow([
                    filename,
                    f"{metrics['snr']:.4f}",
                    f"{metrics['sharpness']:.4f}",
                    f"{metrics['sharpness_details'].get('laplacian', 0):.4f}",
                    f"{metrics['sharpness_details'].get('texture', 0):.4f}",
                    f"{metrics['specular']:.6f}",
                    'YES' if metrics['selected'] else 'NO'
                ])

        print(f"    ✓ Metrics CSV: {csv_path}")

        # Generate JSON summary report
        json_path = os.path.join(self.output_dir, "segmentation_summary.json")
        summary = {
            'video_path': self.video_path,
            'extraction_rate_fps': self.frames_per_second,
            'total_frames': len(self.frame_metrics),
            'selected_count': len(self.selected_frames),
            'rejected_count': len(self.rejected_frames),
            'selection_rate_percent': (
                len(self.selected_frames) / len(self.frame_metrics) * 100
                if self.frame_metrics else 0.0
            ),
            'thresholds': {
                'snr_db': snr_threshold,
                'sharpness': sharpness_threshold,
                'specular': specular_threshold
            },
            'statistics': self._compute_statistics()
        }

        with open(json_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"    ✓ Summary JSON: {json_path}")

    def _compute_statistics(self) -> Dict:
        """Compute statistical summaries for frame metrics."""
        if not self.frame_metrics:
            return {}

        snr_values = [m['snr'] for m in self.frame_metrics.values()]
        sharpness_values = [m['sharpness'] for m in self.frame_metrics.values()]
        laplacian_values = [m['sharpness_details'].get('laplacian', 0) for m in self.frame_metrics.values()]
        texture_values = [m['sharpness_details'].get('texture', 0) for m in self.frame_metrics.values()]
        specular_values = [m['specular'] for m in self.frame_metrics.values()]

        return {
            'snr': {
                'mean': float(np.mean(snr_values)),
                'std': float(np.std(snr_values)),
                'min': float(np.min(snr_values)),
                'max': float(np.max(snr_values)),
                'threshold': snr_threshold
            },
            'sharpness': {
                'combined': {
                    'mean': float(np.mean(sharpness_values)),
                    'std': float(np.std(sharpness_values)),
                    'min': float(np.min(sharpness_values)),
                    'max': float(np.max(sharpness_values)),
                    'threshold': sharpness_threshold
                },
                'laplacian': {
                    'mean': float(np.mean(laplacian_values)),
                    'std': float(np.std(laplacian_values)),
                    'min': float(np.min(laplacian_values)),
                    'max': float(np.max(laplacian_values))
                },
                'texture': {
                    'mean': float(np.mean(texture_values)),
                    'std': float(np.std(texture_values)),
                    'min': float(np.min(texture_values)),
                    'max': float(np.max(texture_values))
                }
            },
            'specular': {
                'mean': float(np.mean(specular_values)),
                'std': float(np.std(specular_values)),
                'min': float(np.min(specular_values)),
                'max': float(np.max(specular_values)),
                'threshold': specular_threshold
            }
        }

    def print_summary(self):
        """Print a summary of the test results."""
        print(f"\n{'='*70}")
        print(f"SNR SEGMENTATION TEST SUMMARY")
        print(f"{'='*70}")

        if not self.frame_metrics:
            print("No frame metrics available")
            return

        stats = self._compute_statistics()

        print(f"\nVIDEO INFORMATION:")
        print(f"  Input video: {self.video_path}")
        print(f"  Extraction rate: {self.frames_per_second} fps")

        print(f"\nFRAME SEGMENTATION RESULTS:")
        print(f"  Total frames extracted: {len(self.frame_metrics)}")
        print(f"  Selected frames (high quality): {len(self.selected_frames)}")
        print(f"  Rejected frames (low quality): {len(self.rejected_frames)}")
        print(f"  Selection rate: {len(self.selected_frames)/len(self.frame_metrics)*100:.1f}%")

        print(f"\nQUALITY THRESHOLDS:")
        print(f"  SNR: >= {snr_threshold} dB")
        print(f"  Sharpness (Combined): >= {sharpness_threshold}")
        print(f"  Specular: <= {specular_threshold}")

        print(f"\nMETRIC STATISTICS (all frames):")

        # SNR statistics
        if 'snr' in stats:
            snr_stat = stats['snr']
            print(f"\n  SNR (dB):")
            print(f"    Mean: {snr_stat['mean']:.4f}")
            print(f"    Std Dev: {snr_stat['std']:.4f}")
            print(f"    Min: {snr_stat['min']:.4f}")
            print(f"    Max: {snr_stat['max']:.4f}")
            print(f"    Threshold: {snr_stat['threshold']}")

        # Sharpness statistics (combined, laplacian, texture)
        if 'sharpness' in stats:
            sharp_stats = stats['sharpness']
            print(f"\n  SHARPNESS (Combined):")
            combined = sharp_stats.get('combined', {})
            print(f"    Mean: {combined.get('mean', 0):.4f}")
            print(f"    Std Dev: {combined.get('std', 0):.4f}")
            print(f"    Min: {combined.get('min', 0):.4f}")
            print(f"    Max: {combined.get('max', 0):.4f}")
            print(f"    Threshold: {combined.get('threshold', 0)}")

            print(f"\n  SHARPNESS (Laplacian):")
            laplacian = sharp_stats.get('laplacian', {})
            print(f"    Mean: {laplacian.get('mean', 0):.4f}")
            print(f"    Std Dev: {laplacian.get('std', 0):.4f}")
            print(f"    Min: {laplacian.get('min', 0):.4f}")
            print(f"    Max: {laplacian.get('max', 0):.4f}")

            print(f"\n  SHARPNESS (Texture/Local Variance):")
            texture = sharp_stats.get('texture', {})
            print(f"    Mean: {texture.get('mean', 0):.4f}")
            print(f"    Std Dev: {texture.get('std', 0):.4f}")
            print(f"    Min: {texture.get('min', 0):.4f}")
            print(f"    Max: {texture.get('max', 0):.4f}")

        # Specular statistics
        if 'specular' in stats:
            spec_stat = stats['specular']
            print(f"\n  SPECULAR (Highlight Ratio):")
            print(f"    Mean: {spec_stat['mean']:.6f}")
            print(f"    Std Dev: {spec_stat['std']:.6f}")
            print(f"    Min: {spec_stat['min']:.6f}")
            print(f"    Max: {spec_stat['max']:.6f}")
            print(f"    Threshold: {spec_stat['threshold']}")

        print(f"\nOUTPUT DIRECTORIES:")
        print(f"  All frames: {self.frames_dir}")
        print(f"  Selected frames: {self.selected_dir}")
        print(f"  Rejected frames: {self.rejected_dir}")
        print(f"  Metrics CSV: {os.path.join(self.output_dir, 'frame_metrics.csv')}")
        print(f"  Summary JSON: {os.path.join(self.output_dir, 'segmentation_summary.json')}")
        print(f"{'='*70}\n")

    def run(self):
        """Execute the complete SNR segmentation test pipeline."""
        try:
            self.extract_frames_from_video()
            self.evaluate_frame_quality()
            self.segment_frames()
            self.generate_metrics_report()
            self.print_summary()
            print("✓ Test completed successfully!")
            return True
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point for the test."""
    print("LED Endoscope - SNR Calculator & Frame Segmentation Test\n")

    # Configuration
    # Modify these paths as needed for your test
    video_file = "camera_capture.mp4"  # Update with your video path
    test_output = "test_extraction"
    extraction_fps = 2

    # Check if video file exists
    if not os.path.exists(video_file):
        print(f"Error: Video file not found: {video_file}")
        print("\nAvailable files in current directory:")
        for f in os.listdir("."):
            if f.endswith(('.mp4', '.avi', '.mov', '.flv')):
                print(f"  - {f}")
        return False

    # Run the test
    test = SNRSegmentationTest(
        video_path=video_file,
        output_dir=test_output,
        frames_per_second=extraction_fps
    )

    return test.run()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
