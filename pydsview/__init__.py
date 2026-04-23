"""
pydsview — Python bindings for DSView's libsigrok4DSL.

Control DreamSourceLab logic analyzers and oscilloscopes from Python.
"""

__version__ = "0.1.7"

from .context import DSContext, DeviceInfo
from .device import Device
from .channel import Channel
from .capture import CaptureResult, CaptureSession
from .trigger import TriggerConfig
from . import export
from ._constants import (
    DeviceMode,
    DeviceType,
    ChannelType,
    Config,
    Coupling,
    TriggerMode,
    DSOTriggerSource,
    DSOTriggerSlope,
    PacketType,
    DeviceStatus,
    SRError,
    SR_HZ,
    SR_KHZ,
    SR_MHZ,
    SR_GHZ,
    SR_mV,
    SR_V,
)
from .errors import (
    DSViewError,
    MallocError,
    ArgError,
    SamplerateError,
    DeviceClosedError,
    FirmwareNotFoundError,
    USBIOError,
)

__all__ = [
    # Core classes
    "DSContext",
    "Device",
    "DeviceInfo",
    "Channel",
    "CaptureResult",
    "CaptureSession",
    "TriggerConfig",
    "export",
    # Enums
    "DeviceMode",
    "DeviceType",
    "ChannelType",
    "Config",
    "Coupling",
    "TriggerMode",
    "DSOTriggerSource",
    "DSOTriggerSlope",
    "PacketType",
    "DeviceStatus",
    "SRError",
    # Helpers
    "SR_HZ",
    "SR_KHZ",
    "SR_MHZ",
    "SR_GHZ",
    "SR_mV",
    "SR_V",
    # Exceptions
    "DSViewError",
    "MallocError",
    "ArgError",
    "SamplerateError",
    "DeviceClosedError",
    "FirmwareNotFoundError",
    "USBIOError",
]
