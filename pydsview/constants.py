"""
libsigrok4DSL 常量定义
来源：DSView/libsigrok4DSL/libsigrok.h
"""

# ─── 返回码 ───────────────────────────────────────────────
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

# ─── 数据包类型 sr_datafeed_packet.type ──────────────────
SR_DF_HEADER        = 10000  # 采集开始
SR_DF_END           = 10001  # 采集结束
SR_DF_META          = 10002  # 元数据
SR_DF_TRIGGER       = 10003  # 触发点
SR_DF_LOGIC         = 10004  # 逻辑分析数据
SR_DF_DSO           = 10005  # 示波器数据
SR_DF_ANALOG        = 10006  # 模拟数据
SR_DF_FRAME_BEGIN   = 10007
SR_DF_FRAME_END     = 10008
SR_DF_OVERFLOW      = 10009  # 数据溢出

# ─── 数据格式 sr_datafeed_logic.format ───────────────────
LA_CROSS_DATA   = 0  # 交叉格式（多通道混合）
LA_SPLIT_DATA   = 1  # 分离格式（每通道单独）

# ─── 通道类型 ─────────────────────────────────────────────
SR_CHANNEL_LOGIC    = 10000
SR_CHANNEL_DSO      = 10001
SR_CHANNEL_ANALOG   = 10002

# ─── 操作模式 ─────────────────────────────────────────────
LOGIC           = 0
DSO             = 1
ANALOG          = 2

# ─── DSLogic 工作模式 ─────────────────────────────────────
LO_OP_BUFFER    = 0  # Buffer 模式（采完再传）
LO_OP_STREAM    = 1  # Stream 模式（实时传输）
LO_OP_INTEST    = 2  # 内部模式测试
LO_OP_EXTEST    = 3  # 外部模式测试
LO_OP_LPTEST    = 4  # SDRAM 回环测试

# ─── 设备类型 ─────────────────────────────────────────────
DEV_TYPE_UNKNOWN    = 0
DEV_TYPE_DEMO       = 1
DEV_TYPE_FILELOG    = 2
DEV_TYPE_USB        = 3
DEV_TYPE_SERIAL     = 4

# ─── 配置 Key（sr_config_option_id）─────────────────────
# 设备类
SR_CONF_LOGIC_ANALYZER  = 10000
SR_CONF_OSCILLOSCOPE    = 10001
SR_CONF_MULTIMETER      = 10002
SR_CONF_DEMO_DEV        = 10003

# 连接
SR_CONF_CONN            = 20000
SR_CONF_SERIALCOMM      = 20001

# 设备配置
SR_CONF_SAMPLERATE      = 30000  # 采样率（Hz）
SR_CONF_CAPTURE_RATIO   = 30001  # 触发前/后比例
SR_CONF_USB_SPEED       = 30002
SR_CONF_USB30_SUPPORT   = 30003
SR_CONF_DEVICE_MODE     = 30004
SR_CONF_INSTANT         = 30005
SR_CONF_STATUS          = 30006
SR_CONF_PATTERN_MODE    = 30007
SR_CONF_RLE             = 30008
SR_CONF_WAIT_UPLOAD     = 30009
SR_CONF_TRIGGER_SLOPE   = 30010
SR_CONF_TRIGGER_SOURCE  = 30011
SR_CONF_TRIGGER_CHANNEL = 30012
SR_CONF_TRIGGER_VALUE   = 30013
SR_CONF_HORIZ_TRIGGERPOS= 30014
SR_CONF_TRIGGER_HOLDOFF = 30015
SR_CONF_TRIGGER_MARGIN  = 30016
SR_CONF_BUFFERSIZE      = 30017
SR_CONF_MAX_TIMEBASE    = 30018
SR_CONF_MIN_TIMEBASE    = 30019
SR_CONF_TIMEBASE        = 30020
SR_CONF_FILTER          = 30021
SR_CONF_DSO_SYNC        = 30022
SR_CONF_UNIT_BITS       = 30023
SR_CONF_TOTAL_CH_NUM    = 30026
SR_CONF_VLD_CH_NUM      = 30027
SR_CONF_LA_CH32         = 30028
SR_CONF_STREAM          = 30052
SR_CONF_ROLL            = 30053
SR_CONF_OPERATION_MODE  = 30065
SR_CONF_CHANNEL_MODE    = 30067
SR_CONF_THRESHOLD       = 30071
SR_CONF_VTH             = 30072
SR_CONF_PROBE_EN        = 30080

# 采集限制
SR_CONF_LIMIT_MSEC      = 50000  # 时间限制（ms）
SR_CONF_LIMIT_SAMPLES   = 50001  # 样本数限制
SR_CONF_LIMIT_FRAMES    = 50002  # 帧数限制
SR_CONF_CONTINUOUS      = 50003  # 持续采集

# ─── 数据类型 ─────────────────────────────────────────────
SR_T_UINT64             = 10000
SR_T_UINT8              = 10001
SR_T_CHAR               = 10002
SR_T_BOOL               = 10003
SR_T_FLOAT              = 10004
SR_T_INT16              = 10009
