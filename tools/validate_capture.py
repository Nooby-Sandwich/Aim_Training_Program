"""
validate_capture.py

Inspects a Raw Input CSV recording.

Checks:
- Number of captured records
- Missing or invalid values
- QPC timestamp ordering
- Event interval distribution
- Mouse movement distribution
- X/Y movement balance

This script does not modify the original CSV.
"""

import csv
import sys
from pathlib import Path

import numpy as np


def load_recording(csv_path):
    """Load the CSV columns we need for initial validation."""

    rows = []

    with open(csv_path, "r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows.append(row)

    if not rows:
        raise ValueError("CSV contains no recorded samples.")

    qpc = np.array(
        [int(row["qpc_ticks"]) for row in rows],
        dtype=np.int64
    )

    dx = np.array(
        [int(row["dx"]) for row in rows],
        dtype=np.int32
    )

    dy = np.array(
        [int(row["dy"]) for row in rows],
        dtype=np.int32
    )

    # The first event has no previous event, so its interval is blank.
    # Represent blank values as NaN so NumPy can handle them safely.
    interval_ms = np.array(
        [
            float(row["interval_ms"]) if row["interval_ms"].strip() else np.nan
            for row in rows
        ],
        dtype=np.float64
    )

    return qpc, dx, dy, interval_ms


def describe(name, values):
    """Print basic statistical information about an array."""

    print(f"\n{name}")
    print(f"  Minimum: {np.min(values):.3f}")
    print(f"  Maximum: {np.max(values):.3f}")
    print(f"  Mean:    {np.mean(values):.3f}")
    print(f"  Median:  {np.median(values):.3f}")
    print(f"  Std dev: {np.std(values):.3f}")


def validate(csv_path):

    qpc, dx, dy, intervals = load_recording(csv_path)

    count = len(qpc)

    print("=" * 45)
    print("RAW INPUT RECORDING VALIDATION")
    print("=" * 45)

    print(f"File: {csv_path}")
    print(f"Total records: {count}")

    # QPC timestamps should be non-decreasing.
    timestamp_diffs = np.diff(qpc)

    print("\nTimestamp checks")
    print(f"  Non-increasing timestamps: "
          f"{np.sum(timestamp_diffs <= 0)}")

    # Check movement distribution.
    movement = np.sqrt(dx.astype(float) ** 2 +
                       dy.astype(float) ** 2)

    stationary = np.sum((dx == 0) & (dy == 0))

    print("\nMovement checks")
    print(f"  Stationary records: {stationary}")
    print(f"  Moving records: {count - stationary}")
    print(f"  X-positive records: {np.sum(dx > 0)}")
    print(f"  X-negative records: {np.sum(dx < 0)}")
    print(f"  Y-positive records: {np.sum(dy > 0)}")
    print(f"  Y-negative records: {np.sum(dy < 0)}")

    describe("X displacement (counts)", dx)
    describe("Y displacement (counts)", dy)
    describe("Movement magnitude (counts)", movement)
    
    # Ignore missing intervals, especially the first event's interval.
    valid_intervals = intervals[np.isfinite(intervals)]

        # Analyze timing only when valid intervals are available.
    if len(valid_intervals) > 0:

        describe("Event intervals (milliseconds)", valid_intervals)

        # Percentiles show the distribution of event arrival intervals.
        # p50 = median, p90 = 90% of intervals are at or below this value.
        p50, p90, p95, p99 = np.percentile(
            valid_intervals,
            [50, 90, 95, 99]
        )

        print("\nTiming percentiles")
        print(f"  P50: {p50:.3f} ms")
        print(f"  P90: {p90:.3f} ms")
        print(f"  P95: {p95:.3f} ms")
        print(f"  P99: {p99:.3f} ms")

        # Count long arrival gaps for further investigation.
        # These thresholds are diagnostic flags, not proof of dropped reports.
        print("\nLong interval analysis")

        for threshold in [2, 5, 10, 50]:
            count = np.sum(valid_intervals > threshold)

            percentage = (count / len(valid_intervals)) * 100

            print(
                f"  Intervals > {threshold} ms: "
                f"{count} ({percentage:.3f}%)"
            )

    else:
        print("\nNo valid event intervals found.")

    print("\nValidation warnings")

    if np.any(timestamp_diffs < 0):
        print("  WARNING: QPC timestamps move backwards.")

    if np.any(timestamp_diffs == 0):
        print("  NOTE: Some events share the same QPC timestamp.")

    if np.any(intervals < 0):
        print("  WARNING: Negative event intervals detected.")

    
    # The first event has no previous event, so its interval
    # is expected to be missing. Any additional missing values
    # deserve investigation.
    missing_mask = np.isnan(intervals)

    if missing_mask[0] and np.sum(missing_mask) == 1:
        print("  PASS: First interval is missing as expected.")
    elif np.any(missing_mask):
        print("  WARNING: Unexpected missing interval values detected.")

    # Infinite values are never valid intervals.
    if np.any(np.isinf(intervals)):
        print("  WARNING: Infinite interval values detected.")

    # Negative intervals should never occur.
    finite_intervals = intervals[np.isfinite(intervals)]

    if np.any(finite_intervals < 0):
        print("  WARNING: Negative intervals detected.")


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage:")
        print("python tools/validate_capture.py path/to/recording.csv")
        raise SystemExit(1)

    validate(Path(sys.argv[1]))