"""
libsigrok4DSL C 结构体 + 回调类型定义（ctypes）
基于 DSView/libsigrok4DSL/libsigrok.h
"""

import ctypes


# ─── 数据包结构体 ────────────────────────────────────────

class SrDatafeedPacket(ctypes.Structure):
    """sr_datafeed_packet —— datafeed 回调收到的包"""
    _fields_ = [
        ("type",                ctypes.c_uint16),
        ("status",              ctypes.c_uint16),
        ("payload",             ctypes.c_void_p),
        ("bExportOriginalData", ctypes.c_int),
    ]


class SrDatafeedLogic(ctypes.Structure):
    """sr_datafeed_logic —— 逻辑分析仪原始数据"""
    _fields_ = [
        ("length",        ctypes.c_uint64),
        ("format",        ctypes.c_int),
        ("index",         ctypes.c_uint16),
        ("order",         ctypes.c_uint16),
        ("unitsize",      ctypes.c_uint16),
        ("data_error",    ctypes.c_uint16),
        ("error_pattern", ctypes.c_uint64),
        ("data",          ctypes.c_void_p),
    ]


class SrDatafeedHeader(ctypes.Structure):
    """sr_datafeed_header"""
    _fields_ = [
        ("feed_version", ctypes.c_int),
        ("tv_sec",       ctypes.c_long),
        ("tv_usec",      ctypes.c_long),
    ]


# ─── 设备信息结构体 ──────────────────────────────────────

class DsDeviceBaseInfo(ctypes.Structure):
    """
    ds_device_base_info —— ds_get_device_list() 返回的设备列表元素
    handle=0 表示列表结尾
    """
    _fields_ = [
        ("handle", ctypes.c_uint64),   # ds_device_handle
        ("name",   ctypes.c_char * 150),
    ]


# ─── 回调函数类型 ────────────────────────────────────────

# void (*dslib_event_callback_t)(int event)
DsEventCallback = ctypes.CFUNCTYPE(None, ctypes.c_int)

# void (*ds_datafeed_callback_t)(const struct sr_dev_inst *sdi,
#                                const struct sr_datafeed_packet *packet)
DsDatafeedCallback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,                      # sdi
    ctypes.POINTER(SrDatafeedPacket),     # packet
)
