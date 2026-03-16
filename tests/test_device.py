"""
tests/test_device.py — Tests for Device configuration and channels.
"""

import pytest

try:
    import pydsview
    from pydsview import Config
    pydsview.DSContext(firmware_dir=None).close()
except Exception:
    pytest.skip("pydsview native library not available", allow_module_level=True)


FIRMWARE_DIR = None


@pytest.fixture(scope="module")
def ctx():
    """Single shared context for the whole module."""
    c = pydsview.DSContext(firmware_dir=FIRMWARE_DIR)
    yield c
    c.close()


@pytest.fixture
def demo_device(ctx):
    """Activate the Demo device and yield it."""
    devices = ctx.list_devices()
    demo_idx = 0
    for i, d in enumerate(devices):
        if "demo" in d.name.lower():
            demo_idx = i
            break
    dev = ctx.get_device(demo_idx)
    return dev


class TestDevice:
    def test_basic_properties(self, demo_device):
        dev = demo_device
        assert dev.name
        assert dev.device_type == pydsview.DeviceType.DEMO
        assert repr(dev)

    def test_channels(self, demo_device):
        dev = demo_device
        channels = dev.channels
        assert len(channels) > 0
        ch0 = channels[0]
        assert ch0.index == 0
        assert ch0.name
        assert repr(ch0)

    def test_samplerate(self, demo_device):
        dev = demo_device
        sr = dev.samplerate
        assert sr > 0

        # Set a different samplerate
        dev.samplerate = 1_000_000
        assert dev.samplerate == 1_000_000

    def test_sample_count(self, demo_device):
        dev = demo_device
        dev.sample_count = 10_000
        assert dev.sample_count == 10_000

    def test_enable_channel(self, demo_device):
        dev = demo_device
        # Should not raise
        dev.enable_channel(0, True)
        dev.enable_channel(0, False)
        dev.enable_channel(0, True)

    def test_set_channel_name(self, demo_device):
        dev = demo_device
        dev.set_channel_name(0, "MY_CH")
        channels = dev.channels
        assert channels[0].name == "MY_CH"
