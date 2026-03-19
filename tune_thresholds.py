"""
Interactive threshold tuner for SNR Segmentation
Helps you find optimal thresholds based on actual frame metrics
"""
import json
import os
import sys
from pathlib import Path


def load_metrics(metrics_dir="test_extraction"):
    """Load frame metrics from CSV."""
    metrics_csv = os.path.join(metrics_dir, "frame_metrics.csv")

    if not os.path.exists(metrics_csv):
        print(f"Error: Metrics file not found: {metrics_csv}")
        return None

    import csv
    metrics = {}

    with open(metrics_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            metrics[row['frame_name']] = {
                'snr': float(row['snr_db']),
                'sharpness': float(row['sharpness']),
                'specular': float(row['specular_ratio']),
            }

    return metrics


def display_statistics(metrics):
    """Display current statistics."""
    if not metrics:
        return

    snr_values = [m['snr'] for m in metrics.values()]
    sharpness_values = [m['sharpness'] for m in metrics.values()]
    specular_values = [m['specular'] for m in metrics.values()]

    print(f"\n{'='*70}")
    print("CURRENT FRAME STATISTICS")
    print(f"{'='*70}\n")

    print("SNR (Signal-to-Noise Ratio):")
    print(f"  Mean: {sum(snr_values)/len(snr_values):.2f} dB")
    print(f"  Min:  {min(snr_values):.2f} dB")
    print(f"  25%:  {sorted(snr_values)[len(snr_values)//4]:.2f} dB")
    print(f"  50%:  {sorted(snr_values)[len(snr_values)//2]:.2f} dB (median)")
    print(f"  75%:  {sorted(snr_values)[3*len(snr_values)//4]:.2f} dB")
    print(f"  Max:  {max(snr_values):.2f} dB")

    print(f"\nSharpness (Laplacian Variance):")
    print(f"  Mean: {sum(sharpness_values)/len(sharpness_values):.2f}")
    print(f"  Min:  {min(sharpness_values):.2f}")
    print(f"  25%:  {sorted(sharpness_values)[len(sharpness_values)//4]:.2f}")
    print(f"  50%:  {sorted(sharpness_values)[len(sharpness_values)//2]:.2f} (median)")
    print(f"  75%:  {sorted(sharpness_values)[3*len(sharpness_values)//4]:.2f}")
    print(f"  Max:  {max(sharpness_values):.2f}")

    print(f"\nSpecular Highlights (Reflection Ratio):")
    print(f"  Mean: {sum(specular_values)/len(specular_values):.4f}")
    print(f"  Min:  {min(specular_values):.4f}")
    print(f"  25%:  {sorted(specular_values)[len(specular_values)//4]:.4f}")
    print(f"  50%:  {sorted(specular_values)[len(specular_values)//2]:.4f} (median)")
    print(f"  75%:  {sorted(specular_values)[3*len(specular_values)//4]:.4f}")
    print(f"  Max:  {max(specular_values):.4f}")


def test_thresholds(metrics, snr_threshold, sharpness_threshold, specular_threshold):
    """Test how many frames pass the given thresholds."""
    selected = 0
    rejected = 0

    for frame_metrics in metrics.values():
        if (frame_metrics['snr'] >= snr_threshold and
            frame_metrics['sharpness'] >= sharpness_threshold and
            frame_metrics['specular'] <= specular_threshold):
            selected += 1
        else:
            rejected += 1

    total = selected + rejected
    selection_rate = selected / total * 100 if total > 0 else 0

    return selected, rejected, selection_rate


def interactive_tuner():
    """Interactive threshold tuning."""
    print(f"\n{'='*70}")
    print("INTERACTIVE THRESHOLD TUNER")
    print(f"{'='*70}")

    metrics = load_metrics()
    if not metrics:
        return False

    print(f"\nLoaded metrics for {len(metrics)} frames")

    display_statistics(metrics)

    # Current defaults
    snr_th = 25
    sharp_th = 100
    spec_th = 0.05

    while True:
        print(f"\n{'='*70}")
        print("CURRENT THRESHOLDS & RESULTS")
        print(f"{'='*70}\n")

        selected, rejected, rate = test_thresholds(metrics, snr_th, sharp_th, spec_th)

        print(f"SNR Threshold:      >= {snr_th:.2f} dB")
        print(f"Sharpness Threshold: >= {sharp_th:.2f}")
        print(f"Specular Threshold:  <= {spec_th:.4f}")

        print(f"\nResults:")
        print(f"  Selected: {selected} frames ({rate:.1f}%)")
        print(f"  Rejected: {rejected} frames ({100-rate:.1f}%)")

        print(f"\n{'='*70}")
        print("OPTIONS")
        print(f"{'='*70}")
        print("1. Adjust SNR threshold")
        print("2. Adjust Sharpness threshold")
        print("3. Adjust Specular threshold")
        print("4. Quick presets")
        print("5. Save thresholds to SNR_Calculator.py")
        print("6. Exit")

        choice = input("\nSelect option (1-6): ").strip()

        if choice == '1':
            print(f"\nCurrent SNR threshold: {snr_th:.2f} dB")
            print("(Recommended range based on data: 5.0 - 14.0)")
            try:
                snr_th = float(input("Enter new SNR threshold: "))
            except ValueError:
                print("Invalid input")

        elif choice == '2':
            print(f"\nCurrent Sharpness threshold: {sharp_th:.2f}")
            print("(Recommended range based on data: 0.8 - 3.3)")
            try:
                sharp_th = float(input("Enter new Sharpness threshold: "))
            except ValueError:
                print("Invalid input")

        elif choice == '3':
            print(f"\nCurrent Specular threshold: {spec_th:.4f}")
            print("(Recommended range based on data: 0.0016 - 0.57)")
            try:
                spec_th = float(input("Enter new Specular threshold: "))
            except ValueError:
                print("Invalid input")

        elif choice == '4':
            print("\nQuick Presets:")
            print("1. Strict (high quality only)")
            print("2. Balanced (medium quality)")
            print("3. Lenient (accept most frames)")
            print("4. Custom")

            preset = input("Select preset (1-4): ").strip()

            if preset == '1':
                # Strict: top 25% of frames
                snr_vals = sorted([m['snr'] for m in metrics.values()])
                sharp_vals = sorted([m['sharpness'] for m in metrics.values()])
                spec_vals = sorted([m['specular'] for m in metrics.values()])

                idx = 3 * len(snr_vals) // 4
                snr_th = snr_vals[idx]
                sharp_th = sharp_vals[idx]
                spec_th = spec_vals[idx - idx//4] if idx - idx//4 >= 0 else spec_vals[0]

                print(f"Strict preset: SNR>={snr_th:.2f}, Sharp>={sharp_th:.2f}, Spec<={spec_th:.4f}")

            elif preset == '2':
                # Balanced: top 50% of frames
                snr_vals = sorted([m['snr'] for m in metrics.values()])
                sharp_vals = sorted([m['sharpness'] for m in metrics.values()])
                spec_vals = sorted([m['specular'] for m in metrics.values()])

                snr_th = snr_vals[len(snr_vals)//2]
                sharp_th = sharp_vals[len(sharp_vals)//2]
                spec_th = spec_vals[len(spec_vals)//2]

                print(f"Balanced preset: SNR>={snr_th:.2f}, Sharp>={sharp_th:.2f}, Spec<={spec_th:.4f}")

            elif preset == '3':
                # Lenient: accept 75% of frames
                snr_vals = sorted([m['snr'] for m in metrics.values()])
                sharp_vals = sorted([m['sharpness'] for m in metrics.values()])
                spec_vals = sorted([m['specular'] for m in metrics.values()])

                snr_th = snr_vals[len(snr_vals)//4]
                sharp_th = sharp_vals[len(sharp_vals)//4]
                spec_th = spec_vals[3*len(spec_vals)//4]

                print(f"Lenient preset: SNR>={snr_th:.2f}, Sharp>={sharp_th:.2f}, Spec<={spec_th:.4f}")

        elif choice == '5':
            save_thresholds(snr_th, sharp_th, spec_th)
            return True

        elif choice == '6':
            print("Exiting without saving")
            return False

        else:
            print("Invalid option")


def save_thresholds(snr_th, sharp_th, spec_th):
    """Save thresholds to SNR_Calculator.py."""
    snr_calc_path = "GUI/SNR_Calculator.py"

    if not os.path.exists(snr_calc_path):
        print(f"Error: File not found: {snr_calc_path}")
        return False

    with open(snr_calc_path, 'r') as f:
        content = f.read()

    # Replace threshold values
    import re
    content = re.sub(r'snr_threshold = [\d.]+', f'snr_threshold = {snr_th}', content)
    content = re.sub(r'sharpness_threshold = [\d.]+', f'sharpness_threshold = {sharp_th}', content)
    content = re.sub(r'specular_threshold = [\d.]+', f'specular_threshold = {spec_th}', content)

    with open(snr_calc_path, 'w') as f:
        f.write(content)

    print(f"\n{'='*70}")
    print("THRESHOLDS SAVED")
    print(f"{'='*70}")
    print(f"\nUpdated SNR_Calculator.py with:")
    print(f"  snr_threshold = {snr_th}")
    print(f"  sharpness_threshold = {sharp_th}")
    print(f"  specular_threshold = {spec_th}")
    print(f"\nRun the test again to apply new thresholds:")
    print(f"  python run_snr_test.py")
    print(f"  or")
    print(f"  python test_snr_segmentation.py")

    return True


def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("SNR SEGMENTATION - THRESHOLD TUNER")
    print("="*70)

    interactive_tuner()


if __name__ == "__main__":
    main()
