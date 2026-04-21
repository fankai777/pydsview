"""
pydsview.capture — Synchronous / asynchronous data capture and results.
"""

from __future__ import annotations

import time
import threading
from typing import Optional

import numpy as np

from ._binding import ffi, lib
from ._constants import (
    Config,
    DeviceMode,
    PacketType,
    Event,
    LogicFormat,
)
from .errors import check_sr, DSViewError

# Keep callback references alive to prevent GC while C is using them.
# We never eagerly delete — old callbacks are replaced only when a new
# capture starts.  This avoids the race where post_event_async fires
# after run_capture returns.
_last_callbacks: object = None


class CaptureResult:
    """
    Holds the data from a completed capture.

    Attributes:
        mode:          The device mode at capture time.
        samplerate:    Sampling rate in Hz.
        sample_count:  Number of requested samples.
        trigger_pos:   Trigger position (sample index), or ``None``.
        raw_data:      Raw bytes collected from the device.
        unitsize:      For logic mode — bytes per sample word.
        num_samples:   Actual number of samples received (DSO/ANALOG).
        unit_bits:     Resolution in bits (ANALOG).
        channel_count: Number of enabled channels (for LA_CROSS_DATA decode).
        data_format:   Logic data format (LogicFormat.CROSS_DATA or SPLIT_DATA).
    """

    def __init__(self):
        self.mode: DeviceMode = DeviceMode.LOGIC
        self.samplerate: int = 0
        self.sample_count: int = 0
        self.trigger_pos: Optional[int] = None
        self.raw_data: bytearray = bytearray()
        self.unitsize: int = 0
        self.num_samples: int = 0
        self.unit_bits: int = 8
        self.unit_pitch: int = 1
        self.channel_count: int = 0
        self.channel_indices: list[int] = []
        self.data_format: int = LogicFormat.CROSS_DATA

    def to_channel_arrays(self) -> list[np.ndarray]:
        """
        Decode LA_CROSS_DATA into per-channel boolean arrays.

        In CROSS_DATA format, for N enabled channels each group of N*8 bytes
        contains N uint64 words (one per channel). Each uint64 holds 64
        samples for that channel (bit 0 = first sample in the group).

        Returns a list of N boolean arrays, one per enabled channel.
        """
        if not self.raw_data or self.mode != DeviceMode.LOGIC:
            return []

        n_ch = self.channel_count
        if n_ch <= 0:
            n_ch = self.unitsize * 8 if self.unitsize else 1

        raw = np.frombuffer(self.raw_data, dtype=np.uint64)
        # raw contains interleaved uint64 words: [ch0_g0, ch1_g0, ..., chN_g0, ch0_g1, ...]
        n_groups = len(raw) // n_ch
        if n_groups == 0:
            return [np.array([], dtype=bool) for _ in range(n_ch)]

        # Trim to exact multiple
        raw = raw[: n_groups * n_ch]
        # Reshape to (n_groups, n_ch)
        grouped = raw.reshape(n_groups, n_ch)

        # Bit positions 0..63
        bits = np.arange(64, dtype=np.uint64)

        channels = []
        for ch_idx in range(n_ch):
            # (n_groups,) of uint64
            words = grouped[:, ch_idx]
            # Unpack each word to 64 bits: (n_groups, 64) bool
            unpacked = ((words[:, np.newaxis] >> bits[np.newaxis, :]) & 1).astype(bool)
            # Flatten: group0_bit0..bit63, group1_bit0..bit63, ...
            channels.append(unpacked.ravel())

        return channels

    def to_numpy(self) -> np.ndarray:
        """
        Return data as a numpy array of packed sample words.

        - **LOGIC mode**: Decodes LA_CROSS_DATA back to packed words.
          ``dtype=uint8/uint16/uint32`` depending on unitsize.
        - **DSO mode**: ``dtype=uint8`` (raw ADC values).
        - **ANALOG mode**: ``dtype=uint8`` (raw ADC values).
        """
        if not self.raw_data:
            return np.array([], dtype=np.uint8)

        if self.mode == DeviceMode.LOGIC:
            ch_arrays = self.to_channel_arrays()
            if not ch_arrays:
                return np.array([], dtype=np.uint8)

            n_samples = len(ch_arrays[0])
            if self.unitsize <= 1:
                dt = np.uint8
            elif self.unitsize <= 2:
                dt = np.uint16
            elif self.unitsize <= 4:
                dt = np.uint32
            else:
                dt = np.uint64

            # Reconstruct packed sample words from per-channel booleans
            packed = np.zeros(n_samples, dtype=dt)
            for bit_pos, ch_data in enumerate(ch_arrays):
                packed |= ch_data.astype(dt) << dt(bit_pos)

            return packed

        # DSO / ANALOG — raw byte stream
        return np.frombuffer(self.raw_data, dtype=np.uint8)

    def channel_data(self, index: int) -> np.ndarray:
        """
        Extract a single logic channel as a boolean array.

        ``index`` is the channel bit position (0-based).
        """
        if self.mode != DeviceMode.LOGIC:
            raise DSViewError("channel_data() only works in LOGIC mode")

        ch_arrays = self.to_channel_arrays()
        if not ch_arrays:
            return np.array([], dtype=bool)

        if index < 0 or index >= len(ch_arrays):
            return np.zeros(len(ch_arrays[0]), dtype=bool)

        return ch_arrays[index]

    def dso_data(self) -> np.ndarray:
        """
        Return DSO data.  Shape depends on the number of enabled channels:
        ``(num_samples,)`` for one channel, ``(num_samples, n_ch)`` for multiple.
        """
        if self.mode != DeviceMode.DSO:
            raise DSViewError("dso_data() only works in DSO mode")
        return np.frombuffer(self.raw_data, dtype=np.uint8)

    def analog_data(self) -> np.ndarray:
        """Return analog data as an array of raw ADC values."""
        if self.mode != DeviceMode.ANALOG:
            raise DSViewError("analog_data() only works in ANALOG mode")
        return np.frombuffer(self.raw_data, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Internal capture implementation
# ---------------------------------------------------------------------------


class _CaptureState:
    """Mutable state shared between the main thread and the C callback."""

    def __init__(self):
        self.result = CaptureResult()
        self.done_event = threading.Event()
        self.error: Optional[str] = None
        self.lock = threading.Lock()
        self.started_event = threading.Event()


def _make_datafeed_callback(state: _CaptureState):
    """Create and return a cffi callback that accumulates data into *state*."""

    @ffi.callback("void(const void*, const struct sr_datafeed_packet*)")
    def _on_data(sdi, packet):
        pkt_type = packet.type

        if pkt_type == PacketType.HEADER:
            state.started_event.set()

        elif pkt_type == PacketType.TRIGGER:
            with state.lock:
                state.result.trigger_pos = 0  # mark that trigger was hit

        elif pkt_type == PacketType.LOGIC:
            logic = ffi.cast("const struct sr_datafeed_logic *", packet.payload)
            length = logic.length
            unitsize = logic.unitsize
            data_format = logic.format
            with state.lock:
                state.result.unitsize = unitsize
                state.result.data_format = data_format
                data_ptr = ffi.cast("const uint8_t *", logic.data)
                state.result.raw_data.extend(ffi.buffer(data_ptr, length))

        elif pkt_type == PacketType.DSO:
            dso = ffi.cast("const struct sr_datafeed_dso *", packet.payload)
            num = dso.num_samples
            with state.lock:
                state.result.num_samples = num
                if num > 0 and dso.data != ffi.NULL:
                    data_ptr = ffi.cast("const uint8_t *", dso.data)
                    state.result.raw_data.extend(ffi.buffer(data_ptr, num))

        elif pkt_type == PacketType.ANALOG:
            analog = ffi.cast("const struct sr_datafeed_analog *", packet.payload)
            num = analog.num_samples
            with state.lock:
                state.result.num_samples = num
                state.result.unit_bits = analog.unit_bits
                state.result.unit_pitch = analog.unit_pitch
                if num > 0 and analog.data != ffi.NULL:
                    nbytes = num * max(analog.unit_pitch, 1)
                    data_ptr = ffi.cast("const uint8_t *", analog.data)
                    state.result.raw_data.extend(ffi.buffer(data_ptr, nbytes))

        elif pkt_type == PacketType.END:
            state.done_event.set()

        elif pkt_type == PacketType.OVERFLOW:
            with state.lock:
                state.error = "Data overflow during capture"
            state.done_event.set()

    return _on_data


def _make_event_callback(state: _CaptureState):
    """Create a cffi callback for library events."""

    @ffi.callback("void(int)")
    def _on_event(event):
        if event in (
            Event.COLLECT_TASK_END,
            Event.COLLECT_TASK_END_BY_DETACHED,
            Event.COLLECT_TASK_END_BY_ERROR,
        ):
            if event == Event.COLLECT_TASK_END_BY_ERROR:
                with state.lock:
                    state.error = "Capture ended with error"
            state.done_event.set()

    return _on_event


def _restore_persistent_event_cb():
    """Switch back to the safe no-op event callback from context.py."""
    from .context import _persistent_event_cb
    lib.ds_set_event_callback(_persistent_event_cb)


def run_capture(device, timeout: Optional[float] = None) -> CaptureResult:
    """
    Execute a synchronous capture on the currently active device.

    This is the implementation behind :meth:`Device.capture`.
    """
    global _last_callbacks

    state = _CaptureState()

    # Populate result metadata from current config
    state.result.mode = device.mode
    try:
        state.result.samplerate = device.samplerate
    except DSViewError:
        pass
    try:
        state.result.sample_count = device.sample_count
    except DSViewError:
        pass

    # Count enabled channels for LA_CROSS_DATA decoding
    try:
        enabled = [ch for ch in device.channels if ch.enabled]
        state.result.channel_count = len(enabled)
        state.result.channel_indices = [ch.index for ch in enabled]
    except Exception:
        pass

    # Create callbacks (keep references alive in module-level variable)
    data_cb = _make_datafeed_callback(state)
    event_cb = _make_event_callback(state)
    _last_callbacks = (data_cb, event_cb)

    lib.ds_set_datafeed_callback(data_cb)
    lib.ds_set_event_callback(event_cb)

    ret = lib.ds_start_collect()
    check_sr(ret, "ds_start_collect failed")

    # Wait for completion
    finished = state.done_event.wait(timeout=timeout)
    if not finished:
        lib.ds_stop_collect()
        state.done_event.wait(timeout=5.0)
        raise DSViewError("Capture timed out", code=1)

    # Restore safe no-op event callback before returning.
    # The data callback is only called from the collect thread which has
    # already finished by the time SR_DF_END is received.
    # But the event callback can be called later by post_event_async.
    _restore_persistent_event_cb()

    # Brief pause to let any in-flight async event thread call the
    # (now-safe) persistent callback instead of our local one.
    time.sleep(0.05)

    if state.error:
        raise DSViewError(state.error, code=1)

    return state.result


class CaptureSession:
    """
    An asynchronous capture session.

    Obtain via :meth:`Device.start_capture`.  Poll with :meth:`is_done`
    or block with :meth:`wait`.
    """

    def __init__(self, device):
        self._device = device
        self._state = _CaptureState()

    def start(self):
        global _last_callbacks
        state = self._state

        state.result.mode = self._device.mode
        try:
            state.result.samplerate = self._device.samplerate
        except DSViewError:
            pass
        try:
            state.result.sample_count = self._device.sample_count
        except DSViewError:
            pass

        # Count enabled channels for LA_CROSS_DATA decoding
        try:
            enabled = [ch for ch in self._device.channels if ch.enabled]
            state.result.channel_count = len(enabled)
            state.result.channel_indices = [ch.index for ch in enabled]
        except Exception:
            pass

        data_cb = _make_datafeed_callback(state)
        event_cb = _make_event_callback(state)
        _last_callbacks = (data_cb, event_cb)

        lib.ds_set_datafeed_callback(data_cb)
        lib.ds_set_event_callback(event_cb)

        ret = lib.ds_start_collect()
        check_sr(ret, "ds_start_collect failed")

    def is_done(self) -> bool:
        return self._state.done_event.is_set()

    def wait(self, timeout: Optional[float] = None) -> CaptureResult:
        """Block until the capture completes and return the result."""
        finished = self._state.done_event.wait(timeout=timeout)

        _restore_persistent_event_cb()
        time.sleep(0.05)

        if not finished:
            raise DSViewError("Capture timed out", code=1)
        if self._state.error:
            raise DSViewError(self._state.error, code=1)
        return self._state.result

    def stop(self):
        """Request the C library to stop collecting."""
        lib.ds_stop_collect()
