"""
DSLogicDevice —— 用 Python 控制 DSLogic 逻辑分析仪

典型用法：

    from pydsview import DSLogicDevice

    with DSLogicDevice() as dev:
        dev.set_samplerate(10_000_000)   # 10 MHz
        dev.set_sample_count(1_000_000)  # 1M 样本
        data = dev.capture()             # 阻塞直到采完
    # data 是 bytes，按通道解析见 README
"""

import ctypes
import threading
from typing import Callable, Optional

from .constants import (
    SR_OK,
    SR_CONF_SAMPLERATE,
    SR_CONF_LIMIT_SAMPLES,
    SR_CONF_OPERATION_MODE,
    SR_DF_HEADER, SR_DF_END, SR_DF_LOGIC,
    LOGIC, LO_OP_BUFFER,
)
from .exceptions import DeviceNotFoundError, DeviceError, CaptureError, LibraryNotFoundError
from .structs import SrDatafeedPacket, SrDatafeedLogic, DatafeedCallback
from . import lib as _lib_module


class DSLogicDevice:
    """
    DSLogic 设备封装类。

    支持 context manager（with 语句），确保资源自动释放。
    """

    def __init__(self, lib_path: str = None):
        """
        Parameters
        ----------
        lib_path : str, optional
            libsigrok4DSL 库文件路径。不指定时自动搜索。
        """
        self._lib = _lib_module.load_library(lib_path)
        self._ctx = ctypes.c_void_p(None)   # sr_context *
        self._sdi = None                     # sr_dev_inst * (c_void_p)
        self._driver = None                  # sr_dev_driver *
        self._opened = False
        self._session_active = False

        # 采集状态
        self._capture_data: list[bytes] = []
        self._capture_done = threading.Event()
        self._capture_error: Optional[Exception] = None

        # 保持 ctypes callback 引用，防止被 GC
        self._datafeed_cb = None

    # ──────────────────────────────────────────────
    #  Context manager
    # ──────────────────────────────────────────────

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    # ──────────────────────────────────────────────
    #  设备生命周期
    # ──────────────────────────────────────────────

    def open(self):
        """初始化 libsigrok4DSL 并打开第一个找到的 DSLogic 设备"""
        if self._opened:
            return

        # 1. 初始化 sr_context
        ctx_ptr = ctypes.c_void_p(None)
        ret = self._lib.sr_init(ctypes.byref(ctx_ptr))
        if ret != SR_OK:
            raise DeviceError("sr_init() 失败", ret)
        self._ctx = ctx_ptr

        # 2. 枚举驱动，找 DSLogic 驱动
        driver_list_ptr = self._lib.sr_driver_list(self._ctx)
        if not driver_list_ptr:
            raise DeviceNotFoundError("没有找到任何 libsigrok4DSL 驱动")

        self._driver = self._find_dslogic_driver(driver_list_ptr)
        if self._driver is None:
            raise DeviceNotFoundError("找不到 DSLogic 驱动（dslogic）")

        # 3. 初始化驱动
        ret = self._lib.sr_driver_init(self._ctx, self._driver)
        if ret != SR_OK:
            raise DeviceError("sr_driver_init() 失败", ret)

        # 4. 扫描设备
        device_list = self._lib.sr_driver_scan(self._driver, None)
        if not device_list:
            raise DeviceNotFoundError("扫描不到 DSLogic 设备，请检查 USB 连接")

        # 取第一个设备（GSList->data）
        glist = ctypes.cast(device_list, ctypes.POINTER(ctypes.c_void_p))
        self._sdi = ctypes.c_void_p(glist[0])

        # 5. 打开设备
        ret = self._lib.sr_dev_open(self._sdi)
        if ret != SR_OK:
            raise DeviceError("sr_dev_open() 失败", ret)

        self._opened = True

    def close(self):
        """关闭设备并释放 sr_context"""
        if self._session_active:
            try:
                self._lib.sr_session_stop()
                self._lib.sr_session_destroy()
            except Exception:
                pass
            self._session_active = False

        if self._sdi and self._opened:
            try:
                self._lib.sr_dev_close(self._sdi)
            except Exception:
                pass

        if self._ctx:
            try:
                self._lib.sr_exit(self._ctx)
            except Exception:
                pass
            self._ctx = ctypes.c_void_p(None)

        self._opened = False
        self._sdi = None

    # ──────────────────────────────────────────────
    #  配置
    # ──────────────────────────────────────────────

    def set_samplerate(self, hz: int):
        """
        设置采样率。

        Parameters
        ----------
        hz : int
            采样率，单位 Hz。例如 10_000_000 表示 10 MHz。
        """
        self._config_set_uint64(SR_CONF_SAMPLERATE, hz)

    def set_sample_count(self, n: int):
        """
        设置采集样本数（Buffer 模式下为总样本数）。

        Parameters
        ----------
        n : int
            样本数，例如 1_000_000（1M）。
        """
        self._config_set_uint64(SR_CONF_LIMIT_SAMPLES, n)

    def set_operation_mode(self, mode: int = LO_OP_BUFFER):
        """
        设置 DSLogic 工作模式。

        Parameters
        ----------
        mode : int
            LO_OP_BUFFER（默认）或 LO_OP_STREAM。
        """
        self._config_set_uint64(SR_CONF_OPERATION_MODE, mode)

    # ──────────────────────────────────────────────
    #  采集
    # ──────────────────────────────────────────────

    def capture(self) -> bytes:
        """
        同步采集数据，阻塞直到采集完成。

        Returns
        -------
        bytes
            所有 SR_DF_LOGIC 数据包的原始字节拼接。
            解析格式取决于 unitsize 和通道数，详见 README。
        """
        self._ensure_open()
        self._capture_data = []
        self._capture_done.clear()
        self._capture_error = None

        # 创建 session
        session = self._lib.sr_session_new()
        if not session:
            raise CaptureError("sr_session_new() 返回 NULL")
        self._session_active = True

        # 添加设备
        ret = self._lib.sr_session_dev_add(self._sdi)
        if ret != SR_OK:
            raise CaptureError(f"sr_session_dev_add() 失败，错误码 {ret}")

        # 注册数据回调
        self._datafeed_cb = DatafeedCallback(self._on_datafeed)
        ret = self._lib.sr_session_datafeed_callback_add(self._datafeed_cb, None)
        if ret != SR_OK:
            raise CaptureError(f"sr_session_datafeed_callback_add() 失败，错误码 {ret}")

        # 运行（阻塞直到 SR_DF_END 或出错）
        ret = self._lib.sr_session_run()
        self._session_active = False
        self._lib.sr_session_destroy()

        if self._capture_error:
            raise self._capture_error

        if ret != SR_OK:
            raise CaptureError(f"sr_session_run() 失败，错误码 {ret}")

        return b"".join(self._capture_data)

    def async_capture(self, callback: Callable[[bytes], None]):
        """
        异步采集：在后台线程运行采集，每个 Logic 数据包调用一次 callback。

        Parameters
        ----------
        callback : callable
            接受 bytes 参数的函数，每次收到一包数据时调用。
        """
        self._ensure_open()

        def _run():
            session = self._lib.sr_session_new()
            if not session:
                return
            self._lib.sr_session_dev_add(self._sdi)

            def _cb(sdi, packet_ptr, cb_data):
                packet = packet_ptr.contents
                if packet.type == SR_DF_LOGIC and packet.payload:
                    logic = ctypes.cast(
                        packet.payload, ctypes.POINTER(SrDatafeedLogic)
                    ).contents
                    if logic.data and logic.length > 0:
                        raw = bytes(
                            ctypes.cast(logic.data, ctypes.POINTER(ctypes.c_uint8 * logic.length)).contents
                        )
                        callback(raw)

            cb_ref = DatafeedCallback(_cb)
            self._lib.sr_session_datafeed_callback_add(cb_ref, None)
            self._lib.sr_session_run()
            self._lib.sr_session_destroy()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

    # ──────────────────────────────────────────────
    #  内部方法
    # ──────────────────────────────────────────────

    def _on_datafeed(self, sdi, packet_ptr, cb_data):
        """datafeed 回调，由 C 库在采集线程调用"""
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

            elif packet.type == SR_DF_END:
                self._capture_done.set()

        except Exception as e:
            self._capture_error = CaptureError(f"datafeed 回调出错: {e}")
            self._capture_done.set()

    def _config_set_uint64(self, key: int, value: int):
        """通过 GVariant uint64 设置设备配置"""
        self._ensure_open()
        try:
            gvar = self._lib.g_variant_new_uint64(ctypes.c_uint64(value))
        except AttributeError:
            # glib 函数未绑定，尝试从系统 glib 加载
            glib = self._load_glib()
            gvar = glib.g_variant_new_uint64(ctypes.c_uint64(value))

        ret = self._lib.sr_config_set(self._sdi, None, key, gvar)
        if ret != SR_OK:
            raise DeviceError(f"sr_config_set(key={key}, value={value}) 失败", ret)

    def _load_glib(self):
        """尝试加载系统 glib-2.0"""
        import ctypes.util
        glib_name = ctypes.util.find_library("glib-2.0")
        if not glib_name:
            raise DeviceError("找不到 glib-2.0，无法创建 GVariant")
        glib = ctypes.CDLL(glib_name)
        glib.g_variant_new_uint64.argtypes = [ctypes.c_uint64]
        glib.g_variant_new_uint64.restype  = ctypes.c_void_p
        return glib

    def _find_dslogic_driver(self, driver_list_ptr) -> Optional[ctypes.c_void_p]:
        """
        从 sr_dev_driver** 列表中找到 DSLogic 驱动。
        DSLogic 驱动的 name 字段为 "dslogic"。
        driver_list 是 NULL 结尾的指针数组。
        """
        # sr_dev_driver 的第一个字段是 char *name
        i = 0
        while True:
            arr = ctypes.cast(
                driver_list_ptr,
                ctypes.POINTER(ctypes.c_void_p)
            )
            drv_ptr = arr[i]
            if not drv_ptr:
                break
            # 第一个字段：name (char *)
            name_ptr = ctypes.cast(drv_ptr, ctypes.POINTER(ctypes.c_char_p))
            name = name_ptr[0]
            if name and b"dslogic" in name.lower():
                return ctypes.c_void_p(drv_ptr)
            i += 1
        return None

    def _ensure_open(self):
        if not self._opened:
            raise DeviceError("设备未打开，请先调用 open() 或使用 with 语句")
