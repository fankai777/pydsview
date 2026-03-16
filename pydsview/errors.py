"""
pydsview.errors — Exception hierarchy mapping SR_ERR_* codes to Python.
"""

from ._constants import SRError


class DSViewError(Exception):
    """Base exception for all pydsview errors."""

    def __init__(self, message: str = "", code: int = 1):
        self.code = code
        super().__init__(message or f"DSView error (code={code})")


class MallocError(DSViewError):
    """Memory allocation failed inside the C library."""
    pass


class ArgError(DSViewError):
    """Invalid argument passed to a library function."""
    pass


class BugError(DSViewError):
    """Internal bug detected in the C library."""
    pass


class SamplerateError(DSViewError):
    """Requested samplerate is invalid or unsupported."""
    pass


class NotAvailableError(DSViewError):
    """The requested feature is not available."""
    pass


class DeviceClosedError(DSViewError):
    """The device is closed."""
    pass


class CallStatusError(DSViewError):
    """Function called in wrong state / wrong order."""
    pass


class FirmwareNotFoundError(DSViewError):
    """Firmware file not found on disk."""
    pass


class DeviceExclusiveError(DSViewError):
    """Device is already in exclusive use."""
    pass


class FirmwareVersionError(DSViewError):
    """Device firmware version is too old."""
    pass


class USBIOError(DSViewError):
    """USB I/O error during communication."""
    pass


class NoDriverError(DSViewError):
    """No driver found for the device."""
    pass


# Map SR_ERR_* code -> exception class
_ERROR_MAP: dict[int, type[DSViewError]] = {
    SRError.SR_ERR:                              DSViewError,
    SRError.SR_ERR_MALLOC:                       MallocError,
    SRError.SR_ERR_ARG:                          ArgError,
    SRError.SR_ERR_BUG:                          BugError,
    SRError.SR_ERR_SAMPLERATE:                   SamplerateError,
    SRError.SR_ERR_NA:                           NotAvailableError,
    SRError.SR_ERR_DEVICE_CLOSED:                DeviceClosedError,
    SRError.SR_ERR_CALL_STATUS:                  CallStatusError,
    SRError.SR_ERR_FIRMWARE_NOT_EXIST:           FirmwareNotFoundError,
    SRError.SR_ERR_DEVICE_IS_EXCLUSIVE:          DeviceExclusiveError,
    SRError.SR_ERR_DEVICE_FIRMWARE_VERSION_LOW:  FirmwareVersionError,
    SRError.SR_ERR_DEVICE_USB_IO_ERROR:          USBIOError,
    SRError.SR_ERR_DEVICE_NO_DRIVER:             NoDriverError,
}


def check_sr(ret: int, context: str = "") -> int:
    """
    Check a C library return code.  If ``ret != SR_OK``, raise the
    appropriate :class:`DSViewError` subclass.

    Returns ``ret`` on success (always 0).
    """
    if ret == SRError.SR_OK:
        return ret

    exc_cls = _ERROR_MAP.get(ret, DSViewError)
    msg = context or f"libsigrok4dsl returned error code {ret}"
    raise exc_cls(msg, code=ret)
