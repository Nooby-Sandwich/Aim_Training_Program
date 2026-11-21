
# Development Log

## 2026-11-20 — Phase 0: Project Initialization

### Completed

- Initialized Git repository.
- Created Python virtual environment.
- Added hardware configuration file.
- Established project directory structure.
- Defined initial technology stack.

### Decisions

- Python-first implementation.
- Windows Raw Input for relative mouse movement.
- QPC for high-resolution receipt timestamps.
- PySide6 for the standalone application.
- NumPy for preallocated telemetry storage.

### Reasoning

The initial implementation prioritizes measurement
accuracy and simplicity over premature optimization.

C++ integration will only be considered if profiling
reveals unacceptable Python capture overhead.

---

## 2026-11-20 — Phase 1: Raw Input Capture

### Objective

Build a standalone foreground mouse telemetry recorder.

### Implementation

- Added Windows Raw Input structure definitions.
- Added mouse device registration.
- Added WM_INPUT event handling.
- Added QPC timestamp acquisition.
- Added preallocated NumPy sample storage.
- Added CSV export.

### Validation

Pending.

### Observations

Pending.

### Problems / Decisions

Pending.

## Phase 1 — Raw Input Capture Validation

**Date:** 21 November 2026

### Hardware configuration
- Mouse: HyperX Pulsefire Haste 2 Wireless
- DPI: 1600
- Polling rate: 1000 Hz
- Connection: Wireless

### Completed
- Windows Raw Input registration
- WM_INPUT event handling
- QPC timestamp collection
- Mouse delta extraction (dx, dy)
- CSV telemetry export
- Automated capture validation
- Event interval percentile analysis

### Horizontal test

| Metric | Result |
|---|---:|
| Records | 16,842 |
| Median interval | 1.008 ms |
| P90 | 1.901 ms |
| P95 | 2.119 ms |
| P99 | 6.132 ms |
| X standard deviation | 3.374 |
| Y standard deviation | 0.509 |

### Vertical test

| Metric | Result |
|---|---:|
| Records | 18,225 |
| Median interval | 1.014 ms |
| P90 | 2.025 ms |
| P95 | 2.152 ms |
| P99 | 5.032 ms |
| X standard deviation | 0.368 |
| Y standard deviation | 1.797 |

### Findings
- Both movement axes are captured successfully.
- QPC timestamps are strictly increasing.
- Horizontal and vertical movement show clear axis separation.
- Median event-arrival intervals are close to the nominal 1 ms polling period.
- Long event-arrival gaps remain under investigation.
- No current evidence justifies migrating the capture implementation to C++.

### Engineering decision
Retain Python for telemetry capture and analysis.

Evaluate Unreal Engine 5 with C++ for the standalone training environment.

### Next milestone
Phase 2: Fixed-target training environment.