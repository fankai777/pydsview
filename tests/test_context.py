"""
tests/test_context.py — Tests for DSContext (using Demo device).
"""

import pytest

try:
    import pydsview
    # Trigger the native lib load early
    pydsview.DSContext(firmware_dir=None).close()
except Exception:
    pytest.skip("pydsview native library not available", allow_module_level=True)


FIRMWARE_DIR = None  # Set to your DSView res/ path if needed


class TestDSContext:
    def test_init_and_close(self):
        ctx = pydsview.DSContext(firmware_dir=FIRMWARE_DIR)
        assert ctx.lib_version  # non-empty string
        ctx.close()

    def test_context_manager(self):
        with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
            assert ctx.lib_version

    def test_list_devices(self):
        with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
            devices = ctx.list_devices()
            assert len(devices) >= 1
            # Demo device should always be present
            names = [d.name for d in devices]
            assert any("Demo" in n or "demo" in n.lower() for n in names), (
                f"Expected Demo device in list, got: {names}"
            )

    def test_get_device_demo(self):
        with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
            devices = ctx.list_devices()
            # Find the demo device index
            demo_idx = 0
            for i, d in enumerate(devices):
                if "demo" in d.name.lower():
                    demo_idx = i
                    break

            dev = ctx.get_device(demo_idx)
            assert dev.name
            assert dev.device_type == pydsview.DeviceType.DEMO
            assert dev.mode in (
                pydsview.DeviceMode.LOGIC,
                pydsview.DeviceMode.DSO,
                pydsview.DeviceMode.ANALOG,
            )

    def test_lib_version_format(self):
        with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
            v = ctx.lib_version
            # Should be something like "1.3.0"
            parts = v.split(".")
            assert len(parts) >= 2
