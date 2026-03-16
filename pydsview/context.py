"""
pydsview.context — DSContext: library lifecycle and device management.
"""

from __future__ import annotations

import atexit
import os
import threading
from typing import Optional

from ._binding import ffi, lib
from ._constants import DeviceType
from .errors import check_sr
from .device import Device


class DeviceInfo:
    """Lightweight device descriptor returned by :meth:`DSContext.list_devices`."""

    __slots__ = ("handle", "name")

    def __init__(self, handle: int, name: str):
        self.handle = handle
        self.name = name

    def __repr__(self) -> str:
        return f"<DeviceInfo '{self.name}' handle={self.handle:#x}>"


# ---------------------------------------------------------------------------
# Module-level singleton lifecycle.
#
# The C library is a global singleton with async threads that can outlive
# ds_lib_exit().  We init once and defer exit to atexit so the process
# teardown handles cleanup safely.
# ---------------------------------------------------------------------------

_lib_lock = threading.Lock()
_lib_initialized = False

# Persistent event callback — stays alive for the process lifetime so
# C async threads always have a valid function pointer to call.
@ffi.callback("void(int)")
def _persistent_event_cb(event):
    pass  # no-op by default; capture.py installs its own when needed


def _atexit_cleanup():
    """Best-effort cleanup at interpreter shutdown."""
    try:
        lib.ds_lib_exit()
    except Exception:
        pass


class DSContext:
    """
    Top-level context that initializes the libsigrok4dsl library.

    Use as a context manager::

        with pydsview.DSContext(firmware_dir="/path/to/res") as ctx:
            ...

    The underlying C library is initialized once per process and cleaned
    up at interpreter exit via ``atexit``.
    """

    def __init__(
        self,
        firmware_dir: Optional[str] = None,
        user_data_dir: Optional[str] = None,
    ):
        global _lib_initialized
        self._closed = False

        with _lib_lock:
            if not _lib_initialized:
                if not firmware_dir:
                    # Default to bundled res/ directory
                    firmware_dir = os.path.join(os.path.dirname(__file__), "res")
                if firmware_dir:
                    lib.ds_set_firmware_resource_dir(firmware_dir.encode())
                if user_data_dir:
                    lib.ds_set_user_data_dir(user_data_dir.encode())

                # Register persistent event callback *before* init so the
                # hotplug thread has a safe function to call.
                lib.ds_set_event_callback(_persistent_event_cb)

                ret = lib.ds_lib_init()
                check_sr(ret, "ds_lib_init failed")

                _lib_initialized = True
                atexit.register(_atexit_cleanup)

    # ---- context manager ----

    def __enter__(self) -> "DSContext":
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        """Mark this context as closed.  The C library stays alive until process exit."""
        self._closed = True

    def __del__(self):
        pass  # nothing to do — atexit handles cleanup

    # ---- device enumeration ----

    def list_devices(self) -> list[DeviceInfo]:
        """
        Return a list of discovered devices (including Demo).

        Each entry is a :class:`DeviceInfo` with ``handle`` and ``name``.
        """
        out_list = ffi.new("struct ds_device_base_info **")
        out_count = ffi.new("int *")

        ret = lib.ds_get_device_list(out_list, out_count)
        check_sr(ret, "ds_get_device_list failed")

        count = out_count[0]
        arr = out_list[0]
        result = []
        for i in range(count):
            info = arr[i]
            name = ffi.string(info.name).decode()
            result.append(DeviceInfo(handle=int(info.handle), name=name))

        # Free the C-allocated array
        if arr != ffi.NULL:
            lib.pyds_free(arr)

        return result

    # ---- device activation ----

    def get_device(self, index: int) -> Device:
        """
        Activate the device at *index* (from :meth:`list_devices` order)
        and return a :class:`Device` wrapper.
        """
        ret = lib.ds_active_device_by_index(index)
        check_sr(ret, f"ds_active_device_by_index({index}) failed")
        return Device()

    def activate_device(self, handle: int) -> Device:
        """
        Activate a device by its handle and return a :class:`Device` wrapper.
        """
        ret = lib.ds_active_device(handle)
        check_sr(ret, f"ds_active_device({handle:#x}) failed")
        return Device()

    def load_session_file(self, path: str) -> Device:
        """
        Open a saved session file (``*.dsl``) and activate it as a virtual
        device.  Returns a :class:`Device` wrapper.
        """
        abs_path = os.path.abspath(path)
        ret = lib.ds_device_from_file(abs_path.encode())
        check_sr(ret, f"ds_device_from_file({abs_path}) failed")
        return Device()

    def reload_devices(self):
        """Re-scan for available devices."""
        ret = lib.ds_reload_device_list()
        check_sr(ret, "ds_reload_device_list failed")

    @property
    def lib_version(self) -> str:
        """Return the libsigrok4dsl version string."""
        return ffi.string(lib.sr_get_lib_version_string()).decode()
