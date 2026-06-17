"""
pydsview.mcp_safety -- shared limits and filesystem policy for MCP tools.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


SUPPORTED_OUTPUT_FORMATS = frozenset({"dsl", "csv", "vcd"})


class McpToolError(Exception):
    """Structured error raised by MCP tool implementations."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"ok": False, "error_code": self.code, "error": self.message}


@dataclass(frozen=True)
class McpServerConfig:
    artifact_dir: Path
    max_samples: int = 10_000_000
    max_duration_ms: int = 10_000
    allow_overwrite: bool = False
    default_timeout_s: float = 30.0

    @classmethod
    def from_env(
        cls,
        *,
        artifact_dir: Optional[Union[str, Path]] = None,
        max_samples: Optional[int] = None,
        max_duration_ms: Optional[int] = None,
        allow_overwrite: Optional[bool] = None,
        default_timeout_s: Optional[float] = None,
    ) -> "McpServerConfig":
        configured_artifact_dir = artifact_dir or os.environ.get("PYDSVIEW_MCP_ARTIFACT_DIR") or "captures"
        return cls(
            artifact_dir=Path(configured_artifact_dir),
            max_samples=max_samples
            if max_samples is not None
            else _env_int("PYDSVIEW_MCP_MAX_SAMPLES", 10_000_000),
            max_duration_ms=max_duration_ms
            if max_duration_ms is not None
            else _env_int("PYDSVIEW_MCP_MAX_DURATION_MS", 10_000),
            allow_overwrite=allow_overwrite
            if allow_overwrite is not None
            else _env_bool("PYDSVIEW_MCP_ALLOW_OVERWRITE", False),
            default_timeout_s=default_timeout_s
            if default_timeout_s is not None
            else _env_float("PYDSVIEW_MCP_DEFAULT_TIMEOUT_S", 30.0),
        )

    @property
    def resolved_artifact_dir(self) -> Path:
        return self.artifact_dir.expanduser().resolve()

    @property
    def profile_dir(self) -> Path:
        return self.resolved_artifact_dir / "profiles"


class CaptureLock:
    """Small non-reentrant lock wrapper with structured busy errors."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise McpToolError("capture_busy", "another pydsview capture is already active")

    def release(self) -> None:
        try:
            self._lock.release()
        except RuntimeError:
            pass


def validate_capture_bounds(
    config: McpServerConfig,
    *,
    samples: Optional[int],
    duration_ms: Optional[int],
) -> None:
    if (samples is None) == (duration_ms is None):
        raise McpToolError("invalid_capture_bounds", "capture requires exactly one of samples or duration_ms")
    if samples is not None:
        if samples <= 0:
            raise McpToolError("invalid_samples", "samples must be positive")
        if samples > config.max_samples:
            raise McpToolError(
                "samples_too_large",
                f"samples exceeds configured maximum of {config.max_samples}",
            )
    if duration_ms is not None:
        if duration_ms <= 0:
            raise McpToolError("invalid_duration", "duration_ms must be positive")
        if duration_ms > config.max_duration_ms:
            raise McpToolError(
                "duration_too_large",
                f"duration_ms exceeds configured maximum of {config.max_duration_ms}",
            )


def resolve_artifact_path(
    config: McpServerConfig,
    *,
    filename: Optional[str],
    output_format: str,
    overwrite: bool,
) -> Path:
    output_format = output_format.lower().lstrip(".")
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise McpToolError("unsupported_output_format", "output_format must be one of dsl, csv, or vcd")

    artifact_dir = config.resolved_artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        raw_path = Path(filename)
        if raw_path.suffix.lower().lstrip(".") != output_format:
            raw_path = raw_path.with_suffix(f".{output_format}")
        candidate = raw_path if raw_path.is_absolute() else artifact_dir / raw_path
    else:
        import datetime as _datetime

        stamp = _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        candidate = artifact_dir / f"capture-{stamp}.{output_format}"

    resolved = candidate.expanduser().resolve()
    if not _is_relative_to(resolved, artifact_dir):
        raise McpToolError("artifact_path_outside_dir", "artifact path must stay inside artifact_dir")
    if resolved.exists() and not (overwrite or config.allow_overwrite):
        raise McpToolError("artifact_exists", f"artifact already exists: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + ".json")


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if not value:
        return default
    return float(value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
