"""
pydsview.trigger — Trigger configuration helpers.
"""

from __future__ import annotations

from ._binding import lib
from ._constants import TriggerMode, Config
from .errors import check_sr


# Mapping from single-char trigger specs to (trigger0, trigger1) byte pairs.
# These match the values expected by ds_trigger_probe_set().
_TRIGGER_CHAR_MAP = {
    "R": (0x01, 0x01),   # Rising edge
    "F": (0x01, 0x00),   # Falling edge
    "1": (0x00, 0x01),   # High
    "0": (0x01, 0x00),   # Low
    "X": (0x00, 0x00),   # Don't care
    "C": (0x01, 0x01),   # Change (either edge)
}


class TriggerConfig:
    """
    High-level wrapper around the ds_trigger_* functions.

    Example::

        trig = TriggerConfig()
        trig.reset()
        trig.set_enabled(True)
        trig.set_mode(TriggerMode.SIMPLE)
        trig.set_position(50)
        trig.set_channel_trigger(0, 'R')   # Rising edge on CH0
    """

    def reset(self):
        """Reset trigger to default (disabled) state."""
        ret = lib.ds_trigger_reset()
        check_sr(ret, "ds_trigger_reset failed")

    def set_enabled(self, enabled: bool):
        """Enable or disable the trigger."""
        ret = lib.ds_trigger_set_en(1 if enabled else 0)
        check_sr(ret, "ds_trigger_set_en failed")

    @property
    def enabled(self) -> bool:
        return bool(lib.ds_trigger_get_en())

    def set_mode(self, mode: TriggerMode):
        """Set trigger mode: SIMPLE, ADV, or SERIAL."""
        ret = lib.ds_trigger_set_mode(int(mode))
        check_sr(ret, "ds_trigger_set_mode failed")

    def set_position(self, percent: int):
        """
        Set trigger position as a percentage (0–90).

        This determines where in the capture buffer the trigger point falls.
        """
        if not 0 <= percent <= 90:
            raise ValueError("Trigger position must be 0–90")
        ret = lib.ds_trigger_set_pos(percent)
        check_sr(ret, "ds_trigger_set_pos failed")

    @property
    def position(self) -> int:
        return lib.ds_trigger_get_pos()

    def set_channel_trigger(self, channel: int, spec: str):
        """
        Set the trigger condition for a single channel.

        *spec* is one of:

        - ``'R'`` — Rising edge
        - ``'F'`` — Falling edge
        - ``'1'`` — High level
        - ``'0'`` — Low level
        - ``'X'`` — Don't care
        - ``'C'`` — Any change (either edge)
        """
        spec = spec.upper()
        if spec not in _TRIGGER_CHAR_MAP:
            raise ValueError(f"Unknown trigger spec '{spec}', use one of: R F 1 0 X C")
        t0, t1 = _TRIGGER_CHAR_MAP[spec]
        ret = lib.ds_trigger_probe_set(channel, t0, t1)
        check_sr(ret, f"ds_trigger_probe_set(ch={channel}) failed")

    def set_stages(self, count: int):
        """Set the number of trigger stages (for advanced trigger)."""
        ret = lib.ds_trigger_set_stage(count)
        check_sr(ret, f"ds_trigger_set_stage({count}) failed")
