"""
pydsview.mcp_server -- stdio MCP server entry point.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Optional

from .mcp_safety import McpServerConfig
from .mcp_tools import PydsviewMcpTools


def build_server(tools: Optional[PydsviewMcpTools] = None) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit(
            "pydsview MCP support requires the optional MCP dependency. "
            "Install with: pip install 'pydsview[mcp]'"
        ) from exc

    toolset = tools or PydsviewMcpTools()
    server = FastMCP("pydsview")

    @server.tool()
    def get_library_status() -> dict[str, Any]:
        return toolset.get_library_status()

    @server.tool()
    def list_devices(include_demo: bool = True) -> dict[str, Any]:
        return toolset.list_devices(include_demo=include_demo)

    @server.tool()
    def get_device_info(device: str) -> dict[str, Any]:
        return toolset.get_device_info(device=device)

    @server.tool()
    def configure_device(
        device: str,
        samplerate_hz: Optional[int] = None,
        samples: Optional[int] = None,
        duration_ms: Optional[int] = None,
        channels: Optional[list[int]] = None,
        threshold_v: Optional[float] = None,
    ) -> dict[str, Any]:
        return toolset.configure_device(
            device=device,
            samplerate_hz=samplerate_hz,
            samples=samples,
            duration_ms=duration_ms,
            channels=channels,
            threshold_v=threshold_v,
        )

    @server.tool()
    def capture(
        device: Optional[str] = None,
        samplerate_hz: Optional[int] = None,
        samples: Optional[int] = None,
        duration_ms: Optional[int] = None,
        channels: Optional[list[int]] = None,
        output_format: str = "dsl",
        filename: Optional[str] = None,
        overwrite: bool = False,
        timeout_s: Optional[float] = None,
        threshold_v: Optional[float] = None,
    ) -> dict[str, Any]:
        return toolset.capture(
            device=device,
            samplerate_hz=samplerate_hz,
            samples=samples,
            duration_ms=duration_ms,
            channels=channels,
            output_format=output_format,
            filename=filename,
            overwrite=overwrite,
            timeout_s=timeout_s,
            threshold_v=threshold_v,
        )

    @server.tool()
    def start_capture(
        device: Optional[str] = None,
        samplerate_hz: Optional[int] = None,
        samples: Optional[int] = None,
        duration_ms: Optional[int] = None,
        channels: Optional[list[int]] = None,
        threshold_v: Optional[float] = None,
        timeout_s: Optional[float] = None,
    ) -> dict[str, Any]:
        return toolset.start_capture(
            device=device,
            samplerate_hz=samplerate_hz,
            samples=samples,
            duration_ms=duration_ms,
            channels=channels,
            threshold_v=threshold_v,
            timeout_s=timeout_s,
        )

    @server.tool()
    def capture_status(session_id: str) -> dict[str, Any]:
        return toolset.capture_status(session_id=session_id)

    @server.tool()
    def stop_capture(session_id: str) -> dict[str, Any]:
        return toolset.stop_capture(session_id=session_id)

    @server.tool()
    def export_capture(
        session_id: str,
        output_format: str = "dsl",
        filename: Optional[str] = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        return toolset.export_capture(
            session_id=session_id,
            output_format=output_format,
            filename=filename,
            overwrite=overwrite,
        )

    @server.tool()
    def load_session_file(path: str) -> dict[str, Any]:
        return toolset.load_session_file(path=path)

    @server.tool()
    def set_trigger(
        device: str,
        enabled: bool,
        mode: str = "simple",
        position_percent: Optional[int] = None,
        channel_triggers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return toolset.set_trigger(
            device=device,
            enabled=enabled,
            mode=mode,
            position_percent=position_percent,
            channel_triggers=channel_triggers,
        )

    @server.tool()
    def save_capture_profile(name: str, profile: dict[str, Any]) -> dict[str, Any]:
        return toolset.save_capture_profile(name=name, profile=profile)

    @server.tool()
    def list_capture_profiles() -> dict[str, Any]:
        return toolset.list_capture_profiles()

    @server.tool()
    def delete_capture_profile(name: str) -> dict[str, Any]:
        return toolset.delete_capture_profile(name=name)

    @server.tool()
    def capture_with_profile(
        name: str,
        device: Optional[str] = None,
        filename: Optional[str] = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        return toolset.capture_with_profile(
            name=name,
            device=device,
            filename=filename,
            overwrite=overwrite,
        )

    return server


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="pydsview-mcp", description="Run the pydsview MCP server.")
    parser.add_argument("--transport", choices=["stdio"], default="stdio", help="MCP transport.")
    parser.add_argument("--artifact-dir", type=Path, help="Directory for capture artifacts.")
    parser.add_argument("--max-samples", type=int, help="Maximum samples allowed for one capture.")
    parser.add_argument("--max-duration-ms", type=int, help="Maximum duration allowed for one capture.")
    parser.add_argument("--allow-overwrite", action="store_true", help="Allow overwriting existing artifacts.")
    parser.add_argument("--default-timeout-s", type=float, help="Default synchronous capture timeout.")
    args = parser.parse_args(argv)

    config = McpServerConfig.from_env(
        artifact_dir=args.artifact_dir,
        max_samples=args.max_samples,
        max_duration_ms=args.max_duration_ms,
        allow_overwrite=args.allow_overwrite if args.allow_overwrite else None,
        default_timeout_s=args.default_timeout_s,
    )
    server = build_server(PydsviewMcpTools(config=config))
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
