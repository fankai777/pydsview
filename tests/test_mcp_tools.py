"""
Hardware-free tests for pydsview MCP tool behavior.
"""

from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from pydsview.mcp_safety import McpServerConfig
    from pydsview.mcp_tools import PydsviewMcpTools
except Exception as exc:  # pragma: no cover - depends on native lib availability.
    raise unittest.SkipTest(f"pydsview native library not available: {exc}")


class McpToolsTests(unittest.TestCase):
    def test_status_and_scan_use_fake_context(self) -> None:
        tools = PydsviewMcpTools(context_factory=_FakeContext)

        status = tools.get_library_status()
        scan = tools.list_devices()

        self.assertTrue(status["ok"])
        self.assertEqual(status["libsigrok4dsl_version"], "1.3.0")
        self.assertTrue(scan["ok"])
        self.assertEqual(scan["count"], 2)
        self.assertEqual(scan["devices"][1]["name"], "DSLogic PLus")

    def test_configure_device_applies_samplerate_channels_and_threshold(self) -> None:
        context = _FakeContext()
        tools = PydsviewMcpTools(context_factory=lambda: context)

        result = tools.configure_device(
            device="1",
            samplerate_hz=2_000_000,
            samples=1000,
            channels=[1],
            threshold_v=1.2,
        )

        self.assertTrue(result["ok"])
        device = context.device
        self.assertEqual(device.samplerate, 2_000_000)
        self.assertEqual(device.sample_count, 1000)
        self.assertEqual(device.enabled, {0: False, 1: True})
        self.assertEqual(device.configs["VTH"], 1.2)

    def test_capture_exports_artifact_and_sidecar(self) -> None:
        context = _FakeContext()
        with tempfile.TemporaryDirectory() as tempdir:
            tools = PydsviewMcpTools(
                config=McpServerConfig(artifact_dir=Path(tempdir)),
                context_factory=lambda: context,
            )
            with _patched_exporters():
                result = tools.capture(
                    device="1",
                    samplerate_hz=1_000_000,
                    samples=64,
                    channels=[0],
                    filename="smoke.dsl",
                )

            self.assertTrue(result["ok"])
            artifact = Path(result["artifact"]["path"])
            metadata = Path(result["artifact"]["metadata_path"])
            self.assertEqual(artifact.read_text(encoding="utf-8"), "dsl")
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(payload["request"]["samples"], 64)
            self.assertEqual(payload["request"]["channels"], [0])
            self.assertEqual(payload["libsigrok4dsl_version"], "1.3.0")

    def test_capture_rejects_unbounded_and_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            tools = PydsviewMcpTools(
                config=McpServerConfig(artifact_dir=Path(tempdir), max_samples=10),
                context_factory=_FakeContext,
            )

            unbounded = tools.capture(device="1", samplerate_hz=1_000_000, channels=[0])
            too_many = tools.capture(device="1", samplerate_hz=1_000_000, samples=11, channels=[0])
            outside = tools.capture(
                device="1",
                samplerate_hz=1_000_000,
                samples=1,
                channels=[0],
                filename="..\\outside.dsl",
            )

        self.assertFalse(unbounded["ok"])
        self.assertEqual(unbounded["error_code"], "invalid_capture_bounds")
        self.assertFalse(too_many["ok"])
        self.assertEqual(too_many["error_code"], "samples_too_large")
        self.assertFalse(outside["ok"])
        self.assertEqual(outside["error_code"], "artifact_path_outside_dir")

    def test_async_capture_status_and_export(self) -> None:
        context = _FakeContext()
        with tempfile.TemporaryDirectory() as tempdir:
            tools = PydsviewMcpTools(
                config=McpServerConfig(artifact_dir=Path(tempdir)),
                context_factory=lambda: context,
            )
            started = tools.start_capture(device="1", samplerate_hz=1_000_000, samples=64, channels=[0])
            self.assertTrue(started["ok"])
            session_id = started["session_id"]

            status = tools.capture_status(session_id)
            self.assertTrue(status["ok"])
            self.assertTrue(status["done"])

            with _patched_exporters():
                exported = tools.export_capture(session_id, filename="async.dsl")

            self.assertTrue(exported["ok"])
            self.assertEqual(Path(exported["artifact"]["path"]).read_text(encoding="utf-8"), "dsl")

    def test_capture_profiles_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            tools = PydsviewMcpTools(
                config=McpServerConfig(artifact_dir=Path(tempdir)),
                context_factory=_FakeContext,
            )

            saved = tools.save_capture_profile(
                "small",
                {"samplerate_hz": 1_000_000, "samples": 64, "channels": [0], "output_format": "dsl"},
            )
            listed = tools.list_capture_profiles()
            deleted = tools.delete_capture_profile("small")

        self.assertTrue(saved["ok"])
        self.assertTrue(listed["ok"])
        self.assertEqual(listed["profiles"][0]["name"], "small")
        self.assertTrue(deleted["ok"])

    def test_server_build_registers_tools_with_fake_mcp_module(self) -> None:
        import sys

        fake_mcp = types.ModuleType("mcp")
        fake_server = types.ModuleType("mcp.server")
        fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        fake_fastmcp_module.FastMCP = _FakeFastMCP

        with patch.dict(
            sys.modules,
            {
                "mcp": fake_mcp,
                "mcp.server": fake_server,
                "mcp.server.fastmcp": fake_fastmcp_module,
            },
        ):
            from pydsview.mcp_server import build_server

            server = build_server(PydsviewMcpTools(context_factory=_FakeContext))

        self.assertIn("get_library_status", server.tools)
        self.assertIn("capture", server.tools)


class _FakeInfo:
    def __init__(self, name: str, handle: int) -> None:
        self.name = name
        self.handle = handle


class _FakeChannel:
    def __init__(self, index: int, name: str) -> None:
        self.index = index
        self.name = name
        self.type = types.SimpleNamespace(name="LOGIC")
        self.enabled = True
        self.bits = 1
        self.vdiv = 0
        self.coupling = types.SimpleNamespace(name="DC")
        self.offset = 0
        self.vfactor = 1
        self.trigger = "X"
        self.trig_value = 0
        self.is_logic = True
        self.is_dso = False
        self.is_analog = False


class _FakeDevice:
    def __init__(self) -> None:
        self.name = "DSLogic PLus"
        self.path = "usb"
        self.driver_name = "DSLogic"
        self.device_type = types.SimpleNamespace(name="USB")
        self.handle = 0x2000
        self.mode = types.SimpleNamespace(name="LOGIC")
        self.samplerate = 0
        self.sample_count = 0
        self.channels = [_FakeChannel(0, "D0"), _FakeChannel(1, "D1")]
        self.enabled: dict[int, bool] = {}
        self.configs: dict[str, object] = {}

    def set_config(self, key, value) -> None:
        key_name = getattr(key, "name", str(key))
        self.configs[key_name] = value

    def enable_channel(self, index: int, enabled: bool) -> None:
        self.enabled[index] = enabled

    def capture(self, timeout=None):
        return types.SimpleNamespace(result=True, timeout=timeout)

    def start_capture(self):
        return _FakeSession()


class _FakeSession:
    def __init__(self) -> None:
        self.stopped = False

    def is_done(self) -> bool:
        return True

    def wait(self, timeout=None):
        return types.SimpleNamespace(result=True, timeout=timeout)

    def stop(self) -> None:
        self.stopped = True


class _FakeContext:
    lib_version = "1.3.0"

    def __init__(self) -> None:
        self.device = _FakeDevice()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def close(self) -> None:
        return None

    def list_devices(self):
        return [_FakeInfo("Demo Device", 0x1000), _FakeInfo("DSLogic PLus", 0x2000)]

    def get_device(self, index: int):
        if index != 1:
            raise AssertionError(f"unexpected index {index}")
        return self.device

    def load_session_file(self, path: str):
        return self.device


class _FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

    def run(self, transport: str = "stdio") -> None:
        self.transport = transport


class _patched_exporters:
    def __enter__(self):
        self.patchers = [
            patch("pydsview.mcp_tools.export.Exporter.save_session", lambda result, path: Path(path).write_text("dsl", encoding="utf-8")),
            patch("pydsview.mcp_tools.export.Exporter.to_csv", lambda result, path: Path(path).write_text("csv", encoding="utf-8")),
            patch("pydsview.mcp_tools.export.Exporter.to_vcd", lambda result, path: Path(path).write_text("vcd", encoding="utf-8")),
        ]
        for patcher in self.patchers:
            patcher.start()
        return self

    def __exit__(self, *exc) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()


if __name__ == "__main__":
    unittest.main()
