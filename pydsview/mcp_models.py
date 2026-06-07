"""
pydsview.mcp_models -- JSON-friendly helpers for MCP tool responses.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any, Optional


def ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


def error_payload(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error_code": code, "error": message}


def platform_info() -> dict[str, str]:
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def device_scan_item(index: int, info: Any) -> dict[str, Any]:
    handle = getattr(info, "handle", None)
    name = str(getattr(info, "name", ""))
    return {
        "selector": str(index),
        "index": index,
        "name": name,
        "handle": int(handle) if handle is not None else None,
        "handle_hex": f"0x{int(handle):x}" if handle is not None else None,
        "is_demo": "demo" in name.casefold(),
    }


def channel_item(channel: Any) -> dict[str, Any]:
    channel_type = getattr(channel, "type", None)
    coupling = getattr(channel, "coupling", None)
    return {
        "index": int(getattr(channel, "index", -1)),
        "name": str(getattr(channel, "name", "")),
        "type": _enum_name(channel_type),
        "enabled": bool(getattr(channel, "enabled", False)),
        "bits": _maybe_int(getattr(channel, "bits", None)),
        "vdiv": _maybe_int(getattr(channel, "vdiv", None)),
        "coupling": _enum_name(coupling),
        "offset": _maybe_int(getattr(channel, "offset", None)),
        "vfactor": _maybe_int(getattr(channel, "vfactor", None)),
        "trigger": str(getattr(channel, "trigger", "")),
        "trig_value": _maybe_int(getattr(channel, "trig_value", None)),
        "is_logic": bool(getattr(channel, "is_logic", False)),
        "is_dso": bool(getattr(channel, "is_dso", False)),
        "is_analog": bool(getattr(channel, "is_analog", False)),
    }


def active_device_item(device: Any) -> dict[str, Any]:
    return {
        "name": _safe_value(device, "name"),
        "path": _safe_value(device, "path"),
        "driver_name": _safe_value(device, "driver_name"),
        "device_type": _enum_name(_safe_value(device, "device_type")),
        "handle": _maybe_int(_safe_value(device, "handle")),
        "handle_hex": _hex_or_none(_safe_value(device, "handle")),
        "mode": _enum_name(_safe_value(device, "mode")),
        "samplerate_hz": _maybe_int(_safe_get_config(device, "samplerate")),
        "sample_count": _maybe_int(_safe_get_config(device, "sample_count")),
        "channels": [channel_item(channel) for channel in _safe_value(device, "channels", [])],
    }


def artifact_item(path: Path, sidecar: Optional[Path] = None) -> dict[str, Optional[str]]:
    return {
        "path": str(path),
        "format": path.suffix.lower().lstrip("."),
        "metadata_path": str(sidecar) if sidecar else None,
    }


def _safe_value(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _safe_get_config(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _enum_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    name = getattr(value, "name", None)
    return str(name) if name is not None else str(value)


def _maybe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _hex_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"0x{int(value):x}"
    except Exception:
        return None
