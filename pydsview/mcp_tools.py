"""
pydsview.mcp_tools -- tool implementations used by the MCP server.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import pydsview

from . import export
from ._constants import Config, TriggerMode
from .mcp_models import (
    active_device_item,
    artifact_item,
    device_scan_item,
    error_payload,
    ok,
    platform_info,
)
from .mcp_safety import (
    CaptureLock,
    McpServerConfig,
    McpToolError,
    resolve_artifact_path,
    sidecar_path,
    validate_capture_bounds,
)
from .trigger import TriggerConfig


ContextFactory = Callable[[], Any]


@dataclass
class ActiveCapture:
    session_id: str
    context: Any
    device: Any
    session: Any
    request: dict[str, Any]
    started_at: float
    libsigrok4dsl_version: Optional[str] = None
    result: Optional[Any] = None
    completed_at: Optional[float] = None
    stopped: bool = False
    error: Optional[str] = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)


class PydsviewMcpTools:
    def __init__(
        self,
        *,
        config: Optional[McpServerConfig] = None,
        context_factory: Optional[ContextFactory] = None,
        capture_lock: Optional[CaptureLock] = None,
    ) -> None:
        self.config = config or McpServerConfig.from_env()
        self.context_factory = context_factory or pydsview.DSContext
        self.capture_lock = capture_lock or CaptureLock()
        self._active_capture: Optional[ActiveCapture] = None

    # ---- PR 1: status and scan -------------------------------------------------

    def get_library_status(self) -> dict[str, Any]:
        firmware_dir = Path(pydsview.__file__).parent / "res"
        payload = {
            "pydsview_version": getattr(pydsview, "__version__", None),
            "firmware_dir": str(firmware_dir),
            **platform_info(),
        }
        try:
            with self.context_factory() as context:
                return ok(**payload, libsigrok4dsl_version=str(context.lib_version))
        except Exception as exc:
            return {
                "ok": False,
                **payload,
                "libsigrok4dsl_version": None,
                "error_code": "library_unavailable",
                "error": str(exc),
            }

    def list_devices(self, include_demo: bool = True) -> dict[str, Any]:
        try:
            with self.context_factory() as context:
                devices = [
                    device_scan_item(index, info)
                    for index, info in enumerate(context.list_devices())
                ]
                if not include_demo:
                    devices = [device for device in devices if not device["is_demo"]]
                return ok(devices=devices, count=len(devices))
        except Exception as exc:
            return error_payload("scan_failed", str(exc))

    # ---- PR 2: device info, configure, sync capture ----------------------------

    def get_device_info(self, device: str) -> dict[str, Any]:
        try:
            with self.context_factory() as context:
                selected = self._select_device(context, device)
                return ok(device=active_device_item(selected))
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("get_device_info_failed", str(exc))

    def configure_device(
        self,
        device: str,
        samplerate_hz: Optional[int] = None,
        samples: Optional[int] = None,
        duration_ms: Optional[int] = None,
        channels: Optional[list[int]] = None,
        threshold_v: Optional[float] = None,
    ) -> dict[str, Any]:
        try:
            with self.context_factory() as context:
                selected = self._select_device(context, device)
                self._apply_capture_config(
                    selected,
                    samplerate_hz=samplerate_hz,
                    samples=samples,
                    duration_ms=duration_ms,
                    channels=channels,
                    threshold_v=threshold_v,
                    trigger=None,
                    require_bound=False,
                )
                return ok(device=active_device_item(selected))
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("configure_device_failed", str(exc))

    def capture(
        self,
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
        trigger_channel: Optional[int] = None,
        trigger: Optional[str] = None,
        trigger_position_percent: Optional[int] = None,
    ) -> dict[str, Any]:
        try:
            validate_capture_bounds(self.config, samples=samples, duration_ms=duration_ms)
            trigger_request = _normalize_simple_trigger(
                trigger_channel=trigger_channel,
                trigger=trigger,
                trigger_position_percent=trigger_position_percent,
            )
            path = resolve_artifact_path(
                self.config,
                filename=filename,
                output_format=output_format,
                overwrite=overwrite,
            )
            self._ensure_no_active_capture()
            self.capture_lock.acquire()
            started_at = time.time()
            try:
                with self.context_factory() as context:
                    selected = self._select_device(context, device)
                    self._apply_capture_config(
                        selected,
                        samplerate_hz=samplerate_hz,
                        samples=samples,
                        duration_ms=duration_ms,
                        channels=channels,
                        threshold_v=threshold_v,
                        trigger=trigger_request,
                        require_bound=True,
                    )
                    if trigger_request:
                        result = self._run_triggered_capture(
                            selected,
                            timeout_s=timeout_s or self.config.default_timeout_s,
                        )
                    else:
                        result = selected.capture(timeout=timeout_s or self.config.default_timeout_s)
                    self._export_result(result, path, output_format)
                    metadata_path = self._write_capture_metadata(
                        path,
                        request={
                            "device": device,
                            "samplerate_hz": samplerate_hz,
                            "samples": samples,
                            "duration_ms": duration_ms,
                            "channels": channels or [],
                            "output_format": output_format,
                            "threshold_v": threshold_v,
                            "timeout_s": timeout_s or self.config.default_timeout_s,
                            "trigger": trigger_request,
                        },
                        started_at=started_at,
                        completed_at=time.time(),
                        selected_device=selected,
                        libsigrok4dsl_version=_safe_lib_version(context),
                        capture_result=result,
                    )
                    return ok(artifact=artifact_item(path, metadata_path))
            finally:
                self.capture_lock.release()
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("capture_failed", str(exc))

    # ---- PR 3: async capture lifecycle ----------------------------------------

    def start_capture(
        self,
        device: Optional[str] = None,
        samplerate_hz: Optional[int] = None,
        samples: Optional[int] = None,
        duration_ms: Optional[int] = None,
        channels: Optional[list[int]] = None,
        threshold_v: Optional[float] = None,
        timeout_s: Optional[float] = None,
        trigger_channel: Optional[int] = None,
        trigger: Optional[str] = None,
        trigger_position_percent: Optional[int] = None,
    ) -> dict[str, Any]:
        try:
            validate_capture_bounds(self.config, samples=samples, duration_ms=duration_ms)
            trigger_request = _normalize_simple_trigger(
                trigger_channel=trigger_channel,
                trigger=trigger,
                trigger_position_percent=trigger_position_percent,
            )
            self._ensure_no_active_capture()
            self.capture_lock.acquire()
            context = self.context_factory()
            context.__enter__()
            try:
                selected = self._select_device(context, device)
                self._apply_capture_config(
                    selected,
                    samplerate_hz=samplerate_hz,
                    samples=samples,
                    duration_ms=duration_ms,
                    channels=channels,
                    threshold_v=threshold_v,
                    trigger=trigger_request,
                    require_bound=True,
                )
                session = selected.start_capture()
                session_id = str(uuid.uuid4())
                request = {
                    "device": device,
                    "samplerate_hz": samplerate_hz,
                    "samples": samples,
                    "duration_ms": duration_ms,
                    "channels": channels or [],
                    "threshold_v": threshold_v,
                    "timeout_s": timeout_s or self.config.default_timeout_s,
                    "trigger": trigger_request,
                }
                self._active_capture = ActiveCapture(
                    session_id=session_id,
                    context=context,
                    device=selected,
                    session=session,
                    request=request,
                    started_at=time.time(),
                    libsigrok4dsl_version=_safe_lib_version(context),
                )
                return ok(session_id=session_id, request=request)
            except Exception:
                _close_context(context)
                self.capture_lock.release()
                raise
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("start_capture_failed", str(exc))

    def capture_status(self, session_id: str) -> dict[str, Any]:
        active = self._active_capture
        if active is None or active.session_id != session_id:
            return error_payload("session_not_found", f"unknown capture session: {session_id}")
        self._update_active_result(active)
        elapsed = time.time() - active.started_at
        return ok(
            session_id=session_id,
            running=active.result is None and not active.stopped and active.error is None,
            done=active.result is not None,
            stopped=active.stopped,
            error=active.error,
            elapsed_s=elapsed,
            artifacts=active.artifacts,
        )

    def stop_capture(self, session_id: str) -> dict[str, Any]:
        active = self._active_capture
        if active is None or active.session_id != session_id:
            return error_payload("session_not_found", f"unknown capture session: {session_id}")
        try:
            active.session.stop()
            active.stopped = True
            return ok(session_id=session_id, stopped=True)
        except Exception as exc:
            active.error = str(exc)
            return error_payload("stop_capture_failed", str(exc))
        finally:
            self._finish_active_capture()

    def export_capture(
        self,
        session_id: str,
        output_format: str = "dsl",
        filename: Optional[str] = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        active = self._active_capture
        if active is None or active.session_id != session_id:
            return error_payload("session_not_found", f"unknown capture session: {session_id}")
        try:
            self._update_active_result(active)
            if active.result is None:
                return error_payload("capture_not_done", "capture is still running")
            path = resolve_artifact_path(
                self.config,
                filename=filename,
                output_format=output_format,
                overwrite=overwrite,
            )
            self._export_result(active.result, path, output_format)
            metadata_path = self._write_capture_metadata(
                path,
                request={**active.request, "output_format": output_format},
                started_at=active.started_at,
                completed_at=active.completed_at or time.time(),
                selected_device=active.device,
                libsigrok4dsl_version=active.libsigrok4dsl_version,
            )
            item = artifact_item(path, metadata_path)
            active.artifacts.append(item)
            return ok(session_id=session_id, artifact=item)
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            active.error = str(exc)
            return error_payload("export_capture_failed", str(exc))
        finally:
            self._finish_active_capture()

    def load_session_file(self, path: str) -> dict[str, Any]:
        try:
            session_path = Path(path).expanduser().resolve()
            if not session_path.exists():
                raise McpToolError("session_not_found", f"session file does not exist: {session_path}")
            with self.context_factory() as context:
                device = context.load_session_file(str(session_path))
                return ok(path=str(session_path), device=active_device_item(device))
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("load_session_failed", str(exc))

    # ---- PR 4: triggers and profiles ------------------------------------------

    def set_trigger(
        self,
        device: str,
        enabled: bool,
        mode: str = "simple",
        position_percent: Optional[int] = None,
        channel_triggers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        try:
            with self.context_factory() as context:
                selected = self._select_device(context, device)
                trigger = TriggerConfig()
                trigger.reset()
                trigger.set_enabled(enabled)
                trigger.set_mode(_parse_trigger_mode(mode))
                if position_percent is not None:
                    trigger.set_position(position_percent)
                for channel, spec in (channel_triggers or {}).items():
                    trigger.set_channel_trigger(int(channel), spec)
                return ok(device=active_device_item(selected), trigger={"enabled": trigger.enabled})
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("set_trigger_failed", str(exc))

    def save_capture_profile(self, name: str, profile: dict[str, Any]) -> dict[str, Any]:
        try:
            path = self._profile_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = self._normalize_profile(profile)
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return ok(name=name, path=str(path), profile=payload)
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("save_profile_failed", str(exc))

    def list_capture_profiles(self) -> dict[str, Any]:
        profile_dir = self.config.profile_dir
        if not profile_dir.exists():
            return ok(profiles=[])
        profiles = []
        for path in sorted(profile_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                payload = None
            profiles.append({"name": path.stem, "path": str(path), "profile": payload})
        return ok(profiles=profiles)

    def delete_capture_profile(self, name: str) -> dict[str, Any]:
        try:
            path = self._profile_path(name)
            if not path.exists():
                return error_payload("profile_not_found", f"unknown capture profile: {name}")
            path.unlink()
            return ok(name=name, deleted=True)
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("delete_profile_failed", str(exc))

    def capture_with_profile(
        self,
        name: str,
        device: Optional[str] = None,
        filename: Optional[str] = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        try:
            path = self._profile_path(name)
            if not path.exists():
                return error_payload("profile_not_found", f"unknown capture profile: {name}")
            profile = json.loads(path.read_text(encoding="utf-8"))
            return self.capture(
                device=device or profile.get("device"),
                samplerate_hz=profile.get("samplerate_hz"),
                samples=profile.get("samples"),
                duration_ms=profile.get("duration_ms"),
                channels=profile.get("channels"),
                output_format=profile.get("output_format", "dsl"),
                filename=filename,
                overwrite=overwrite,
                timeout_s=profile.get("timeout_s"),
                threshold_v=profile.get("threshold_v"),
                trigger_channel=profile.get("trigger_channel"),
                trigger=profile.get("trigger"),
                trigger_position_percent=profile.get("trigger_position_percent"),
            )
        except McpToolError as exc:
            return exc.to_dict()
        except Exception as exc:
            return error_payload("capture_with_profile_failed", str(exc))

    # ---- internal helpers ------------------------------------------------------

    def _select_device(self, context: Any, selector: Optional[str]) -> Any:
        devices = list(context.list_devices())
        if not devices:
            raise McpToolError("no_devices", "pydsview found no devices")
        if selector:
            selected = _find_device_index(devices, selector)
            if selected is None:
                raise McpToolError("device_not_found", f"device selector did not match: {selector!r}")
            return context.get_device(selected)
        non_demo = [
            index
            for index, info in enumerate(devices)
            if "demo" not in str(getattr(info, "name", "")).casefold()
        ]
        if len(non_demo) == 1:
            return context.get_device(non_demo[0])
        if len(devices) == 1:
            return context.get_device(0)
        raise McpToolError("ambiguous_device", "multiple devices found; pass a device selector")

    def _apply_capture_config(
        self,
        device: Any,
        *,
        samplerate_hz: Optional[int],
        samples: Optional[int],
        duration_ms: Optional[int],
        channels: Optional[list[int]],
        threshold_v: Optional[float],
        trigger: Optional[dict[str, Any]],
        require_bound: bool,
    ) -> None:
        if require_bound:
            validate_capture_bounds(self.config, samples=samples, duration_ms=duration_ms)
        elif samples is not None and duration_ms is not None:
            raise McpToolError("invalid_capture_bounds", "configure_device accepts samples or duration_ms, not both")
        if trigger:
            device.set_config(Config.OPERATION_MODE, 1)
        if threshold_v is not None:
            device.set_config(Config.VTH, float(threshold_v))
        if samplerate_hz is not None:
            if samplerate_hz <= 0:
                raise McpToolError("invalid_samplerate", "samplerate_hz must be positive")
            device.samplerate = int(samplerate_hz)
        if samples is not None:
            device.sample_count = int(samples)
        if duration_ms is not None:
            device.set_config(Config.LIMIT_MSEC, int(duration_ms))
        if trigger:
            device.set_config(Config.RLE, False)
            device.set_config(Config.LOOP_MODE, False)
        if channels is not None:
            self._configure_channels(device, channels)
        if trigger:
            self._apply_simple_trigger(trigger)

    def _configure_channels(self, device: Any, channels: list[int]) -> None:
        available = {int(channel.index) for channel in device.channels if getattr(channel, "is_logic", True)}
        requested = {int(channel) for channel in channels}
        missing = requested - available
        if missing:
            raise McpToolError("unknown_channel", f"unknown logic channels: {sorted(missing)}")
        for channel in available:
            device.enable_channel(channel, channel in requested)

    def _export_result(self, result: Any, path: Path, output_format: str) -> None:
        output_format = output_format.lower().lstrip(".")
        if output_format == "dsl":
            export.Exporter.save_session(result, str(path), channel_indices=getattr(result, "channel_indices", None))
        elif output_format == "csv":
            export.Exporter.to_csv(result, str(path))
        elif output_format == "vcd":
            export.Exporter.to_vcd(result, str(path))
        else:
            raise McpToolError("unsupported_output_format", "output_format must be one of dsl, csv, or vcd")

    def _write_capture_metadata(
        self,
        path: Path,
        *,
        request: dict[str, Any],
        started_at: float,
        completed_at: float,
        selected_device: Any,
        libsigrok4dsl_version: Optional[str] = None,
        capture_result: Optional[Any] = None,
    ) -> Path:
        metadata_path = sidecar_path(path)
        payload = {
            "pydsview_version": getattr(pydsview, "__version__", None),
            "libsigrok4dsl_version": libsigrok4dsl_version,
            "artifact": str(path),
            "request": request,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_s": completed_at - started_at,
            "device": active_device_item(selected_device),
            "result": _capture_result_item(capture_result),
        }
        metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return metadata_path

    def _apply_simple_trigger(self, trigger_request: dict[str, Any]) -> None:
        trigger = TriggerConfig()
        trigger.reset()
        trigger.set_mode(TriggerMode.SIMPLE)
        trigger.set_position(int(trigger_request["position_percent"]))
        trigger.set_channel_trigger(int(trigger_request["channel"]), str(trigger_request["spec"]))
        trigger.set_enabled(True)

    def _run_triggered_capture(self, device: Any, *, timeout_s: float) -> Any:
        session = device.start_capture()
        started_at = time.time()
        while not session.is_done():
            if time.time() - started_at > timeout_s:
                session.stop()
                raise McpToolError("trigger_timeout", f"triggered capture timed out after {timeout_s:g} seconds")
            time.sleep(0.05)
        return session.wait(timeout=5.0)

    def _ensure_no_active_capture(self) -> None:
        if self._active_capture is not None:
            raise McpToolError("capture_busy", "another pydsview capture is already active")

    def _update_active_result(self, active: ActiveCapture) -> None:
        if active.result is not None or active.stopped or active.error is not None:
            return
        try:
            if active.session.is_done():
                active.result = active.session.wait(timeout=0)
                active.completed_at = time.time()
        except Exception as exc:
            active.error = str(exc)
            self._finish_active_capture()

    def _finish_active_capture(self) -> None:
        active = self._active_capture
        if active is not None:
            _close_context(active.context)
        self._active_capture = None
        self.capture_lock.release()

    def _profile_path(self, name: str) -> Path:
        safe = name.strip()
        if not safe or any(char in safe for char in "\\/:*?\"<>|"):
            raise McpToolError("invalid_profile_name", "profile name must be a simple file stem")
        return self.config.profile_dir / f"{safe}.json"

    def _normalize_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        output_format = str(profile.get("output_format", "dsl")).lower().lstrip(".")
        samples = profile.get("samples")
        duration_ms = profile.get("duration_ms")
        trigger_request = _normalize_simple_trigger(
            trigger_channel=profile.get("trigger_channel"),
            trigger=profile.get("trigger"),
            trigger_position_percent=profile.get("trigger_position_percent"),
        )
        validate_capture_bounds(self.config, samples=samples, duration_ms=duration_ms)
        if output_format not in {"dsl", "csv", "vcd"}:
            raise McpToolError("unsupported_output_format", "profile output_format must be dsl, csv, or vcd")
        return {
            "device": profile.get("device"),
            "samplerate_hz": profile.get("samplerate_hz"),
            "samples": samples,
            "duration_ms": duration_ms,
            "channels": profile.get("channels") or [],
            "threshold_v": profile.get("threshold_v"),
            "timeout_s": profile.get("timeout_s"),
            "trigger_channel": trigger_request["channel"] if trigger_request else None,
            "trigger": trigger_request["spec"] if trigger_request else None,
            "trigger_position_percent": trigger_request["position_percent"] if trigger_request else None,
            "output_format": output_format,
        }


def _normalize_simple_trigger(
    *,
    trigger_channel: Optional[int],
    trigger: Optional[str],
    trigger_position_percent: Optional[int],
) -> Optional[dict[str, Any]]:
    if trigger_channel is None and trigger is None and trigger_position_percent is None:
        return None
    if trigger_channel is None or trigger is None:
        raise McpToolError("invalid_trigger", "triggered capture requires trigger_channel and trigger")
    position = 50 if trigger_position_percent is None else int(trigger_position_percent)
    if not 0 <= position <= 90:
        raise McpToolError("invalid_trigger", "trigger_position_percent must be between 0 and 90")
    spec = str(trigger).strip().upper()
    if spec not in {"R", "F", "1", "0", "C"}:
        raise McpToolError("invalid_trigger", "trigger must be one of R, F, 1, 0, or C")
    return {
        "channel": int(trigger_channel),
        "spec": spec,
        "position_percent": position,
        "mode": "simple",
    }


def _capture_result_item(result: Optional[Any]) -> Optional[dict[str, Any]]:
    if result is None:
        return None
    raw_data = getattr(result, "raw_data", None)
    raw_bytes = len(raw_data) if raw_data is not None else None
    channel_indices = getattr(result, "channel_indices", None)
    return {
        "samplerate_hz": getattr(result, "samplerate", None),
        "sample_count": getattr(result, "sample_count", None),
        "trigger_pos": getattr(result, "trigger_pos", None),
        "raw_bytes": raw_bytes,
        "channel_count": getattr(result, "channel_count", None),
        "channel_indices": list(channel_indices) if channel_indices is not None else None,
    }


def _find_device_index(devices: list[Any], selector: str) -> Optional[int]:
    normalized = selector.strip().casefold()
    if normalized.isdigit():
        index = int(normalized)
        return index if 0 <= index < len(devices) else None
    for index, info in enumerate(devices):
        name = str(getattr(info, "name", "")).casefold()
        handle = getattr(info, "handle", None)
        if normalized == name or normalized in name:
            return index
        if handle is not None and normalized in {str(handle).casefold(), f"0x{int(handle):x}"}:
            return index
    return None


def _parse_trigger_mode(mode: str) -> TriggerMode:
    normalized = mode.strip().upper()
    aliases = {
        "SIMPLE": TriggerMode.SIMPLE,
        "ADV": TriggerMode.ADV,
        "ADVANCED": TriggerMode.ADV,
        "SERIAL": TriggerMode.SERIAL,
    }
    if normalized not in aliases:
        raise McpToolError("invalid_trigger_mode", "mode must be simple, advanced, or serial")
    return aliases[normalized]


def _close_context(context: Any) -> None:
    try:
        context.__exit__(None, None, None)
    except Exception:
        try:
            context.close()
        except Exception:
            pass


def _safe_lib_version(context: Any) -> Optional[str]:
    try:
        return str(context.lib_version)
    except Exception:
        return None
