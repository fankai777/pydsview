"""
pydsview.device — Device wrapper: configuration, channel management, capture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from ._binding import ffi, lib
from ._constants import Config, DeviceMode, DeviceType, DataType
from .errors import check_sr, DSViewError
from .channel import Channel

# The config_info table in hwdriver.c reports SR_T_LIST for configs that
# support list queries, but the driver's config_set/config_get use a
# different GVariant type for the actual value.  Configs missing from the
# table fall through to uint64 by default, which is also wrong.
# This map provides the correct GVariant type for set/get operations.
_CONFIG_TYPE_OVERRIDES: dict[int, int] = {
    Config.OPERATION_MODE:  DataType.INT16,   # table: LIST, driver: int16
    Config.CHANNEL_MODE:    DataType.INT16,   # table: LIST, driver: int16
    Config.THRESHOLD:       DataType.INT16,   # table: LIST, driver: int16
    Config.FILTER:          DataType.INT16,   # table: LIST, driver: int16
    Config.BUFFER_OPTIONS:  DataType.INT16,   # table: LIST, driver: int16
    Config.INSTANT:         DataType.BOOL,    # not in table, driver: bool
    Config.LOOP_MODE:       DataType.BOOL,    # not in table, driver: bool
}

if TYPE_CHECKING:
    from .capture import CaptureResult, CaptureSession


class Device:
    """
    Represents the currently *active* device in the libsigrok4dsl context.

    Obtain via :meth:`DSContext.get_device` or :meth:`DSContext.load_session_file`.
    """

    def __init__(self):
        self._info = ffi.new("struct ds_device_full_info *")
        ret = lib.ds_get_actived_device_info(self._info)
        check_sr(ret, "ds_get_actived_device_info failed")

    # ---- basic properties ----

    @property
    def name(self) -> str:
        return ffi.string(self._info.name).decode()

    @property
    def path(self) -> str:
        return ffi.string(self._info.path).decode()

    @property
    def driver_name(self) -> str:
        return ffi.string(self._info.driver_name).decode()

    @property
    def device_type(self) -> DeviceType:
        return DeviceType(self._info.dev_type)

    @property
    def handle(self) -> int:
        return int(self._info.handle)

    @property
    def mode(self) -> DeviceMode:
        return DeviceMode(lib.ds_get_actived_device_mode())

    # ---- channel list ----

    @property
    def channels(self) -> list[Channel]:
        """Return a snapshot of all channels on the active device."""
        sdi = self._info.di
        if not sdi:
            return []
        ch_list_ptr = lib.pyds_sdi_get_channels(sdi)
        if not ch_list_ptr:
            return []
        n = lib.pyds_gslist_length(ch_list_ptr)
        result = []
        for i in range(n):
            ch_ptr = lib.pyds_gslist_nth_data(ch_list_ptr, i)
            if ch_ptr:
                result.append(Channel(ch_ptr))
        return result

    # ---- config helpers ----

    def _get_config_variant(self, key: int, ch=ffi.NULL) -> Any:
        data_p = ffi.new("GVariant *[1]")
        ret = lib.ds_get_actived_device_config(ch, ffi.NULL, key, data_p)
        check_sr(ret, f"get_config({key}) failed")
        return data_p[0]

    def _get_config_datatype(self, key: int) -> Optional[int]:
        info = lib.ds_get_actived_device_config_info(key)
        if info == ffi.NULL:
            return None
        return info.datatype

    def get_config(self, key: int, channel: Optional[Channel] = None) -> Any:
        """
        Read a configuration value by SR_CONF_* key.

        Returns a Python int, bool, float, or str depending on the data type.
        """
        ch_ptr = channel._ptr if channel else ffi.NULL
        data_p = ffi.new("GVariant *[1]")
        ret = lib.ds_get_actived_device_config(ch_ptr, ffi.NULL, key, data_p)
        check_sr(ret, f"get_config({key}) failed")
        v = data_p[0]
        if v == ffi.NULL:
            return None

        dtype = _CONFIG_TYPE_OVERRIDES.get(key) or self._get_config_datatype(key)
        try:
            if dtype == DataType.UINT64:
                return lib.pyds_gvariant_get_uint64(v)
            elif dtype == DataType.BOOL:
                return bool(lib.pyds_gvariant_get_boolean(v))
            elif dtype == DataType.CHAR:
                return ffi.string(lib.pyds_gvariant_get_string(v)).decode()
            elif dtype == DataType.INT16:
                return lib.pyds_gvariant_get_int16(v)
            elif dtype == DataType.FLOAT:
                return lib.pyds_gvariant_get_double(v)
            else:
                # default: try uint64
                return lib.pyds_gvariant_get_uint64(v)
        finally:
            lib.pyds_gvariant_unref(v)

    def set_config(self, key: int, value: Any, channel: Optional[Channel] = None):
        """
        Write a configuration value by SR_CONF_* key.

        Automatically creates the appropriate GVariant based on the config's
        data type.
        """
        ch_ptr = channel._ptr if channel else ffi.NULL
        dtype = _CONFIG_TYPE_OVERRIDES.get(key) or self._get_config_datatype(key)

        if dtype == DataType.BOOL or isinstance(value, bool):
            gv = lib.pyds_gvariant_new_boolean(int(value))
        elif dtype == DataType.CHAR or isinstance(value, str):
            gv = lib.pyds_gvariant_new_string(value.encode() if isinstance(value, str) else value)
        elif dtype == DataType.INT16:
            gv = lib.pyds_gvariant_new_int16(int(value))
        elif dtype == DataType.FLOAT or isinstance(value, float):
            gv = lib.pyds_gvariant_new_double(float(value))
        else:
            # Default to uint64
            gv = lib.pyds_gvariant_new_uint64(int(value))

        lib.pyds_gvariant_ref_sink(gv)
        ret = lib.ds_set_actived_device_config(ch_ptr, ffi.NULL, key, gv)
        check_sr(ret, f"set_config({key}) failed")

    # ---- convenience properties ----

    @property
    def samplerate(self) -> int:
        return self.get_config(Config.SAMPLERATE)

    @samplerate.setter
    def samplerate(self, value: int):
        self.set_config(Config.SAMPLERATE, value)

    @property
    def sample_count(self) -> int:
        return self.get_config(Config.LIMIT_SAMPLES)

    @sample_count.setter
    def sample_count(self, value: int):
        self.set_config(Config.LIMIT_SAMPLES, value)

    # ---- channel management ----

    def enable_channel(self, index: int, enabled: bool = True):
        """Enable or disable a channel by its index."""
        ret = lib.ds_enable_device_channel_index(index, int(enabled))
        check_sr(ret, f"enable_channel({index}) failed")

    def set_channel_name(self, index: int, name: str):
        """Rename a channel by its index."""
        ret = lib.ds_set_device_channel_name(index, name.encode())
        check_sr(ret, f"set_channel_name({index}) failed")

    # ---- capture ----

    def capture(self, timeout: Optional[float] = None) -> "CaptureResult":
        """
        Perform a synchronous capture.  Blocks until data collection is
        complete or *timeout* seconds have elapsed.

        Returns a :class:`CaptureResult` with the captured data.
        """
        from .capture import run_capture
        return run_capture(self, timeout=timeout)

    def start_capture(self) -> "CaptureSession":
        """
        Start an asynchronous capture.  Returns a :class:`CaptureSession`
        that can be polled or awaited.
        """
        from .capture import CaptureSession
        session = CaptureSession(self)
        session.start()
        return session

    def stop_capture(self):
        """Stop an ongoing capture."""
        ret = lib.ds_stop_collect()
        check_sr(ret, "ds_stop_collect failed")

    def __repr__(self) -> str:
        return f"<Device '{self.name}' mode={self.mode.name} type={self.device_type.name}>"
