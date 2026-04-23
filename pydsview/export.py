"""
pydsview.export — Pure-Python data exporters (CSV, VCD, session zip).
"""

from __future__ import annotations

import csv
import io
import os
import json
import zipfile
from typing import Optional, Sequence

import numpy as np

from ._constants import DeviceMode
from .capture import CaptureResult


class Exporter:
    """Static methods for exporting :class:`CaptureResult` data."""

    @staticmethod
    def to_csv(
        result: CaptureResult,
        path: str,
        channels: Optional[Sequence[int]] = None,
        time_column: bool = True,
        compressed: bool = True,
    ):
        """
        Export logic capture data to CSV.

        Parameters:
            result:      A completed CaptureResult.
            path:        Output file path.
            channels:    Channel indices to include (default: all).
            time_column: If True, prepend a ``Time(s)`` column.
            compressed:  If True (default), only write rows where at least one
                         channel value changed — matches DSView's "压缩数据" mode.
                         If False, write every sample ("原始数据" mode).
        """
        raw = result.to_numpy()
        if raw.size == 0:
            with open(path, "w") as f:
                f.write("")
            return

        if result.mode == DeviceMode.LOGIC:
            # Decode per-channel arrays (ordered by enabled-channel list).
            ch_arrays = result.to_channel_arrays()
            if not ch_arrays:
                with open(path, "w") as f:
                    f.write("")
                return

            # Map channel index -> bool array. If channel_indices isn't
            # populated (older result), fall back to 0..N-1 ordering.
            enabled_indices = result.channel_indices or list(range(len(ch_arrays)))
            ch_map = {idx: arr for idx, arr in zip(enabled_indices, ch_arrays)}

            if channels is None:
                channels = list(enabled_indices)

            Exporter.write_logic_csv(
                path,
                ch_map,
                channels,
                samplerate=result.samplerate,
                time_column=time_column,
                compressed=compressed,
            )

        elif result.mode in (DeviceMode.DSO, DeviceMode.ANALOG):
            period = 1.0 / result.samplerate if result.samplerate else 0.0

            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                header = []
                if time_column:
                    header.append("Time(s)")
                header.append("Value")
                writer.writerow(header)

                for i, val in enumerate(raw):
                    row = []
                    if time_column:
                        row.append(f"{i * period:.15g}")
                    row.append(int(val))
                    writer.writerow(row)

    @staticmethod
    def write_logic_csv(
        path: str,
        ch_map: dict,
        channels: Sequence[int],
        samplerate: int,
        time_column: bool = True,
        compressed: bool = True,
    ):
        """
        Vectorized CSV writer for logic data given pre-decoded channel arrays.

        Much faster than round-tripping through a :class:`CaptureResult` when
        the caller already has per-channel arrays in hand (e.g. worker threads
        doing their own decoding). Same output format as :meth:`to_csv`.

        Parameters:
            path:        Output file path.
            ch_map:      ``{channel_index: np.ndarray}`` — bool or 0/1 uint8,
                         one entry per channel. All arrays must have equal
                         length. Missing channels (listed in ``channels`` but
                         absent here) are emitted as zeros.
            channels:    Channel indices to emit, in column order.
            samplerate:  Samples per second, used for the ``Time(s)`` column.
            time_column: If True, prepend a ``Time(s)`` column.
            compressed:  If True, only emit rows where at least one channel
                         differs from the previous emitted row.
        """
        n_ch = len(channels)
        n_samples = 0
        for c in channels:
            arr = ch_map.get(c)
            if arr is not None:
                n_samples = len(arr)
                break

        header_parts = []
        if time_column:
            header_parts.append("Time(s)")
        header_parts.extend(str(c) for c in channels)
        header_bytes = (",".join(header_parts) + "\n").encode("ascii")

        if n_ch == 0 or n_samples == 0:
            with open(path, "wb") as f:
                f.write(header_bytes)
            return

        period = 1.0 / samplerate if samplerate else 0.0

        # Stack channels into a contiguous (n_samples, n_ch) uint8 buffer.
        # bool and uint8 are both 1 byte so the assignment is effectively a
        # memcpy; no per-sample Python work.
        data = np.empty((n_samples, n_ch), dtype=np.uint8)
        for i, c in enumerate(channels):
            arr = ch_map.get(c)
            if arr is None:
                data[:, i] = 0
            else:
                data[:, i] = arr

        # Change-row detection — one C-level pass over the whole buffer.
        if compressed and n_samples > 1:
            changed = np.any(data[1:] != data[:-1], axis=1)
            keep_idx = np.empty(int(changed.sum()) + 1, dtype=np.int64)
            keep_idx[0] = 0
            keep_idx[1:] = np.nonzero(changed)[0] + 1
        else:
            keep_idx = np.arange(n_samples, dtype=np.int64)

        kept = data[keep_idx]
        n_kept = kept.shape[0]

        # Build each output row's channel segment directly in bytes:
        # [ch0, ',', ch1, ',', ..., chN]  (n_ch chars + n_ch-1 commas)
        row_width = 2 * n_ch - 1
        row_bytes = np.empty((n_kept, row_width), dtype=np.uint8)
        row_bytes[:, 0::2] = kept + 48          # '0' = 0x30, '1' = 0x31
        if n_ch > 1:
            row_bytes[:, 1::2] = 44             # ','

        with open(path, "wb") as f:
            f.write(header_bytes)

            if time_column:
                # Per-row Python loop for %.15g float formatting. Buffered in
                # 1 MB chunks so we don't hold the entire output in memory
                # when the signal doesn't compress well.
                FLUSH = 1 << 20
                buf = bytearray()
                for i in range(n_kept):
                    t = int(keep_idx[i]) * period
                    buf += f"{t:.15g},".encode("ascii")
                    buf += row_bytes[i].tobytes()
                    buf.append(10)              # '\n'
                    if len(buf) >= FLUSH:
                        f.write(buf)
                        buf = bytearray()
                if buf:
                    f.write(buf)
            else:
                # Fully vectorized: append a newline column and write in one go.
                nl_col = np.full((n_kept, 1), 10, dtype=np.uint8)
                out = np.hstack([row_bytes, nl_col])
                f.write(out.tobytes())

    @staticmethod
    def to_vcd(
        result: CaptureResult,
        path: str,
        channels: Optional[Sequence[int]] = None,
        timescale: str = "1ns",
    ):
        """
        Export logic capture data to VCD (Value Change Dump) format.

        Only works for LOGIC mode captures.

        Parameters:
            result:     A completed CaptureResult.
            path:       Output file path.
            channels:   Channel indices to include (default: all).
            timescale:  VCD timescale string (e.g. ``"1ns"``, ``"1us"``).
        """
        if result.mode != DeviceMode.LOGIC:
            raise ValueError("VCD export only supports LOGIC mode")

        ch_arrays = result.to_channel_arrays()
        if not ch_arrays:
            with open(path, "w") as f:
                f.write("")
            return

        enabled_indices = result.channel_indices or list(range(len(ch_arrays)))
        ch_map = {idx: arr for idx, arr in zip(enabled_indices, ch_arrays)}

        if channels is None:
            channels = list(enabled_indices)

        n_samples = len(ch_arrays[0])

        # VCD uses single-character identifiers: '!', '"', '#', ...
        id_chars = [chr(33 + i) for i in range(len(channels))]

        # Calculate time multiplier (samples -> timescale units)
        if result.samplerate:
            # Parse timescale
            ts_value = 1
            ts_unit = "ns"
            for i, c in enumerate(timescale):
                if c.isalpha():
                    ts_value = int(timescale[:i]) if i > 0 else 1
                    ts_unit = timescale[i:]
                    break

            unit_ns = {"s": 1e9, "ms": 1e6, "us": 1e3, "ns": 1, "ps": 1e-3}
            ns_per_ts = ts_value * unit_ns.get(ts_unit, 1)
            ns_per_sample = 1e9 / result.samplerate
            time_mult = ns_per_sample / ns_per_ts
        else:
            time_mult = 1.0

        def sample_value(ch_idx: int, i: int) -> int:
            arr = ch_map.get(ch_idx)
            return int(arr[i]) if arr is not None else 0

        with open(path, "w") as f:
            # Header
            f.write("$timescale {0} $end\n".format(timescale))
            f.write("$scope module logic $end\n")
            for idx, ch in enumerate(channels):
                f.write(f"$var wire 1 {id_chars[idx]} CH{ch} $end\n")
            f.write("$upscope $end\n")
            f.write("$enddefinitions $end\n")

            # Initial values
            f.write("#0\n")
            f.write("$dumpvars\n")
            prev = [sample_value(ch, 0) for ch in channels]
            for idx, val in enumerate(prev):
                f.write(f"{val}{id_chars[idx]}\n")
            f.write("$end\n")

            # Value changes
            for i in range(1, n_samples):
                cur = [sample_value(ch, i) for ch in channels]
                if cur == prev:
                    continue
                t = int(i * time_mult + 0.5)
                f.write(f"#{t}\n")
                for idx, (p, c) in enumerate(zip(prev, cur)):
                    if p != c:
                        f.write(f"{c}{id_chars[idx]}\n")
                prev = cur

    @staticmethod
    def save_session(
        result: CaptureResult,
        path: str,
        channel_indices: Optional[Sequence[int]] = None,
        driver_name: str = "DSLogic",
    ):
        """
        Save capture data in DSView-compatible session format (``*.dsl``).

        The ``.dsl`` format (version 3) is a ZIP file containing:
        - ``header``     — INI-format metadata (GKeyFile compatible)
        - ``decoders``   — JSON array (empty ``[]`` if no decoders)
        - ``session``    — JSON session config
        - ``L-{ch}/{block}`` — Per-channel packed data (1 byte = 8 samples)

        Parameters:
            result:          A completed CaptureResult.
            path:            Output file path (should end in ``.dsl``).
            channel_indices: Actual channel indices (e.g. [0,1,2,...,15]).
                             If None, uses range(channel_count).
            driver_name:     Device driver name for the header.
        """
        if result.mode != DeviceMode.LOGIC:
            raise ValueError("save_session currently only supports LOGIC mode")

        # Decode LA_CROSS_DATA into per-channel arrays
        ch_arrays = result.to_channel_arrays()
        n_ch = len(ch_arrays)
        if n_ch == 0:
            raise ValueError("No channel data to save")

        # Determine channel indices
        if channel_indices is None:
            channel_indices = list(range(n_ch))
        if len(channel_indices) != n_ch:
            raise ValueError(
                f"channel_indices length ({len(channel_indices)}) != "
                f"decoded channel count ({n_ch})"
            )

        total_samples = len(ch_arrays[0])

        # Pack each channel's boolean array into bytes (8 samples per byte)
        LEAF_BLOCK_SAMPLES = 1 << 24  # 16,777,216 samples per block
        n_blocks = max(1, (total_samples + LEAF_BLOCK_SAMPLES - 1) // LEAF_BLOCK_SAMPLES)

        # Build samplerate string
        sr_str = _samplerate_string(result.samplerate)

        # Build INI header
        lines = []
        lines.append("[version]")
        lines.append("version = 3")
        lines.append("")
        lines.append("[header]")
        lines.append(f"driver = {driver_name}")
        lines.append(f"device mode = {result.mode.value}")
        lines.append("capturefile = data")
        lines.append(f"total samples = {total_samples}")
        lines.append(f"total probes = {n_ch}")
        lines.append(f"total blocks = {n_blocks}")
        lines.append(f"samplerate = {sr_str}")
        if result.trigger_pos is not None:
            lines.append(f"trigger pos = {result.trigger_pos}")
        else:
            lines.append("trigger pos = 0")

        # Per-probe entries: probeN = name
        for i, ch_idx in enumerate(channel_indices):
            lines.append(f"probe{ch_idx} = {ch_idx}")
        lines.append("")

        header_text = "\n".join(lines)

        # Minimal session JSON
        session_json = json.dumps({
            "Version": 3,
            "Device": driver_name,
            "DeviceMode": result.mode.value,
        })

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("header", header_text)
            zf.writestr("decoders", "[]")
            zf.writestr("session", session_json)

            # Write per-channel data blocks
            for i, ch_idx in enumerate(channel_indices):
                ch_data = ch_arrays[i]
                for blk in range(n_blocks):
                    start = blk * LEAF_BLOCK_SAMPLES
                    end = min(start + LEAF_BLOCK_SAMPLES, total_samples)
                    block_samples = ch_data[start:end]
                    packed = np.packbits(block_samples, bitorder="little")
                    zf.writestr(f"L-{ch_idx}/{blk}", bytes(packed))


def _samplerate_string(rate: int) -> str:
    """Format samplerate as a human-readable string matching DSView convention."""
    if rate == 0:
        return "0 Hz"
    if rate >= 1_000_000_000:
        if rate % 1_000_000_000 == 0:
            return f"{rate // 1_000_000_000} GHz"
        return f"{rate / 1_000_000_000:.6f} GHz"
    if rate >= 1_000_000:
        if rate % 1_000_000 == 0:
            return f"{rate // 1_000_000} MHz"
        return f"{rate / 1_000_000:.6f} MHz"
    if rate >= 1_000:
        if rate % 1_000 == 0:
            return f"{rate // 1_000} kHz"
        return f"{rate / 1_000:.6f} KHz"
    return f"{rate} Hz"
