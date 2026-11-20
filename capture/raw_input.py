
"""
raw_input.py

Windows Raw Input capture module.

Responsibilities:
- Register our application for foreground mouse Raw Input.
- Decode WM_INPUT messages.
- Capture relative mouse movement.
- Timestamp event receipt using QueryPerformanceCounter.
- Store samples in a preallocated NumPy array.

This module does NOT:
- Move the Windows cursor.
- Install global mouse hooks.
- Interact with commercial games.
- Write files during input capture.
"""

import ctypes
from ctypes import wintypes

import numpy as np

from PySide6.QtCore import QAbstractNativeEventFilter


# ---------------------------------------------------------
# 1. Windows constants
# ---------------------------------------------------------

# Windows message sent when raw input arrives.
WM_INPUT = 0x00FF

# Raw input device type: mouse.
RIM_TYPEMOUSE = 0

# Raw input command: retrieve the complete input structure.
RID_INPUT = 0x10000003

# Generic Desktop Controls usage page.
HID_USAGE_PAGE_GENERIC = 0x01

# Mouse usage within the Generic Desktop Controls page.
HID_USAGE_GENERIC_MOUSE = 0x02

# Flag indicating absolute rather than relative movement.
MOUSE_MOVE_ABSOLUTE = 0x01

# Windows API error return for GetRawInputData.
UINT_ERROR = 0xFFFFFFFF


# ---------------------------------------------------------
# 2. Windows structure definitions
# ---------------------------------------------------------

class RAWINPUTDEVICE(ctypes.Structure):
    """
    Describes which hardware input device our application
    wants to receive input from.
    """

    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    """
    Header present at the beginning of every RAWINPUT record.

    It tells us the device type, structure size and device handle.
    """

    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWMOUSE(ctypes.Structure):
    """
    Mouse-specific portion of a RAWINPUT record.

    ulButtons is a 32-bit union:
    - Lower 16 bits: button flags.
    - Upper 16 bits: button data.

    We preserve both rather than discarding button information.
    """

    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("ulButtons", wintypes.DWORD),
        ("ulRawButtons", wintypes.DWORD),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.DWORD),
    ]


# ---------------------------------------------------------
# 3. Load Windows API functions
# ---------------------------------------------------------

# WinDLL uses the Windows stdcall calling convention.
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


# RegisterRawInputDevices:
# Registers the mouse as an input source for our application.
RegisterRawInputDevices = user32.RegisterRawInputDevices

RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE),
    wintypes.UINT,
    wintypes.UINT,
]

RegisterRawInputDevices.restype = wintypes.BOOL


# GetRawInputData:
# Reads the actual mouse information from the WM_INPUT handle.
GetRawInputData = user32.GetRawInputData

GetRawInputData.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT,
]

GetRawInputData.restype = wintypes.UINT


# QueryPerformanceCounter:
# Provides a high-resolution monotonic counter.
QueryPerformanceCounter = kernel32.QueryPerformanceCounter

QueryPerformanceCounter.argtypes = [
    ctypes.POINTER(ctypes.c_longlong)
]

QueryPerformanceCounter.restype = wintypes.BOOL


# QueryPerformanceFrequency:
# Provides the number of QPC ticks per second.
QueryPerformanceFrequency = kernel32.QueryPerformanceFrequency

QueryPerformanceFrequency.argtypes = [
    ctypes.POINTER(ctypes.c_longlong)
]

QueryPerformanceFrequency.restype = wintypes.BOOL


# ---------------------------------------------------------
# 4. Sample storage format
# ---------------------------------------------------------

# Each input event will be stored in one structured NumPy record.
#
# Using explicit data types keeps memory usage predictable.
SAMPLE_DTYPE = np.dtype([
    ("qpc_ticks", "<u8"),
    ("dx", "<i4"),
    ("dy", "<i4"),
    ("mouse_flags", "<u2"),
    ("button_flags", "<u2"),
    ("button_data", "<u2"),
    ("raw_buttons", "<u4"),
    ("device_handle", "<u8"),
])


# Maximum number of mouse events stored per recording.
MAX_SAMPLES = 1_000_000


# ---------------------------------------------------------
# 5. Raw Input capture class
# ---------------------------------------------------------

class RawInputCapture(QAbstractNativeEventFilter):

    def __init__(self):
        super().__init__()

        # Allocate the sample array once, before recording begins.
        self.samples = np.empty(MAX_SAMPLES, dtype=SAMPLE_DTYPE)

        # Current write position in the preallocated array.
        self.count = 0

        # Number of events that could not be stored.
        self.overflow_count = 0

        # Number of malformed or unreadable input records.
        self.parse_errors = 0

        # Count events that report absolute rather than relative motion.
        self.absolute_events = 0

        # Capture is disabled until the user presses Start.
        self.recording = False

        # Store the QPC frequency once.
        self.qpc_frequency = ctypes.c_longlong()

        if not QueryPerformanceFrequency(
            ctypes.byref(self.qpc_frequency)
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        self.qpc_frequency = self.qpc_frequency.value

        # Preallocate a reusable buffer for one mouse RAWINPUT record.
        # A mouse record fits within this 64-byte buffer on Windows
        # 32-bit and 64-bit systems.
        self.raw_buffer = ctypes.create_string_buffer(64)

        # Store the last registration target for reference.
        self.registered_hwnd = None

    # -----------------------------------------------------
    # 6. Register our application for mouse input
    # -----------------------------------------------------

    def register_mouse(self, hwnd: int):
        """
        Register this application's window for foreground
        Raw Input mouse messages.

        Flags = 0 means:
        - No background input.
        - No suppression of legacy mouse messages.
        """

        device = RAWINPUTDEVICE(
            HID_USAGE_PAGE_GENERIC,
            HID_USAGE_GENERIC_MOUSE,
            0,
            wintypes.HWND(hwnd),
        )

        success = RegisterRawInputDevices(
            ctypes.byref(device),
            1,
            ctypes.sizeof(RAWINPUTDEVICE),
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        self.registered_hwnd = hwnd

    # -----------------------------------------------------
    # 7. Recording controls
    # -----------------------------------------------------

    def start(self):
        """Reset counters and begin a fresh recording."""

        self.count = 0
        self.overflow_count = 0
        self.parse_errors = 0
        self.absolute_events = 0

        self.recording = True

    def stop(self):
        """Stop recording without deleting captured samples."""

        self.recording = False

    # -----------------------------------------------------
    # 8. Decode an individual WM_INPUT message
    # -----------------------------------------------------

    def nativeEventFilter(self, eventType, message):
        """
        Qt calls this method whenever a native Windows message
        passes through its event dispatcher.

        We inspect WM_INPUT and leave all other messages alone.
        """

        # Only process Windows native message types.
        if bytes(eventType) not in (
            b"windows_generic_MSG",
            b"windows_dispatcher_MSG",
        ):
            return False

        # Convert Qt's native message pointer into a Windows MSG.
        msg_pointer = ctypes.cast(
            ctypes.c_void_p(int(message)),
            ctypes.POINTER(wintypes.MSG),
        )

        msg = msg_pointer.contents

        # Ignore everything except raw input messages.
        if msg.message != WM_INPUT:
            return False

        # We don't need to process input while recording is stopped.
        # Returning False allows Qt to continue normal message handling.
        if not self.recording:
            return False

        # Timestamp immediately upon entering the event handler.
        qpc_timestamp = ctypes.c_longlong()

        if not QueryPerformanceCounter(
            ctypes.byref(qpc_timestamp)
        ):
            self.parse_errors += 1
            return False

        # LPARAM contains the HRAWINPUT handle.
        # Mask it to the native pointer width because LPARAM is signed.
        pointer_bits = ctypes.sizeof(ctypes.c_void_p) * 8
        raw_handle = int(msg.lParam) & ((1 << pointer_bits) - 1)

        raw_handle = wintypes.HANDLE(raw_handle)

        # GetRawInputData fills our reusable buffer with the event.
        buffer_size = wintypes.UINT(ctypes.sizeof(self.raw_buffer))

        copied = GetRawInputData(
            raw_handle,
            RID_INPUT,
            ctypes.cast(self.raw_buffer, wintypes.LPVOID),
            ctypes.byref(buffer_size),
            ctypes.sizeof(RAWINPUTHEADER),
        )

        # Validate that Windows successfully returned a complete record.
        required_size = (
            ctypes.sizeof(RAWINPUTHEADER)
            + ctypes.sizeof(RAWMOUSE)
        )

        if copied == UINT_ERROR or copied < required_size:
            self.parse_errors += 1
            return False

        # Interpret the beginning of the buffer as RAWINPUTHEADER.
        # from_buffer avoids allocating a separate copy.
        header = RAWINPUTHEADER.from_buffer(self.raw_buffer)

        # We registered for mouse input, but still verify the device type.
        if header.dwType != RIM_TYPEMOUSE:
            return False

        # Interpret the mouse portion immediately after the header.
        mouse_offset = ctypes.sizeof(RAWINPUTHEADER)

        mouse = RAWMOUSE.from_buffer(
            self.raw_buffer,
            mouse_offset,
        )

        # Absolute mouse movement is not a relative delta.
        # Don't accidentally mix it with our movement measurements.
        if mouse.usFlags & MOUSE_MOVE_ABSOLUTE:
            self.absolute_events += 1
            return False

        # Check whether our preallocated array still has capacity.
        if self.count >= MAX_SAMPLES:
            self.overflow_count += 1
            return False

        # Extract the two 16-bit values packed inside ulButtons.
        button_flags = mouse.ulButtons & 0xFFFF
        button_data = (mouse.ulButtons >> 16) & 0xFFFF

        # Store the event directly into the next available array slot.
        self.samples[self.count] = (
            qpc_timestamp.value,
            mouse.lLastX,
            mouse.lLastY,
            mouse.usFlags,
            button_flags,
            button_data,
            mouse.ulRawButtons,
            int(header.hDevice or 0),
        )

        # Advance the write position.
        self.count += 1

        # IMPORTANT:
        # Return False so Qt continues normal Windows message handling.
        # In particular, foreground WM_INPUT messages require the
        # normal DefWindowProc cleanup path.
        return False
