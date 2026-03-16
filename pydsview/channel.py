"""
pydsview.channel — Channel info wrapper.
"""

from __future__ import annotations

from ._binding import ffi, lib
from ._constants import ChannelType, Coupling


class Channel:
    """Read-only snapshot of a :c:type:`sr_channel` from the active device."""

    __slots__ = (
        "_ptr", "index", "name", "type", "enabled",
        "bits", "vdiv", "coupling", "offset", "vfactor",
        "trigger", "trig_value",
    )

    def __init__(self, ch_ptr):
        self._ptr = ch_ptr
        self.index: int = lib.pyds_channel_get_index(ch_ptr)
        self.name: str = ffi.string(lib.pyds_channel_get_name(ch_ptr)).decode()
        self.type: ChannelType = ChannelType(lib.pyds_channel_get_type(ch_ptr))
        self.enabled: bool = bool(lib.pyds_channel_get_enabled(ch_ptr))
        self.bits: int = lib.pyds_channel_get_bits(ch_ptr)
        self.vdiv: int = lib.pyds_channel_get_vdiv(ch_ptr)
        self.coupling: Coupling = Coupling(lib.pyds_channel_get_coupling(ch_ptr))
        self.offset: int = lib.pyds_channel_get_offset(ch_ptr)
        self.vfactor: int = lib.pyds_channel_get_vfactor(ch_ptr)
        self.trigger: str = ffi.string(lib.pyds_channel_get_trigger(ch_ptr)).decode()
        self.trig_value: int = lib.pyds_channel_get_trig_value(ch_ptr)

    @property
    def is_logic(self) -> bool:
        return self.type == ChannelType.LOGIC

    @property
    def is_dso(self) -> bool:
        return self.type == ChannelType.DSO

    @property
    def is_analog(self) -> bool:
        return self.type == ChannelType.ANALOG

    def __repr__(self) -> str:
        state = "ON" if self.enabled else "OFF"
        return f"<Channel {self.index} '{self.name}' {self.type.name} {state}>"
