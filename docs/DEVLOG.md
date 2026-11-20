
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
