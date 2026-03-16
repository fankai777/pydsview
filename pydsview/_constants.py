"""
pydsview._constants — Enums and macro constants from libsigrok4DSL/libsigrok.h.
"""

from enum import IntEnum

# ---------------------------------------------------------------------------
# Error / status codes
# ---------------------------------------------------------------------------

class SRError(IntEnum):
    SR_OK                               = 0
    SR_ERR                              = 1
    SR_ERR_MALLOC                       = 2
    SR_ERR_ARG                          = 3
    SR_ERR_BUG                          = 4
    SR_ERR_SAMPLERATE                   = 5
    SR_ERR_NA                           = 6
    SR_ERR_DEVICE_CLOSED                = 7
    SR_ERR_CALL_STATUS                  = 8
    SR_ERR_HAVE_DONE                    = 9
    SR_ERR_FIRMWARE_NOT_EXIST           = 10
    SR_ERR_DEVICE_IS_EXCLUSIVE          = 11
    SR_ERR_DEVICE_FIRMWARE_VERSION_LOW  = 12
    SR_ERR_DEVICE_USB_IO_ERROR          = 13
    SR_ERR_DEVICE_NO_DRIVER             = 14


# ---------------------------------------------------------------------------
# Device type
# ---------------------------------------------------------------------------

class DeviceType(IntEnum):
    UNKNOWN  = 0
    DEMO     = 1
    FILELOG  = 2
    USB      = 3
    SERIAL   = 4


# ---------------------------------------------------------------------------
# Operation / device mode
# ---------------------------------------------------------------------------

class DeviceMode(IntEnum):
    LOGIC   = 0
    DSO     = 1
    ANALOG  = 2


# ---------------------------------------------------------------------------
# Channel type
# ---------------------------------------------------------------------------

class ChannelType(IntEnum):
    DECODER   = 9998
    GROUP     = 9999
    LOGIC     = 10000
    DSO       = 10001
    ANALOG    = 10002
    FFT       = 10003
    LISSAJOUS = 10004
    MATH      = 10005


# ---------------------------------------------------------------------------
# Datafeed packet type
# ---------------------------------------------------------------------------

class PacketType(IntEnum):
    HEADER      = 10000
    END         = 10001
    META        = 10002
    TRIGGER     = 10003
    LOGIC       = 10004
    DSO         = 10005
    ANALOG      = 10006
    FRAME_BEGIN = 10007
    FRAME_END   = 10008
    OVERFLOW    = 10009


# ---------------------------------------------------------------------------
# Device status
# ---------------------------------------------------------------------------

class DeviceStatus(IntEnum):
    NOT_FOUND      = 10000
    INITIALIZING   = 10001
    INACTIVE       = 10002
    INCOMPATIBLE   = 10003
    ACTIVE         = 10004
    STOPPING       = 10005


# ---------------------------------------------------------------------------
# Coupling
# ---------------------------------------------------------------------------

class Coupling(IntEnum):
    DC  = 0
    AC  = 1
    GND = 2


# ---------------------------------------------------------------------------
# Trigger mode
# ---------------------------------------------------------------------------

class TriggerMode(IntEnum):
    SIMPLE  = 0
    ADV     = 1
    SERIAL  = 2


# ---------------------------------------------------------------------------
# DSO trigger source / slope
# ---------------------------------------------------------------------------

class DSOTriggerSource(IntEnum):
    AUTO  = 0
    CH0   = 1
    CH1   = 2
    CH0A1 = 3
    CH0O1 = 4


class DSOTriggerSlope(IntEnum):
    RISING  = 0
    FALLING = 1


# ---------------------------------------------------------------------------
# SR_CONF_* configuration keys
# ---------------------------------------------------------------------------

class Config(IntEnum):
    # Device classes
    LOGIC_ANALYZER       = 10000
    OSCILLOSCOPE         = 10001
    MULTIMETER           = 10002
    DEMO_DEV             = 10003

    # Driver scan
    CONN                 = 20000
    SERIALCOMM           = 20001

    # Core device config
    SAMPLERATE           = 30000
    CAPTURE_RATIO        = 30001
    USB_SPEED            = 30002
    USB30_SUPPORT        = 30003
    DEVICE_MODE          = 30004
    INSTANT              = 30005
    STATUS               = 30006
    PATTERN_MODE         = 30007
    RLE                  = 30008
    WAIT_UPLOAD          = 30009
    TRIGGER_SLOPE        = 30010
    TRIGGER_SOURCE       = 30011
    TRIGGER_CHANNEL      = 30012
    TRIGGER_VALUE        = 30013
    HORIZ_TRIGGERPOS     = 30014
    TRIGGER_HOLDOFF      = 30015
    TRIGGER_MARGIN       = 30016
    BUFFERSIZE           = 30017
    MAX_TIMEBASE         = 30018
    MIN_TIMEBASE         = 30019
    TIMEBASE             = 30020
    FILTER               = 30021
    DSO_SYNC             = 30022
    UNIT_BITS            = 30023
    REF_MIN              = 30024
    REF_MAX              = 30025
    TOTAL_CH_NUM         = 30026
    VLD_CH_NUM           = 30027
    LA_CH32              = 30028
    HAVE_ZERO            = 30029
    ZERO                 = 30030
    ZERO_SET             = 30031
    ZERO_LOAD            = 30032
    ZERO_DEFAULT         = 30033
    ZERO_COMB_FGAIN      = 30034
    ZERO_COMB            = 30035
    VOCM                 = 30036
    CALI                 = 30037
    STATUS_PERIOD        = 30038
    STREAM               = 30052
    ROLL                 = 30053
    TEST                 = 30054
    OPERATION_MODE       = 30065
    BUFFER_OPTIONS       = 30066
    CHANNEL_MODE         = 30067
    MAX_HEIGHT           = 30069
    THRESHOLD            = 30071
    VTH                  = 30072
    MAX_DSO_SAMPLERATE   = 30073
    MAX_DSO_SAMPLELIMITS = 30074
    HW_DEPTH             = 30075
    BANDWIDTH            = 30076
    BANDWIDTH_LIMIT      = 30077

    # Probe config
    PROBE_CONFIGS        = 30078
    PROBE_EN             = 30080
    PROBE_COUPLING       = 30081
    PROBE_VDIV           = 30082
    PROBE_FACTOR         = 30083
    PROBE_MAP_DEFAULT    = 30084
    PROBE_MAP_UNIT       = 30085
    PROBE_MAP_MIN        = 30086
    PROBE_MAP_MAX        = 30087
    PROBE_OFFSET         = 30088
    PROBE_HW_OFFSET      = 30089
    PROBE_PREOFF         = 30090
    PROBE_VGAIN          = 30093

    # Special
    DEVICE_OPTIONS       = 30098
    DEVICE_SESSIONS      = 30099
    FILE_VERSION         = 30102
    CAPTURE_NUM_PROBES   = 30103
    NUM_BLOCKS           = 30104

    # Acquisition
    LIMIT_MSEC           = 50000
    LIMIT_SAMPLES        = 50001
    TRIGGER_TIME         = 50002
    TRIGGER_POS          = 50003
    ACTUAL_SAMPLES       = 50004
    LIMIT_FRAMES         = 50005
    CONTINUOUS           = 50006
    DATALOG              = 50007

    # Loop
    LOOP_MODE            = 60001


# ---------------------------------------------------------------------------
# Data type codes (SR_T_*)
# ---------------------------------------------------------------------------

class DataType(IntEnum):
    UINT64          = 10000
    UINT8           = 10001
    CHAR            = 10002
    BOOL            = 10003
    FLOAT           = 10004
    RATIONAL_PERIOD = 10005
    RATIONAL_VOLT   = 10006
    KEYVALUE        = 10007
    LIST            = 10008
    INT16           = 10009


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class Event(IntEnum):
    COLLECT_TASK_START          = 101
    COLLECT_TASK_END            = 102
    DEVICE_RUNNING              = 103
    DEVICE_STOPPED              = 104
    COLLECT_TASK_END_BY_DETACHED = 105
    COLLECT_TASK_END_BY_ERROR   = 106
    DEVICE_SPEED_NOT_MATCH      = 107


class DeviceEvent(IntEnum):
    NEW_DEVICE_ATTACH      = 1
    CURRENT_DEVICE_DETACH  = 2
    INACTIVE_DEVICE_DETACH = 3


# ---------------------------------------------------------------------------
# Logic data format
# ---------------------------------------------------------------------------

class LogicFormat(IntEnum):
    CROSS_DATA = 0
    SPLIT_DATA = 1


# ---------------------------------------------------------------------------
# Frequency / sample helpers  (pure Python, matching C macros)
# ---------------------------------------------------------------------------

def SR_HZ(n):  return n
def SR_KHZ(n): return n * 1_000
def SR_MHZ(n): return n * 1_000_000
def SR_GHZ(n): return n * 1_000_000_000

def SR_NS(n):  return n
def SR_US(n):  return n * 1_000
def SR_MS(n):  return n * 1_000_000
def SR_SEC(n): return n * 1_000_000_000

def SR_B(n):  return n
def SR_KB(n): return n * 1024
def SR_MB(n): return n * 1048576
def SR_GB(n): return n * 1073741824

def SR_mV(n): return n
def SR_V(n):  return n * 1000
