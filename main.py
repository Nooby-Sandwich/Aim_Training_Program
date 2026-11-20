
"""
main.py

Application entry point.

Creates a small Qt window and connects it to the
Windows Raw Input capture module.
"""

import sys
import csv
import time

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
)

from PySide6.QtCore import QTimer

from capture.raw_input import RawInputCapture


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Aim Diagnostics - Raw Input Recorder")
        self.setMinimumSize(550, 250)

        # Create the capture engine.
        self.capture = RawInputCapture()

        # Track the last UI refresh for approximate reports/second.
        self.last_refresh_time = time.perf_counter()
        self.last_refresh_count = 0

        # -------------------------------------------------
        # UI components
        # -------------------------------------------------

        self.status_label = QLabel("Status: Waiting")
        self.count_label = QLabel("Captured reports: 0")
        self.rate_label = QLabel("Approximate rate: 0 reports/sec")

        self.start_button = QPushButton("Start Recording")
        self.stop_button = QPushButton("Stop Recording")
        self.save_button = QPushButton("Save CSV")

        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(False)

        # -------------------------------------------------
        # Layout
        # -------------------------------------------------

        layout = QVBoxLayout()

        layout.addWidget(self.status_label)
        layout.addWidget(self.count_label)
        layout.addWidget(self.rate_label)

        button_layout = QHBoxLayout()

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_button)

        layout.addLayout(button_layout)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

        # -------------------------------------------------
        # Connect UI actions to application functions
        # -------------------------------------------------

        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.save_button.clicked.connect(self.save_recording)

        # A GUI timer refreshes statistics.
        # This timer is NOT used for mouse event timestamps.
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.refresh_statistics)
        self.ui_timer.start(250)

    # -----------------------------------------------------
    # Register Raw Input after the window has a valid HWND
    # -----------------------------------------------------

    def register_raw_input(self):
        try:
            # winId() provides the native Windows window handle.
            hwnd = int(self.winId())

            self.capture.register_mouse(hwnd)

            self.status_label.setText(
                f"Status: Raw Input registered (HWND={hwnd})"
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Raw Input Registration Failed",
                str(error),
            )

            self.start_button.setEnabled(False)

    # -----------------------------------------------------
    # Start recording
    # -----------------------------------------------------

    def start_recording(self):

        self.capture.start()

        self.last_refresh_count = 0
        self.last_refresh_time = time.perf_counter()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_button.setEnabled(False)

        self.status_label.setText("Status: Recording")

    # -----------------------------------------------------
    # Stop recording
    # -----------------------------------------------------

    def stop_recording(self):

        self.capture.stop()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(True)

        self.status_label.setText("Status: Recording stopped")

    # -----------------------------------------------------
    # Update the UI with capture statistics
    # -----------------------------------------------------

    def refresh_statistics(self):

        current_count = self.capture.count
        current_time = time.perf_counter()

        elapsed = current_time - self.last_refresh_time

        if elapsed > 0:
            # Calculate the number of new reports received
            # since the previous GUI refresh.
            new_reports = current_count - self.last_refresh_count

            approximate_rate = new_reports / elapsed

            self.rate_label.setText(
                f"Approximate rate: {approximate_rate:.1f} reports/sec"
            )

        self.count_label.setText(
            f"Captured reports: {current_count:,}"
        )

        self.last_refresh_count = current_count
        self.last_refresh_time = current_time

        # Display any data-quality issues.
        if self.capture.overflow_count:
            self.status_label.setText(
                f"WARNING: Buffer overflow ({self.capture.overflow_count})"
            )

    # -----------------------------------------------------
    # Export captured samples to CSV
    # -----------------------------------------------------

    def save_recording(self):

        # Avoid writing a snapshot while new events are arriving.
        if self.capture.recording:
            QMessageBox.information(
                self,
                "Recording Active",
                "Stop recording before exporting the CSV.",
            )
            return

        if self.capture.count == 0:
            QMessageBox.warning(
                self,
                "No Data",
                "No mouse samples have been captured.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Mouse Telemetry",
            "mouse_samples.csv",
            "CSV Files (*.csv)",
        )

        if not file_path:
            return

        samples = self.capture.samples[:self.capture.count]

        try:
            with open(
                file_path,
                "w",
                newline="",
                encoding="utf-8",
            ) as file:

                writer = csv.writer(file)

                # Column names describe the data in each row.
                writer.writerow([
                    "qpc_ticks",
                    "elapsed_seconds",
                    "interval_ms",
                    "dx",
                    "dy",
                    "mouse_flags",
                    "button_flags",
                    "button_data",
                    "raw_buttons",
                    "device_handle",
                ])

                first_timestamp = int(samples[0]["qpc_ticks"])
                previous_timestamp = None

                for sample in samples:

                    timestamp = int(sample["qpc_ticks"])

                    # Convert QPC ticks into elapsed seconds.
                    elapsed_seconds = (
                        timestamp - first_timestamp
                    ) / self.capture.qpc_frequency

                    # Calculate the interval since the previous event.
                    if previous_timestamp is None:
                        interval_ms = ""
                    else:
                        interval_ms = (
                            (timestamp - previous_timestamp)
                            / self.capture.qpc_frequency
                        ) * 1000.0

                    writer.writerow([
                        timestamp,
                        elapsed_seconds,
                        interval_ms,
                        int(sample["dx"]),
                        int(sample["dy"]),
                        int(sample["mouse_flags"]),
                        int(sample["button_flags"]),
                        int(sample["button_data"]),
                        int(sample["raw_buttons"]),
                        hex(int(sample["device_handle"])),
                    ])

                    previous_timestamp = timestamp

            QMessageBox.information(
                self,
                "Export Complete",
                f"Saved {self.capture.count:,} samples.\n\n{file_path}",
            )

        except OSError as error:
            QMessageBox.critical(
                self,
                "CSV Export Failed",
                str(error),
            )

    # -----------------------------------------------------
    # Clean shutdown
    # -----------------------------------------------------

    def closeEvent(self, event):

        self.capture.stop()

        super().closeEvent(event)


# ---------------------------------------------------------
# Application entry point
# ---------------------------------------------------------

def main():

    # This implementation uses Windows-specific APIs.
    if sys.platform != "win32":
        raise SystemExit("This application requires Windows.")

    app = QApplication(sys.argv)

    window = MainWindow()

    # Keep a strong reference to the native event filter
    # through the MainWindow instance.
    app.installNativeEventFilter(window.capture)

    window.show()

    # Create the native window handle before registering Raw Input.
    app.processEvents()

    window.register_raw_input()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
