"""
DSLogicDevice —— 用 Python 控制 DSLogic 逻辑分析仪

使用 DreamSourceLab 的 ds_* 高层 API（lib_main.c）。

典型用法：

    from pydsview import DSLogicDevice

    with DSLogicDevice() as dev:
        dev.set_samplerate(10_000_000)   # 10 MHz
        dev.set_sample_count(1_000_000)  # 1M 样本
        data = dev.capture()             # bytes，每字节8通道

"""

import ctypes
import os
import threading
from typing import Callable, Optional

from .constants import (
    SR_OK,
    SR_CONF_SAMPLERATE,
    SR_CONF_LIMIT_SAMPLES,
    SR_CONF_OPERATION_MODE,
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

    def stop(self):
        """停止正在进行的采集"""
        if self._initialized:
            self._lib.ds_stop_collect()

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
