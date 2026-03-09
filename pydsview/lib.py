"""
加载 libsigrok4DSL 动态库并绑定 C 函数签名

编译好的库文件默认搜索路径：
  Windows: libsigrok4DSL.dll（DSView 安装目录或本目录）
  Linux:   libsigrok4DSL.so / libsigrok4DSL.so.0

自定义路径：
  import pydsview.lib as lib
  lib.load_library("/path/to/libsigrok4DSL.so")
"""

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path

from .exceptions import LibraryNotFoundError
from .structs import SrDatafeedPacket, DatafeedCallback

_lib = None  # 全局库句柄


def _candidate_paths():
    """返回候选库路径列表，优先级从高到低"""
    candidates = []

    # 1. 环境变量 LIBSIGROK4DSL_PATH 指定
    env_path = os.environ.get("LIBSIGROK4DSL_PATH")
    if env_path:
        candidates.append(env_path)

    # 2. pydsview 包同级目录
    pkg_dir = Path(__file__).parent
    for name in ("libsigrok4DSL.dll", "libsigrok4DSL.so", "libsigrok4DSL.so.0"):
        candidates.append(str(pkg_dir / name))
        candidates.append(str(pkg_dir.parent / name))

    # 3. DSView 默认安装路径（Windows）
    if sys.platform == "win32":
        for base in [
            r"C:\Program Files\DSView",
            r"C:\Program Files (x86)\DSView",
        ]:
            candidates.append(os.path.join(base, "libsigrok4DSL.dll"))

    # 4. 系统 PATH / ldconfig
    found = ctypes.util.find_library("sigrok4DSL")
    if found:
        candidates.append(found)

    return candidates


def load_library(path: str = None) -> ctypes.CDLL:
    """
    加载 libsigrok4DSL 动态库。

    Parameters
    ----------
    path : str, optional
        库文件的完整路径。不指定时自动搜索常见位置。

    Returns
    -------
    ctypes.CDLL
        已加载并完成函数签名绑定的库对象。

    Raises
    ------
    LibraryNotFoundError
        找不到或无法加载库文件时抛出。
    """
    global _lib

    candidates = [path] if path else _candidate_paths()

    last_err = None
    for p in candidates:
        if p is None:
            continue
        try:
            _lib = ctypes.CDLL(p)
            _bind_functions(_lib)
            return _lib
        except OSError as e:
            last_err = e

    raise LibraryNotFoundError(
        "找不到 libsigrok4DSL 库文件。\n"
        "请先编译 DSView（见 README 的 WSL2 编译步骤），\n"
        "或设置环境变量 LIBSIGROK4DSL_PATH 指向库文件路径。\n"
        f"最后一个错误：{last_err}"
    )


def get_lib() -> ctypes.CDLL:
    """获取已加载的库，未加载则先尝试自动加载"""
    global _lib
    if _lib is None:
        load_library()
    return _lib


def _bind_functions(lib: ctypes.CDLL):
    """
    为所有公开 C 函数绑定 argtypes 和 restype。
    函数签名来自 libsigrok4DSL/libsigrok.h 及 lib_main.c。
    """

    # sr_init(struct sr_context **ctx) → int
    lib.sr_init.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    lib.sr_init.restype  = ctypes.c_int

    # sr_exit(struct sr_context *ctx) → int
    lib.sr_exit.argtypes = [ctypes.c_void_p]
    lib.sr_exit.restype  = ctypes.c_int

    # --- 驱动扫描 ---
    # sr_driver_list(struct sr_context *ctx) → struct sr_dev_driver **
    lib.sr_driver_list.argtypes = [ctypes.c_void_p]
    lib.sr_driver_list.restype  = ctypes.c_void_p

    # sr_driver_init(struct sr_context *ctx, struct sr_dev_driver *driver) → int
    lib.sr_driver_init.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.sr_driver_init.restype  = ctypes.c_int

    # sr_driver_scan(struct sr_dev_driver *driver, GSList *options) → GSList *
    lib.sr_driver_scan.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.sr_driver_scan.restype  = ctypes.c_void_p

    # --- 设备操作 ---
    # sr_dev_open(struct sr_dev_inst *sdi) → int
    lib.sr_dev_open.argtypes = [ctypes.c_void_p]
    lib.sr_dev_open.restype  = ctypes.c_int

    # sr_dev_close(struct sr_dev_inst *sdi) → int
    lib.sr_dev_close.argtypes = [ctypes.c_void_p]
    lib.sr_dev_close.restype  = ctypes.c_int

    # --- 配置 ---
    # sr_config_get(driver, sdi, probe_group, key, data) → int
    lib.sr_config_get.argtypes = [
        ctypes.c_void_p,  # driver
        ctypes.c_void_p,  # sdi
        ctypes.c_void_p,  # probe_group
        ctypes.c_int,     # key
        ctypes.c_void_p,  # GVariant **data
    ]
    lib.sr_config_get.restype = ctypes.c_int

    # sr_config_set(sdi, probe_group, key, data) → int
    lib.sr_config_set.argtypes = [
        ctypes.c_void_p,  # sdi
        ctypes.c_void_p,  # probe_group
        ctypes.c_int,     # key
        ctypes.c_void_p,  # GVariant *data
    ]
    lib.sr_config_set.restype = ctypes.c_int

    # --- Session ---
    # sr_session_new() → struct sr_session *
    lib.sr_session_new.argtypes = []
    lib.sr_session_new.restype  = ctypes.c_void_p

    # sr_session_destroy() → int
    lib.sr_session_destroy.argtypes = []
    lib.sr_session_destroy.restype  = ctypes.c_int

    # sr_session_dev_add(sdi) → int
    lib.sr_session_dev_add.argtypes = [ctypes.c_void_p]
    lib.sr_session_dev_add.restype  = ctypes.c_int

    # sr_session_datafeed_callback_add(cb, cb_data) → int
    lib.sr_session_datafeed_callback_add.argtypes = [
        DatafeedCallback,
        ctypes.c_void_p,
    ]
    lib.sr_session_datafeed_callback_add.restype = ctypes.c_int

    # sr_session_run() → int
    lib.sr_session_run.argtypes = []
    lib.sr_session_run.restype  = ctypes.c_int

    # sr_session_stop() → int
    lib.sr_session_stop.argtypes = []
    lib.sr_session_stop.restype  = ctypes.c_int

    # --- GLib GVariant helpers（libsigrok4DSL 通常自带或依赖 glib）---
    # 如果 glib 独立，这部分需要单独加载 libglib
    # 这里先尝试从同一个库中绑定（有些构建会把 glib 静态链接进去）
    try:
        # g_variant_new_uint64(guint64 value) → GVariant *
        lib.g_variant_new_uint64.argtypes = [ctypes.c_uint64]
        lib.g_variant_new_uint64.restype  = ctypes.c_void_p

        lib.g_variant_new_boolean.argtypes = [ctypes.c_int]
        lib.g_variant_new_boolean.restype  = ctypes.c_void_p

        lib.g_variant_get_uint64.argtypes = [ctypes.c_void_p]
        lib.g_variant_get_uint64.restype  = ctypes.c_uint64

        lib.g_variant_unref.argtypes = [ctypes.c_void_p]
        lib.g_variant_unref.restype  = None
    except AttributeError:
        # glib 不在同一库中，后续使用时另行加载
        pass
