"""
tests/test_capture.py — Integration test: capture using the Demo device.
"""

import pytest
import numpy as np

try:
    import pydsview
    pydsview.DSContext(firmware_dir=None).close()
except Exception:
    pytest.skip("pydsview native library not available", allow_module_level=True)


FIRMWARE_DIR = None


@pytest.fixture(scope="module")
def ctx():
    c = pydsview.DSContext(firmware_dir=FIRMWARE_DIR)
    yield c
    c.close()


@pytest.fixture
def demo_device(ctx):
    devices = ctx.list_devices()
    demo_idx = 0
    for i, d in enumerate(devices):
        if "demo" in d.name.lower():
            demo_idx = i
            break
    dev = ctx.get_device(demo_idx)
    return dev


class TestCapture:
    def test_sync_capture_logic(self, demo_device):
        dev = demo_device
        dev.samplerate = 1_000_000
        dev.sample_count = 1024

        result = dev.capture(timeout=10.0)

        assert result.mode == pydsview.DeviceMode.LOGIC
        assert result.samplerate == 1_000_000
        assert len(result.raw_data) > 0

        data = result.to_numpy()
        assert data.size > 0

    def test_channel_data(self, demo_device):
        dev = demo_device
        dev.samplerate = 1_000_000
        dev.sample_count = 1024

        result = dev.capture(timeout=10.0)
        ch0 = result.channel_data(0)
        assert ch0.dtype == bool
        assert ch0.size > 0

    def test_async_capture(self, demo_device):
        dev = demo_device
        dev.samplerate = 1_000_000
        dev.sample_count = 1024

        session = dev.start_capture()
        result = session.wait(timeout=10.0)

        assert result.mode == pydsview.DeviceMode.LOGIC
        assert len(result.raw_data) > 0
