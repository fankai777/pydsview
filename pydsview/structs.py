"""
libsigrok4DSL C 结构体定义（ctypes）
严格按照 DSView/libsigrok4DSL/libsigrok.h 的字段顺序
"""

import ctypes


class SrDatafeedHeader(ctypes.Structure):
    """sr_datafeed_header —— 采集开始时的元数据"""
    _fields_ = [
        ("feed_version",    ctypes.c_int),
        # struct timeval
        ("tv_sec",          ctypes.c_long),
        ("tv_usec",         ctypes.c_long),
    ]


class SrDatafeedLogic(ctypes.Structure):
    """
    sr_datafeed_logic —— 逻辑分析仪原始数据包
    payload 中最重要的结构体：data 指向原始采样数据
    """
    _fields_ = [
        ("length",          ctypes.c_uint64),   # 数据字节数
        ("format",          ctypes.c_int),       # LA_CROSS_DATA or LA_SPLIT_DATA
        ("index",           ctypes.c_uint16),    # LA_SPLIT_DATA 时的通道索引
        ("order",           ctypes.c_uint16),
        ("unitsize",        ctypes.c_uint16),    # 每个样本的字节数
        ("data_error",      ctypes.c_uint16),
        ("error_pattern",   ctypes.c_uint64),
        ("data",            ctypes.c_void_p),    # 指向原始数据
    ]


class SrDatafeedPacket(ctypes.Structure):
    """
    sr_datafeed_packet —— datafeed 回调收到的数据包
    根据 type 字段决定如何解析 payload：
      SR_DF_HEADER  → payload 转换为 SrDatafeedHeader*
      SR_DF_LOGIC   → payload 转换为 SrDatafeedLogic*
      SR_DF_END     → payload 为 NULL
    """
    _fields_ = [
        ("type",                ctypes.c_uint16),
        ("status",              ctypes.c_uint16),
        ("payload",             ctypes.c_void_p),
        ("bExportOriginalData", ctypes.c_int),
    ]


class SrChannel(ctypes.Structure):
    """
    sr_channel —— 通道描述（精简版，不含 DSO 校准字段）
    注意：完整结构体在 libsigrok.h 有很多 DSO 相关字段，
    Python 侧只需要 index/type/enabled/name 基本信息
    """
    _fields_ = [
        ("index",       ctypes.c_uint16),
        ("type",        ctypes.c_int),
        ("enabled",     ctypes.c_int),     # gboolean → int
        ("name",        ctypes.c_char_p),
        ("trigger",     ctypes.c_char_p),
    ]


class SrConfig(ctypes.Structure):
    """sr_config —— 设备配置键值对"""
    _fields_ = [
        ("key",     ctypes.c_int),
        ("data",    ctypes.c_void_p),   # GVariant*，通过 glib 创建
    ]


# Datafeed 回调函数类型：
# void callback(const struct sr_dev_inst *sdi,
#               const struct sr_datafeed_packet *packet,
#               void *cb_data)
DatafeedCallback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,                        # sdi
    ctypes.POINTER(SrDatafeedPacket),        # packet
    ctypes.c_void_p,                         # cb_data
)
