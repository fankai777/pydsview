"""
tests/test_export.py — Tests for CSV/VCD/session export (no hardware needed).
"""

import os
import tempfile
import zipfile
import json

import pytest
import numpy as np

from pydsview._constants import DeviceMode, LogicFormat
from pydsview.capture import CaptureResult
from pydsview.export import Exporter


def _make_logic_result(n_samples=128, unitsize=2, samplerate=1_000_000, n_channels=16):
    """Create a fake CaptureResult with LA_CROSS_DATA format for testing exports.

    Note: n_samples is rounded up to the next multiple of 64 (group size).
    """
    result = CaptureResult()
    result.mode = DeviceMode.LOGIC
    result.samplerate = samplerate
    result.sample_count = n_samples
    result.unitsize = unitsize
    result.channel_count = n_channels
    result.data_format = LogicFormat.CROSS_DATA

    # Build LA_CROSS_DATA: for each group of 64 samples, write N uint64 words
    # CH0 toggles every sample, CH1 is always high, rest are zero
    n_groups = (n_samples + 63) // 64
    words = []
    for g in range(n_groups):
        for ch in range(n_channels):
            word = np.uint64(0)
            samples_in_group = min(64, n_samples - g * 64)
            for bit in range(samples_in_group):
                sample_idx = g * 64 + bit
                if ch == 0 and sample_idx % 2 == 0:
                    word |= np.uint64(1) << np.uint64(bit)
                elif ch == 1:
                    word |= np.uint64(1) << np.uint64(bit)
            words.append(word)

    result.raw_data = bytearray(np.array(words, dtype=np.uint64).tobytes())
    return result


class TestCSVExport:
    def test_basic_csv(self):
        result = _make_logic_result()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            Exporter.to_csv(result, path, channels=[0, 1])
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 129  # header + 128 data rows (2 groups * 64)
            assert lines[0].strip() == "Time(s),0,1"
        finally:
            os.unlink(path)

    def test_csv_no_time(self):
        result = _make_logic_result(n_samples=64)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            Exporter.to_csv(result, path, channels=[0], time_column=False)
            with open(path) as f:
                lines = f.readlines()
            assert "Time" not in lines[0]
        finally:
            os.unlink(path)


class TestVCDExport:
    def test_basic_vcd(self):
        result = _make_logic_result()
        with tempfile.NamedTemporaryFile(suffix=".vcd", delete=False) as f:
            path = f.name
        try:
            Exporter.to_vcd(result, path, channels=[0, 1])
            with open(path) as f:
                content = f.read()
            assert "$timescale" in content
            assert "$var wire" in content
            assert "CH0" in content
        finally:
            os.unlink(path)

    def test_vcd_only_logic(self):
        result = CaptureResult()
        result.mode = DeviceMode.DSO
        with tempfile.NamedTemporaryFile(suffix=".vcd", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError, match="LOGIC"):
                Exporter.to_vcd(result, path)
        finally:
            os.unlink(path)


class TestSessionExport:
    def test_save_session_zip(self):
        result = _make_logic_result()
        with tempfile.NamedTemporaryFile(suffix=".dsl", delete=False) as f:
            path = f.name
        try:
            Exporter.save_session(result, path)
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                # Must have INI header, decoders, session
                assert "header" in names
                assert "decoders" in names
                assert "session" in names

                # Parse the INI header
                header_text = zf.read("header").decode()
                assert "[version]" in header_text
                assert "version = 3" in header_text
                assert "[header]" in header_text
                assert "samplerate = 1 MHz" in header_text
                assert "device mode = 0" in header_text
                assert "total probes = 16" in header_text

                # Must have per-channel data files (L-{ch}/{block})
                assert "L-0/0" in names
                assert "L-1/0" in names
                assert "L-15/0" in names

                # Verify channel 0 data: toggles every sample
                ch0_data = zf.read("L-0/0")
                assert len(ch0_data) > 0
                # Unpack and check first few values
                ch0_bits = np.unpackbits(
                    np.frombuffer(ch0_data[:1], dtype=np.uint8),
                    bitorder="little",
                )
                # CH0 toggles: 1, 0, 1, 0, ...
                assert ch0_bits[0] == 1
                assert ch0_bits[1] == 0

                # Verify channel 1 data: always high
                ch1_data = zf.read("L-1/0")
                ch1_bits = np.unpackbits(
                    np.frombuffer(ch1_data[:1], dtype=np.uint8),
                    bitorder="little",
                )
                assert all(ch1_bits[:8] == 1)
        finally:
            os.unlink(path)
