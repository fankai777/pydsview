"""
pydsview —— 用 Python 控制 DSLogic 逻辑分析仪

快速开始：

    from pydsview import DSLogicDevice

    with DSLogicDevice() as dev:
        dev.set_samplerate(10_000_000)
        dev.set_sample_count(1_000_000)
        data = dev.capture()

如果 libsigrok4DSL 未编译，import 不会出错，只有在调用时才抛出 LibraryNotFoundError。
"""

try:
    from .core import DSLogicDevice
except Exception:
    # 库未找到时不影响 import，调用时会有更清晰的报错
    DSLogicDevice = None  # type: ignore

from .constants import *  # noqa: F401, F403
from .exceptions import (
    PyDSViewError,
    LibraryNotFoundError,
    DeviceNotFoundError,
    DeviceError,
    CaptureError,
)

__version__ = "0.1.0"
__all__ = [
    "DSLogicDevice",
    "PyDSViewError",
    "LibraryNotFoundError",
    "DeviceNotFoundError",
    "DeviceError",
    "CaptureError",
]
