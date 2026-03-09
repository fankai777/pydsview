"""
DSLogicDevice —— 用 Python 控制 DSLogic 逻辑分析仪

使用 DreamSourceLab 的 ds_* 高层 API（lib_main.c）。

典型用法（手动停止模式，推荐）：

    import time
    from pydsview import DSLogicDevice

    with DSLogicDevice() as dev:
        dev.set_samplerate(10_000_000)   # 10 MHz
        dev.set_voltage_threshold(1.65)  # 3.3V 系统
        dev.start()                      # 开始采集，不阻塞

        time.sleep(2)                    # 采集 2 秒（或等待你的触发条件）

        data = dev.stop_and_get()        # 停止 + 返回全部数据（bytes）
        print(f"采集到 {len(data):,} 字节")

典型用法（固定样本数，自动停止）：

    with DSLogicDevice() as dev:
        dev.set_samplerate(10_000_000)
        dev.set_sample_count(1_000_000)  # 1M 样本后自动停
        data = dev.capture()             # 阻塞直到采完

"""

import ctypes
import ctypes.util
import csv
import os
import struct
import threading
from typing import Callable, List, Optional

from .constants import (
    SR_OK,
    SR_CONF_SAMPLERATE,
    SR_CONF_LIMIT_SAMPLES,
    SR_CONF_OPERATION_MODE,
    SR_CONF_VTH,
    SR_DF_LOGIC, SR_DF_END,
    DS_EV_COLLECT_TASK_END,
    DS_EV_COLLECT_TASK_END_BY_ERROR,
    DS_EV_COLLECT_TASK_END_BY_DETACHED,
    LO_OP_BUFFER,
)
from .exceptions import DeviceNotFoundError, DeviceError, CaptureError
from .structs import SrDatafeedPacket, SrDatafeedLogic, DsDatafeedCallback, DsEventCallback, DsDeviceBaseInfo
from . import lib as _lib_module


class DSLogicDevice:
    """
    DSLogic 设备封装。支持 with 语句。

    Parameters
    ----------
    lib_path : str, optional
        libsigrok4DSL.so 路径，不指定则自动搜索。
    firmware_dir : str, optional
        固件目录，默认使用 DSView 安装目录下的 firmware/。
    """

    def __init__(self, lib_path: str = None, firmware_dir: str = None):
        self._lib = _lib_module.load_library(lib_path)
        self._firmware_dir = firmware_dir
        self._initialized = False
        self._device_active = False

        # 采集状态
        self._capture_data: list[bytes] = []
        self._capture_done = threading.Event()
        self._capture_error: Optional[Exception] = None

        # 保持回调引用，防止 GC
        self._datafeed_cb = None
        self._event_cb = None

        # glib 句柄（懒加载）
        self._glib = None

    # ──────────────────────────────────────────────
    #  Context manager
    # ──────────────────────────────────────────────

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    # ──────────────────────────────────────────────
    #  生命周期
    # ──────────────────────────────────────────────

    def open(self):
        """初始化库并激活第一个找到的 DSLogic 设备"""
        if self._initialized:
            return

        # 1. 初始化库
        ret = self._lib.ds_lib_init()
        if ret != SR_OK:
            raise DeviceError("ds_lib_init() 失败", ret)
        self._initialized = True

        # 2. 设置固件目录（DSLogic 需要加载固件）
        fw_dir = self._firmware_dir or self._find_firmware_dir()
        if fw_dir:
            self._lib.ds_set_firmware_resource_dir(fw_dir.encode())

        # 3. 激活第一个设备（index=-1 选最后一个，0 选第一个）
        ret = self._lib.ds_active_device_by_index(0)
        if ret != SR_OK:
            raise DeviceNotFoundError(
                f"ds_active_device_by_index(0) 失败（错误码 {ret}），"
                "请检查 USB 连接和固件目录。"
            )
        self._device_active = True

    def close(self):
        """释放设备和库资源"""
        if self._device_active:
            try:
                self._lib.ds_stop_collect()
                self._lib.ds_release_actived_device()
            except Exception:
                pass
            self._device_active = False

        if self._initialized:
            try:
                self._lib.ds_lib_exit()
            except Exception:
                pass
            self._initialized = False

    # ──────────────────────────────────────────────
    #  设备信息
    # ──────────────────────────────────────────────

    def list_devices(self) -> list[dict]:
        """
        列出所有已连接的 DSLogic 设备。

        Returns
        -------
        list of dict, 每项含 'handle' 和 'name'
        """
        self._ensure_init()
        out_list = ctypes.c_void_p(None)
        out_count = ctypes.c_int(0)
        ret = self._lib.ds_get_device_list(
            ctypes.byref(out_list), ctypes.byref(out_count)
        )
        if ret != SR_OK or not out_list.value:
            return []

        count = out_count.value
        arr = ctypes.cast(out_list, ctypes.POINTER(DsDeviceBaseInfo * count)).contents
        devices = [
            {"handle": arr[i].handle, "name": arr[i].name.decode(errors="replace")}
            for i in range(count)
        ]

        # 释放 glib 分配的内存
        try:
            self._lib.g_free(out_list)
        except AttributeError:
            self._glib_call("g_free", [ctypes.c_void_p], None, out_list)

        return devices

    # ──────────────────────────────────────────────
    #  配置
    # ──────────────────────────────────────────────

    def set_samplerate(self, hz: int):
        """设置采样率，单位 Hz。例如 10_000_000 = 10 MHz"""
        self._config_set_uint64(SR_CONF_SAMPLERATE, hz)

    def set_sample_count(self, n: int):
        """设置采集样本数（Buffer 模式）"""
        self._config_set_uint64(SR_CONF_LIMIT_SAMPLES, n)

    def set_operation_mode(self, mode: int = LO_OP_BUFFER):
        """设置工作模式：LO_OP_BUFFER（默认）或 LO_OP_STREAM"""
        self._config_set_uint64(SR_CONF_OPERATION_MODE, mode)

    def enable_channel(self, index: int, enable: bool = True):
        """
        启用或禁用指定通道。

        Parameters
        ----------
        index : int
            通道索引，从 0 开始（CH0=0, CH1=1, ...）
        enable : bool
            True 启用，False 禁用
        """
        self._ensure_device()
        self._lib.ds_enable_device_channel_index.argtypes = [
            ctypes.c_int, ctypes.c_int
        ]
        self._lib.ds_enable_device_channel_index.restype = ctypes.c_int
        ret = self._lib.ds_enable_device_channel_index(index, int(enable))
        if ret != SR_OK:
            raise DeviceError(
                f"ds_enable_device_channel_index({index}, {enable}) 失败", ret
            )

    def enable_channels(self, channels: List[int], total: int = 8):
        """
        批量设置通道启用状态。未在列表中的通道会被禁用。

        Parameters
        ----------
        channels : list of int
            要启用的通道索引列表，例如 [0, 1, 2, 3]
        total : int
            设备总通道数，默认 8（DSLogic 基础版）
        """
        for i in range(total):
            self.enable_channel(i, i in channels)

    def set_voltage_threshold(self, voltage: float):
        """
        设置逻辑电平判断阈值电压。

        Parameters
        ----------
        voltage : float
            阈值电压，单位 V。常用值：
            - 1.8V 系统 → 0.9
            - 3.3V 系统 → 1.65（默认）
            - 5V 系统   → 2.5
        """
        self._ensure_device()
        gvar = self._gvariant_double(voltage)
        ret = self._lib.ds_set_actived_device_config(None, None, SR_CONF_VTH, gvar)
        if ret != SR_OK:
            raise DeviceError(
                f"set_voltage_threshold({voltage}V) 失败，错误码 {ret}"
            )

    # ──────────────────────────────────────────────
    #  采集
    # ──────────────────────────────────────────────

    def capture(self) -> bytes:
        """
        同步采集，阻塞直到采集完成。

        Returns
        -------
        bytes
            所有 SR_DF_LOGIC 包拼接的原始数据。
            每个字节对应 8 个通道在同一时刻的电平（bit0=CH0, ...）。
        """
        self._ensure_device()
        self._capture_data = []
        self._capture_done.clear()
        self._capture_error = None

        # 注册数据回调
        self._datafeed_cb = DsDatafeedCallback(self._on_datafeed)
        self._lib.ds_set_datafeed_callback(self._datafeed_cb)

        # 注册事件回调（监听采集结束事件）
        self._event_cb = DsEventCallback(self._on_event)
        self._lib.ds_set_event_callback(self._event_cb)

        # 开始采集（非阻塞，在内部线程运行）
        ret = self._lib.ds_start_collect()
        if ret != SR_OK:
            raise CaptureError(f"ds_start_collect() 失败，错误码 {ret}")

        # 等待结束事件
        self._capture_done.wait()

        if self._capture_error:
            raise self._capture_error

        return b"".join(self._capture_data)

    def async_capture(self, on_data: Callable[[bytes], None],
                      on_done: Callable[[], None] = None):
        """
        异步采集，每收到一包 Logic 数据调用 on_data，采集结束调用 on_done。

        Parameters
        ----------
        on_data : callable(bytes)
        on_done : callable, optional
        """
        self._ensure_device()

        def _datafeed(sdi, packet_ptr):
            packet = packet_ptr.contents
            if packet.type == SR_DF_LOGIC and packet.payload:
                logic = ctypes.cast(
                    packet.payload, ctypes.POINTER(SrDatafeedLogic)
                ).contents
                if logic.data and logic.length > 0:
                    raw = bytes(
                        ctypes.cast(
                            logic.data,
                            ctypes.POINTER(ctypes.c_uint8 * int(logic.length))
                        ).contents
                    )
                    on_data(raw)

        def _event(ev):
            if ev in (DS_EV_COLLECT_TASK_END,
                      DS_EV_COLLECT_TASK_END_BY_ERROR,
                      DS_EV_COLLECT_TASK_END_BY_DETACHED):
                if on_done:
                    on_done()

        self._datafeed_cb = DsDatafeedCallback(_datafeed)
        self._event_cb = DsEventCallback(_event)
        self._lib.ds_set_datafeed_callback(self._datafeed_cb)
        self._lib.ds_set_event_callback(self._event_cb)

        ret = self._lib.ds_start_collect()
        if ret != SR_OK:
            raise CaptureError(f"ds_start_collect() 失败，错误码 {ret}")

    def start(self):
        """
        开始采集，**不阻塞**。数据在后台持续积累。
        调用 stop_and_get() 停止并取回所有数据。

        适合"手动控制采集时长"的场景：
            dev.start()
            time.sleep(2)          # 或等待某个条件
            data = dev.stop_and_get()
        """
        self._ensure_device()
        self._capture_data = []
        self._capture_done.clear()
        self._capture_error = None

        self._datafeed_cb = DsDatafeedCallback(self._on_datafeed)
        self._lib.ds_set_datafeed_callback(self._datafeed_cb)

        self._event_cb = DsEventCallback(self._on_event)
        self._lib.ds_set_event_callback(self._event_cb)

        ret = self._lib.ds_start_collect()
        if ret != SR_OK:
            raise CaptureError(f"ds_start_collect() 失败，错误码 {ret}")

    def stop_and_get(self) -> bytes:
        """
        停止采集并返回从 start() 开始积累的所有数据。

        Returns
        -------
        bytes
            所有 SR_DF_LOGIC 包拼接的原始数据。
            每字节 = 8 通道在同一时刻的电平（bit0=CH0 ... bit7=CH7）
        """
        self._lib.ds_stop_collect()
        # 等待库回调通知采集真正结束（最多 3 秒）
        self._capture_done.wait(timeout=3.0)

        if self._capture_error:
            raise self._capture_error

        return b"".join(self._capture_data)

    def stop(self):
        """停止正在进行的采集（不返回数据，用 stop_and_get() 代替）"""
        if self._initialized:
            self._lib.ds_stop_collect()

    # ──────────────────────────────────────────────
    #  导出文件
    # ──────────────────────────────────────────────

    def export_csv(self, data: bytes, path: str,
                   channels: List[int] = None, samplerate: int = None):
        """
        将采集数据导出为 CSV 文件。

        Parameters
        ----------
        data : bytes
            capture() 返回的原始数据
        path : str
            输出文件路径，例如 "capture.csv"
        channels : list of int, optional
            要导出的通道列表，默认导出全部 8 个通道
        samplerate : int, optional
            采样率（Hz），用于计算时间戳列；不传则只输出序号

        CSV 格式：
            index, time_us(可选), CH0, CH1, CH2, ...
        """
        if channels is None:
            channels = list(range(8))

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)

            # 表头
            header = ["index"]
            if samplerate:
                header.append("time_us")
            header += [f"CH{ch}" for ch in channels]
            writer.writerow(header)

            # 数据行
            for i, byte in enumerate(data):
                row = [i]
                if samplerate:
                    row.append(f"{i / samplerate * 1e6:.3f}")
                row += [1 if (byte >> ch) & 1 else 0 for ch in channels]
                writer.writerow(row)

    def export_vcd(self, data: bytes, path: str,
                   channels: List[int] = None, samplerate: int = 10_000_000):
        """
        将采集数据导出为 VCD（Value Change Dump）文件。
        VCD 是标准波形格式，可用 GTKWave 等工具打开。

        Parameters
        ----------
        data : bytes
            capture() 返回的原始数据
        path : str
            输出文件路径，例如 "capture.vcd"
        channels : list of int, optional
            要导出的通道列表，默认全部 8 个
        samplerate : int
            采样率（Hz），默认 10 MHz
        """
        if channels is None:
            channels = list(range(8))

        # VCD 时间单位：1ns（1GHz base），timescale 根据采样率计算
        period_ns = int(1e9 / samplerate)

        with open(path, "w") as f:
            # 文件头
            f.write("$timescale 1ns $end\n")
            f.write("$scope module DSLogic $end\n")
            for ch in channels:
                f.write(f"$var wire 1 {chr(ord('!') + ch)} CH{ch} $end\n")
            f.write("$upscope $end\n")
            f.write("$enddefinitions $end\n")
            f.write("#0\n")
            f.write("$dumpvars\n")

            # 初始状态
            if data:
                first = data[0]
                for ch in channels:
                    val = (first >> ch) & 1
                    f.write(f"{val}{chr(ord('!') + ch)}\n")
            f.write("$end\n")

            # 只写发生变化的时刻（节省文件大小）
            prev = data[0] if data else 0
            for i, byte in enumerate(data):
                changed = byte ^ prev
                if changed or i == 0:
                    f.write(f"#{i * period_ns}\n")
                    for ch in channels:
                        if (changed >> ch) & 1:
                            val = (byte >> ch) & 1
                            f.write(f"{val}{chr(ord('!') + ch)}\n")
                    prev = byte

    def export_binary(self, data: bytes, path: str):
        """
        直接将原始采集数据写入二进制文件。

        Parameters
        ----------
        data : bytes
            capture() 返回的原始数据
        path : str
            输出文件路径
        """
        with open(path, "wb") as f:
            f.write(data)

    # ──────────────────────────────────────────────
    #  内部方法
    # ──────────────────────────────────────────────

    def _on_datafeed(self, sdi, packet_ptr):
        try:
            packet = packet_ptr.contents
            if packet.type == SR_DF_LOGIC and packet.payload:
                logic = ctypes.cast(
                    packet.payload, ctypes.POINTER(SrDatafeedLogic)
                ).contents
                if logic.data and logic.length > 0:
                    raw = bytes(
                        ctypes.cast(
                            logic.data,
                            ctypes.POINTER(ctypes.c_uint8 * int(logic.length))
                        ).contents
                    )
                    self._capture_data.append(raw)
        except Exception as e:
            self._capture_error = CaptureError(f"datafeed 回调出错: {e}")
            self._capture_done.set()

    def _on_event(self, event: int):
        if event in (DS_EV_COLLECT_TASK_END,
                     DS_EV_COLLECT_TASK_END_BY_ERROR,
                     DS_EV_COLLECT_TASK_END_BY_DETACHED):
            if event != DS_EV_COLLECT_TASK_END:
                self._capture_error = CaptureError(
                    f"采集被中断（event={event}）"
                )
            self._capture_done.set()

    def _config_set_uint64(self, key: int, value: int):
        self._ensure_device()
        gvar = self._gvariant_uint64(value)
        ret = self._lib.ds_set_actived_device_config(None, None, key, gvar)
        if ret != SR_OK:
            raise DeviceError(f"ds_set_actived_device_config(key={key}) 失败", ret)

    def _gvariant_uint64(self, value: int) -> ctypes.c_void_p:
        """创建 GVariant uint64，优先从 libsigrok4DSL，其次从系统 glib"""
        try:
            return self._lib.g_variant_new_uint64(ctypes.c_uint64(value))
        except AttributeError:
            return self._get_glib().g_variant_new_uint64(ctypes.c_uint64(value))

    def _gvariant_double(self, value: float) -> ctypes.c_void_p:
        """创建 GVariant double（用于 VTH 等 float 类型配置）"""
        try:
            fn = self._lib.g_variant_new_double
            fn.argtypes = [ctypes.c_double]
            fn.restype = ctypes.c_void_p
            return fn(ctypes.c_double(value))
        except AttributeError:
            glib = self._get_glib()
            glib.g_variant_new_double.argtypes = [ctypes.c_double]
            glib.g_variant_new_double.restype = ctypes.c_void_p
            return glib.g_variant_new_double(ctypes.c_double(value))

    def _get_glib(self):
        if self._glib is None:
            name = ctypes.util.find_library("glib-2.0")
            if not name:
                raise DeviceError("找不到 glib-2.0，无法创建 GVariant")
            self._glib = ctypes.CDLL(name)
            self._glib.g_variant_new_uint64.argtypes = [ctypes.c_uint64]
            self._glib.g_variant_new_uint64.restype  = ctypes.c_void_p
            self._glib.g_free.argtypes = [ctypes.c_void_p]
            self._glib.g_free.restype  = None
        return self._glib

    def _glib_call(self, fn_name, argtypes, restype, *args):
        glib = self._get_glib()
        fn = getattr(glib, fn_name)
        fn.argtypes = argtypes
        fn.restype  = restype
        return fn(*args)

    def _find_firmware_dir(self) -> Optional[str]:
        """在常见位置查找 DSLogic 固件目录"""
        candidates = [
            r"C:\Program Files\DSView",
            r"C:\Program Files (x86)\DSView",
            "/usr/share/DSView",
            "/usr/local/share/DSView",
            os.path.expanduser("~/.local/share/DSView"),
        ]
        for d in candidates:
            if os.path.isdir(d):
                return d
        return None

    def _ensure_init(self):
        if not self._initialized:
            raise DeviceError("库未初始化，请先调用 open() 或使用 with 语句")

    def _ensure_device(self):
        self._ensure_init()
        if not self._device_active:
            raise DeviceError("没有激活的设备，请先调用 open()")
