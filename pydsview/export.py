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
            # Determine which channels to export
            if channels is None:
                max_bits = result.unitsize * 8 if result.unitsize else 1
                channels = list(range(max_bits))

            period = 1.0 / result.samplerate if result.samplerate else 0.0

            # Build a mask covering only the exported channel bits
            mask = np.uint64(0)
            for ch in channels:
                mask |= np.uint64(1) << np.uint64(ch)

            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                header = []
                if time_column:
                    header.append("Time(s)")
                header.extend(f"CH{ch}" for ch in channels)
                writer.writerow(header)

                prev = None
                for i in range(len(raw)):
                    cur = int(raw[i]) & int(mask)
                    if compressed and prev is not None and cur == prev:
                        continue
                    prev = cur
                    row = []
                    if time_column:
                        row.append(f"{i * period:.15g}")
                    for ch in channels:
                        row.append(int((raw[i] >> ch) & 1))
                    writer.writerow(row)

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

        raw = result.to_numpy()
        if raw.size == 0:
            with open(path, "w") as f:
                f.write("")
            return

        if channels is None:
            max_bits = result.unitsize * 8 if result.unitsize else 1
            channels = list(range(max_bits))

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
            for idx, ch in enumerate(channels):
                val = int((raw[0] >> ch) & 1)
                f.write(f"{val}{id_chars[idx]}\n")
            f.write("$end\n")

            # Value changes
            prev = raw[0]
            for i in range(1, len(raw)):
                cur = raw[i]
                if cur == prev:
                    continue
                t = int(i * time_mult + 0.5)
                f.write(f"#{t}\n")
                diff = cur ^ prev
                for idx, ch in enumerate(channels):
                    if (diff >> ch) & 1:
                        val = int((cur >> ch) & 1)
                        f.write(f"{val}{id_chars[idx]}\n")
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
