"""
加载 libsigrok4DSL 动态库并绑定 ds_* C 函数签名

DreamSourceLab 在 lib_main.c 中提供了高层 ds_* API，
比底层 sr_* API 更简洁，是 DSView 内部实际使用的接口。

库文件搜索顺序：
  1. 环境变量 LIBSIGROK4DSL_PATH
  2. pydsview 包目录（优先）
  3. Windows DSView 安装目录
  4. 系统 PATH / ldconfig
"""

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path

from .exceptions import LibraryNotFoundError
from .structs import SrDatafeedPacket, DsDatafeedCallback, DsEventCallback

_lib = None  # 全局库句柄

# Windows: 在 import 时把 pydsview 包目录加入 DLL 搜索路径
# 这样 libglib-2.0-0.dll 等运行时依赖才能被找到
import sys as _sys
if _sys.platform == "win32":
    import os as _os
    _pkg_dir = str(Path(__file__).parent)
    if hasattr(_os, "add_dll_directory"):  # Python 3.8+
        _os.add_dll_directory(_pkg_dir)


def _candidate_paths():
    candidates = []

    env_path = os.environ.get("LIBSIGROK4DSL_PATH")
    if env_path:
        candidates.append(env_path)

    pkg_dir = Path(__file__).parent
    for name in ("libsigrok4DSL.so", "libsigrok4DSL.so.0", "libsigrok4DSL.dll"):
        candidates.append(str(pkg_dir / name))
        candidates.append(str(pkg_dir.parent / name))

    if sys.platform == "win32":
        for base in [
            r"C:\Program Files\DSView",
            r"C:\Program Files (x86)\DSView",
        ]:
            candidates.append(os.path.join(base, "libsigrok4DSL.dll"))

    found = ctypes.util.find_library("sigrok4DSL")
    if found:
        candidates.append(found)

    return candidates


def load_library(path: str = None) -> ctypes.CDLL:
    """
    加载 libsigrok4DSL.so。

    Raises
    ------
    LibraryNotFoundError
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
        "请编译 DSView 后将 libsigrok4DSL.so 放到 pydsview/ 目录，\n"
        "或设置环境变量 LIBSIGROK4DSL_PATH。\n"
        f"最后错误：{last_err}"
    )


def get_lib() -> ctypes.CDLL:
    global _lib
    if _lib is None:
        load_library()
    return _lib


def _bind_functions(lib: ctypes.CDLL):
    """
    绑定 lib_main.c 中的 ds_* 公开 API。
    签名来自 libsigrok4DSL/libsigrok.h 末尾的 SR_API 声明。
    """

    # int ds_lib_init()
    lib.ds_lib_init.argtypes = []
    lib.ds_lib_init.restype  = ctypes.c_int

    # int ds_lib_exit()
    lib.ds_lib_exit.argtypes = []
    lib.ds_lib_exit.restype  = ctypes.c_int

    # void ds_set_event_callback(dslib_event_callback_t cb)
    lib.ds_set_event_callback.argtypes = [DsEventCallback]
    lib.ds_set_event_callback.restype  = None

    # void ds_set_datafeed_callback(ds_datafeed_callback_t cb)
    lib.ds_set_datafeed_callback.argtypes = [DsDatafeedCallback]
    lib.ds_set_datafeed_callback.restype  = None

    # void ds_set_firmware_resource_dir(const char *dir)
    lib.ds_set_firmware_resource_dir.argtypes = [ctypes.c_char_p]
    lib.ds_set_firmware_resource_dir.restype  = None

    # void ds_set_user_data_dir(const char *dir)
    lib.ds_set_user_data_dir.argtypes = [ctypes.c_char_p]
    lib.ds_set_user_data_dir.restype  = None

    # int ds_get_device_list(struct ds_device_base_info **out_list, int *out_count)
    lib.ds_get_device_list.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),  # ds_device_base_info**
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.ds_get_device_list.restype = ctypes.c_int

    # int ds_active_device(ds_device_handle handle)  -- handle = uint64
    lib.ds_active_device.argtypes = [ctypes.c_uint64]
    lib.ds_active_device.restype  = ctypes.c_int

    # int ds_active_device_by_index(int index)
    lib.ds_active_device_by_index.argtypes = [ctypes.c_int]
    lib.ds_active_device_by_index.restype  = ctypes.c_int

    # int ds_release_actived_device()
    lib.ds_release_actived_device.argtypes = []
    lib.ds_release_actived_device.restype  = ctypes.c_int

    # int ds_get_actived_device_config(const struct sr_channel *ch, const struct sr_channel_group *cg, int key, GVariant **data)
    lib.ds_get_actived_device_config.argtypes = [
        ctypes.c_void_p,  # ch
        ctypes.c_void_p,  # cg
        ctypes.c_int,     # key
        ctypes.POINTER(ctypes.c_void_p),  # GVariant **
    ]
    lib.ds_get_actived_device_config.restype = ctypes.c_int

    # int ds_set_actived_device_config(const struct sr_channel *ch, const struct sr_channel_group *cg, int key, GVariant *data)
    lib.ds_set_actived_device_config.argtypes = [
        ctypes.c_void_p,  # ch
        ctypes.c_void_p,  # cg
        ctypes.c_int,     # key
        ctypes.c_void_p,  # GVariant *
    ]
    lib.ds_set_actived_device_config.restype = ctypes.c_int

    # int ds_start_collect()
    lib.ds_start_collect.argtypes = []
    lib.ds_start_collect.restype  = ctypes.c_int

    # int ds_stop_collect()
    lib.ds_stop_collect.argtypes = []
    lib.ds_stop_collect.restype  = ctypes.c_int

    # int ds_is_collecting()
    lib.ds_is_collecting.argtypes = []
    lib.ds_is_collecting.restype  = ctypes.c_int

    # int ds_have_actived_device()
    lib.ds_have_actived_device.argtypes = []
    lib.ds_have_actived_device.restype  = ctypes.c_int

    # int ds_get_actived_device_mode()
    lib.ds_get_actived_device_mode.argtypes = []
    lib.ds_get_actived_device_mode.restype  = ctypes.c_int

    # int ds_enable_device_channel_index(int ch_index, gboolean enable)
    lib.ds_enable_device_channel_index.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.ds_enable_device_channel_index.restype  = ctypes.c_int

    # int ds_set_device_channel_name(int ch_index, const char *name)
    lib.ds_set_device_channel_name.argtypes = [ctypes.c_int, ctypes.c_char_p]
    lib.ds_set_device_channel_name.restype  = ctypes.c_int

    # int ds_get_actived_device_status(struct sr_status *status, gboolean prg)
    lib.ds_get_actived_device_status.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.ds_get_actived_device_status.restype  = ctypes.c_int

    # GVariant helpers（glib，可能不在同一库）
    try:
        lib.g_variant_new_uint64.argtypes = [ctypes.c_uint64]
        lib.g_variant_new_uint64.restype  = ctypes.c_void_p
        lib.g_variant_new_boolean.argtypes = [ctypes.c_int]
        lib.g_variant_new_boolean.restype  = ctypes.c_void_p
        lib.g_variant_get_uint64.argtypes  = [ctypes.c_void_p]
        lib.g_variant_get_uint64.restype   = ctypes.c_uint64
        lib.g_variant_unref.argtypes = [ctypes.c_void_p]
        lib.g_variant_unref.restype  = None
        lib.g_free.argtypes = [ctypes.c_void_p]
        lib.g_free.restype  = None
    except AttributeError:
        pass  # glib 从系统单独加载
