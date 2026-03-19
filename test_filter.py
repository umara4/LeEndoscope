"""
Comprehensive Filter.py Testing Script
=======================================
Tests the endoscope image filtering pipeline on frames in test_extraction/frames.

Features:
  1. Batch processes all frames with filter.py
  2. Organizes results (usable/rejected)
  3. Generates detailed statistical reports
  4. Saves filtered images and debug sheets
  5. Provides performance metrics and visualizations
"""

import os
import sys
import json
import csv
import time
from pathlib import Path
from dataclasses import asdict
import numpy as np
import cv2

# Fix encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add GUI directory to path to import filter module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'GUI'))

try:
    from filter import process_image, FrameReport, save_debug_sheet
except ImportError as e:
    print(f"Error: Could not import filter module. {e}")
    sys.exit(1)


# ================================================================
# CONFIGURATION
# ================================================================

class FilterTestConfig:
    """Test configuration parameters."""
    INPUT_DIR = "test_extraction/frames"
    OUTPUT_DIR = "filter_test_results"
    USABLE_DIR = "filter_test_results/usable"
    REJECTED_DIR = "filter_test_results/rejected"
    DEBUG_DIR = "filter_test_results/debug_sheets"

    # Filter parameters
    SHARPEN_STRENGTH = 1.5
    CLAHE_CLIP = 2.0
    GLARE_THRESHOLD = 220
    VERBOSE = True


# ================================================================
# STATISTICS & REPORTING
# ================================================================

class FilterTestStats:
    """Collect and compute statistics from processing results."""

    def __init__(self):
        self.reports = []
        self.processing_times = []
        self.errors = []
        self.start_time = None
        self.end_time = None

    def add_report(self, report: FrameReport, process_time: float):
        """Add a processed frame report."""
        self.reports.append(report)
        self.processing_times.append(process_time)

    def add_error(self, filename: str, error_msg: str):
        """Log a processing error."""
        self.errors.append({"filename": filename, "error": error_msg})

    def get_summary(self) -> dict:
        """Compute summary statistics."""
        if not self.reports:
            return {}

        reports_dict = [asdict(r) for r in self.reports]

        # Extract numeric metrics
        quality_scores = [r.quality_score for r in self.reports]
        blur_scores = [r.blur_score for r in self.reports]
        brightness_means = [r.brightness_mean for r in self.reports]
        glare_pcts = [r.glare_coverage_pct for r in self.reports]
        bubble_pcts = [r.bubble_coverage_pct for r in self.reports]
        occ_pcts = [r.occlusion_coverage_pct for r in self.reports]
        usable_count = sum(1 for r in self.reports if r.is_usable)

        summary = {
            "total_frames": len(self.reports),
            "usable_frames": usable_count,
            "rejected_frames": len(self.reports) - usable_count,
            "usable_percentage": round(usable_count / len(self.reports) * 100, 2),
            "errors": len(self.errors),
            "total_time_seconds": round(self.end_time - self.start_time, 2) if self.end_time and self.start_time else 0,
            "avg_time_per_frame_ms": round(np.mean(self.processing_times) * 1000, 2) if self.processing_times else 0,
            "quality_score": {
                "mean": round(np.mean(quality_scores), 2),
                "std": round(np.std(quality_scores), 2),
                "min": round(np.min(quality_scores), 2),
                "max": round(np.max(quality_scores), 2),
                "median": round(np.median(quality_scores), 2),
            },
            "blur_score": {
                "mean": round(np.mean(blur_scores), 2),
                "std": round(np.std(blur_scores), 2),
                "min": round(np.min(blur_scores), 2),
                "max": round(np.max(blur_scores), 2),
                "median": round(np.median(blur_scores), 2),
            },
            "brightness_mean": {
                "mean": round(np.mean(brightness_means), 2),
                "std": round(np.std(brightness_means), 2),
                "min": round(np.min(brightness_means), 2),
                "max": round(np.max(brightness_means), 2),
                "median": round(np.median(brightness_means), 2),
            },
            "glare_coverage_pct": {
                "mean": round(np.mean(glare_pcts), 2),
                "std": round(np.std(glare_pcts), 2),
                "min": round(np.min(glare_pcts), 2),
                "max": round(np.max(glare_pcts), 2),
                "median": round(np.median(glare_pcts), 2),
            },
            "bubble_coverage_pct": {
                "mean": round(np.mean(bubble_pcts), 2),
                "std": round(np.std(bubble_pcts), 2),
                "min": round(np.min(bubble_pcts), 2),
                "max": round(np.max(bubble_pcts), 2),
                "median": round(np.median(bubble_pcts), 2),
            },
            "occlusion_coverage_pct": {
                "mean": round(np.mean(occ_pcts), 2),
                "std": round(np.std(occ_pcts), 2),
                "min": round(np.min(occ_pcts), 2),
                "max": round(np.max(occ_pcts), 2),
                "median": round(np.median(occ_pcts), 2),
            },
        }

        return summary


# ================================================================
# MAIN TEST RUNNER
# ================================================================

class FilterTestRunner:
    """Main test runner for filter.py."""

    def __init__(self, config: FilterTestConfig):
        self.config = config
        self.stats = FilterTestStats()

    def setup_output_dirs(self):
        """Create output directory structure."""
        dirs = [
            self.config.OUTPUT_DIR,
            self.config.USABLE_DIR,
            self.config.REJECTED_DIR,
            self.config.DEBUG_DIR,
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
        print(f"[OK] Output directories created in {self.config.OUTPUT_DIR}/")

    def get_image_files(self) -> list:
        """Get all image files from input directory."""
        if not os.path.isdir(self.config.INPUT_DIR):
            print(f"Error: Input directory not found: {self.config.INPUT_DIR}")
            return []

        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
        files = [
            f for f in os.listdir(self.config.INPUT_DIR)
            if os.path.splitext(f)[1].lower() in exts
        ]
        return sorted(files)

    def process_frame(self, filename: str) -> tuple:
        """Process a single frame and return (success, report, time_taken)."""
        filepath = os.path.join(self.config.INPUT_DIR, filename)

        try:
            start_time = time.time()
            img = cv2.imread(filepath)

            if img is None:
                raise ValueError(f"Could not read image")

            # Run filter pipeline
            filtered, report, masks = process_image(
                img,
                filename=filename,
                sharpen_strength=self.config.SHARPEN_STRENGTH,
                clahe_clip=self.config.CLAHE_CLIP,
                glare_thresh=self.config.GLARE_THRESHOLD,
                verbose=False  # Disable verbose output during batch processing
            )

            elapsed = time.time() - start_time
            return True, (filtered, report, masks), elapsed

        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            return False, str(e), elapsed

    def save_results(self, filename: str, filtered_img: np.ndarray,
                     report: FrameReport, masks: dict):
        """Save filtered image, debug sheet, and organize by usability."""
        base_name = os.path.splitext(filename)[0]

        # Determine output folder
        output_folder = self.config.USABLE_DIR if report.is_usable else self.config.REJECTED_DIR

        # Save filtered image
        filtered_path = os.path.join(output_folder, f"{base_name}_filtered.jpg")
        cv2.imwrite(filtered_path, filtered_img)

        # Save debug sheet (suppress stdout to avoid encoding errors)
        original_path = os.path.join(self.config.INPUT_DIR, filename)
        original_img = cv2.imread(original_path)
        debug_path = os.path.join(self.config.DEBUG_DIR, f"{base_name}_debug.jpg")

        # Suppress stdout during save_debug_sheet to avoid encoding issues
        old_stdout = sys.stdout
        try:
            sys.stdout = open(os.devnull, 'w')
            save_debug_sheet(original_img, filtered_img, masks, debug_path)
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout

        # Save individual report
        report_path = os.path.join(output_folder, f"{base_name}_report.json")
        with open(report_path, "w") as f:
            json.dump(asdict(report), f, indent=2)

    def run_batch(self):
        """Run batch processing on all frames."""
        files = self.get_image_files()

        if not files:
            print("No image files found in input directory.")
            return

        print(f"\n{'='*60}")
        print(f"  FILTER TEST - BATCH PROCESSING")
        print(f"{'='*60}")
        print(f"Processing {len(files)} frames from: {self.config.INPUT_DIR}/")
        print(f"Output directory: {self.config.OUTPUT_DIR}/")
        print(f"Parameters:")
        print(f"  - Sharpen strength: {self.config.SHARPEN_STRENGTH}")
        print(f"  - CLAHE clip limit: {self.config.CLAHE_CLIP}")
        print(f"  - Glare threshold: {self.config.GLARE_THRESHOLD}")
        print(f"{'='*60}\n")

        self.stats.start_time = time.time()

        for i, filename in enumerate(files, 1):
            # Progress indicator
            progress = f"[{i}/{len(files)}]"

            success, result, elapsed = self.process_frame(filename)

            if success:
                filtered, report, masks = result
                self.stats.add_report(report, elapsed)

                # Save results
                try:
                    self.save_results(filename, filtered, report, masks)
                    status = "[OK]" if report.is_usable else "[RE]"
                    print(f"{progress} {filename:<30} {status:<12} "
                          f"Quality: {report.quality_score:>5.1f}  "
                          f"Time: {elapsed*1000:>6.1f}ms")
                except Exception as e:
                    print(f"{progress} {filename:<30} [ERROR] (save) {str(e)[:40]}")
                    self.stats.add_error(filename, f"Save error: {str(e)}")
            else:
                print(f"{progress} {filename:<30} [ERROR] (process) {result[:40]}")
                self.stats.add_error(filename, result)

        self.stats.end_time = time.time()

    def generate_reports(self):
        """Generate summary reports."""
        summary = self.stats.get_summary()

        # Save JSON summary
        summary_path = os.path.join(self.config.OUTPUT_DIR, "filter_summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Save CSV details
        csv_path = os.path.join(self.config.OUTPUT_DIR, "filter_details.csv")
        if self.stats.reports:
            fieldnames = list(asdict(self.stats.reports[0]).keys())
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for report in self.stats.reports:
                    writer.writerow(asdict(report))

        # Save error log
        if self.stats.errors:
            error_path = os.path.join(self.config.OUTPUT_DIR, "errors.json")
            with open(error_path, "w") as f:
                json.dump(self.stats.errors, f, indent=2)

        return summary

    def print_summary(self, summary: dict):
        """Print formatted summary report."""
        print(f"\n{'='*60}")
        print(f"  TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total frames processed  : {summary.get('total_frames', 0)}")
        print(f"Usable frames           : {summary.get('usable_frames', 0)} "
              f"({summary.get('usable_percentage', 0)}%)")
        print(f"Rejected frames         : {summary.get('rejected_frames', 0)}")
        print(f"Processing errors       : {summary.get('errors', 0)}")
        print(f"{'-'*60}")
        print(f"Total processing time   : {summary.get('total_time_seconds', 0):.2f} seconds")
        print(f"Avg time per frame      : {summary.get('avg_time_per_frame_ms', 0):.2f} ms")
        print(f"\n{'-'*60}")
        print(f"QUALITY SCORE STATISTICS:")
        for key, unit in [("quality_score", "/100"), ("blur_score", "(Laplacian var)"),
                          ("brightness_mean", "(0-255)"), ("glare_coverage_pct", "%"),
                          ("bubble_coverage_pct", "%"), ("occlusion_coverage_pct", "%")]:
            if key in summary:
                stats = summary[key]
                print(f"\n{key.replace('_', ' ').title()} {unit}:")
                print(f"  Mean     : {stats['mean']:.2f}")
                print(f"  Std Dev  : {stats['std']:.2f}")
                print(f"  Min/Max  : {stats['min']:.2f} / {stats['max']:.2f}")
                print(f"  Median   : {stats['median']:.2f}")

        print(f"\n{'='*60}")
        print(f"Reports saved to: {self.config.OUTPUT_DIR}/")
        print(f"  - filter_summary.json    - Overall statistics")
        print(f"  - filter_details.csv     - Per-frame metrics")
        if self.stats.errors:
            print(f"  - errors.json            - Processing errors")
        print(f"  - usable/               - High-quality filtered frames")
        print(f"  - rejected/             - Low-quality filtered frames")
        print(f"  - debug_sheets/         - Original + filtered + masks")
        print(f"{'='*60}\n")


# ================================================================
# MAIN ENTRY POINT
# ================================================================

def main():
    """Main entry point."""
    config = FilterTestConfig()
    runner = FilterTestRunner(config)

    # Setup
    runner.setup_output_dirs()

    # Run batch processing
    runner.run_batch()

    # Generate and display reports
    summary = runner.generate_reports()
    runner.print_summary(summary)


if __name__ == "__main__":
    main()
