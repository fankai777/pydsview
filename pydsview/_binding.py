"""
pydsview._binding — cffi ABI-mode bindings for libsigrok4dsl + shim.

Loads the shared library at import time and exposes ``ffi`` and ``lib``.
"""

import os
import sys
import cffi

ffi = cffi.FFI()

# ---------------------------------------------------------------------------
# C declarations (ABI mode — no compiler needed at runtime)
# ---------------------------------------------------------------------------

ffi.cdef("""
    /* ---- opaque types ---- */
    typedef unsigned long long ds_device_handle;
    typedef void *GVariant;
    typedef void *GSList;

    /* ---- structs ---- */
    struct ds_device_base_info {
        ds_device_handle handle;
        char name[150];
    };

    struct ds_device_full_info {
        ds_device_handle handle;
        char name[150];
        char path[256];
        char driver_name[20];
        int  dev_type;
        int  actived_times;
        void *di;                 /* sr_dev_inst*, opaque */
    };

    struct sr_datafeed_packet {
        uint16_t type;
        uint16_t status;
        const void *payload;
        int bExportOriginalData;
    };

    struct sr_datafeed_logic {
        uint64_t length;
        int format;
        uint16_t index;
        uint16_t order;
        uint16_t unitsize;
        uint16_t data_error;
        uint64_t error_pattern;
        void *data;
    };

    struct sr_datafeed_dso {
        void *probes;
        int num_samples;
        int mq;
        int unit;
        uint64_t mqflags;
        int samplerate_tog;
        int trig_flag;
        uint8_t trig_ch;
        void *data;
    };

    struct sr_datafeed_analog {
        void *probes;
        int num_samples;
        uint8_t unit_bits;
        uint16_t unit_pitch;
        int mq;
        int unit;
        uint64_t mqflags;
        void *data;
    };

    struct sr_config_info {
        int  key;
        int  datatype;
        const char *name;
    };

    /* ---- ds_* public API ---- */
    int  ds_lib_init(void);
    int  ds_lib_exit(void);

    void ds_set_firmware_resource_dir(const char *dir);
    void ds_set_user_data_dir(const char *dir);

    typedef void (*dslib_event_callback_t)(int event);
    typedef void (*ds_datafeed_callback_t)(const void *sdi,
                                           const struct sr_datafeed_packet *packet);

    void ds_set_event_callback(dslib_event_callback_t cb);
    void ds_set_datafeed_callback(ds_datafeed_callback_t cb);

    int  ds_get_device_list(struct ds_device_base_info **out_list, int *out_count);
    int  ds_active_device(ds_device_handle handle);
    int  ds_active_device_by_index(int index);
    int  ds_get_actived_device_index(void);
    int  ds_have_actived_device(void);
    int  ds_device_from_file(const char *file_path);
    int  ds_remove_device(ds_device_handle handle);
    int  ds_reload_device_list(void);
    int  ds_close_all_device(void);

    int  ds_get_actived_device_info(struct ds_device_full_info *fill_info);
    int  ds_get_actived_device_mode(void);
    int  ds_get_actived_device_init_status(int *status);

    int  ds_start_collect(void);
    int  ds_stop_collect(void);
    int  ds_is_collecting(void);
    int  ds_release_actived_device(void);
    int  ds_get_last_error(void);

    /* config get/set — ch and cg are opaque pointers (NULL OK) */
    int  ds_get_actived_device_config(const void *ch, const void *cg,
                                      int key, GVariant **data);
    int  ds_set_actived_device_config(const void *ch, const void *cg,
                                      int key, GVariant *data);
    int  ds_get_actived_device_config_list(const void *cg, int key,
                                           GVariant **data);
    const struct sr_config_info *ds_get_actived_device_config_info(int key);

    /* channel management */
    int  ds_enable_device_channel_index(int ch_index, int enable);
    int  ds_set_device_channel_name(int ch_index, const char *name);

    /* trigger */
    int      ds_trigger_reset(void);
    int      ds_trigger_set_en(uint16_t enable);
    uint16_t ds_trigger_get_en(void);
    int      ds_trigger_set_mode(uint16_t mode);
    int      ds_trigger_set_pos(uint16_t position);
    uint16_t ds_trigger_get_pos(void);
    int      ds_trigger_set_stage(uint16_t stages);
    int      ds_trigger_probe_set(uint16_t probe,
                                  unsigned char trigger0, unsigned char trigger1);
    int      ds_trigger_stage_set_value(uint16_t stage, uint16_t probes,
                                        char *trigger0, char *trigger1);
    int      ds_trigger_stage_set_logic(uint16_t stage, uint16_t probes,
                                        unsigned char trigger_logic);
    int      ds_trigger_stage_set_inv(uint16_t stage, uint16_t probes,
                                      unsigned char trigger0_inv,
                                      unsigned char trigger1_inv);
    int      ds_trigger_stage_set_count(uint16_t stage, uint16_t probes,
                                        uint32_t trigger0_count,
                                        uint32_t trigger1_count);

    /* version / error strings */
    const char *sr_get_lib_version_string(void);
    const char *sr_error_str(int error_code);
    const char *sr_error_name(int error_code);

    /* ---- shim helpers (pyds_*) ---- */

    /* GVariant */
    GVariant *pyds_gvariant_new_uint64(uint64_t val);
    GVariant *pyds_gvariant_new_uint32(uint32_t val);
    GVariant *pyds_gvariant_new_int16(int16_t val);
    GVariant *pyds_gvariant_new_boolean(int val);
    GVariant *pyds_gvariant_new_string(const char *val);
    GVariant *pyds_gvariant_new_double(double val);

    uint64_t    pyds_gvariant_get_uint64(GVariant *v);
    uint32_t    pyds_gvariant_get_uint32(GVariant *v);
    int16_t     pyds_gvariant_get_int16(GVariant *v);
    int         pyds_gvariant_get_boolean(GVariant *v);
    const char *pyds_gvariant_get_string(GVariant *v);
    double      pyds_gvariant_get_double(GVariant *v);

    void pyds_gvariant_unref(GVariant *v);
    void pyds_gvariant_ref_sink(GVariant *v);

    int  pyds_gvariant_tuple_nchildren(GVariant *v);
    uint64_t pyds_gvariant_tuple_get_uint64(GVariant *v, int index);

    /* GSList */
    int   pyds_gslist_length(void *list);
    void *pyds_gslist_nth_data(void *list, int n);

    /* sr_channel accessors */
    int         pyds_channel_get_index(void *ch);
    const char *pyds_channel_get_name(void *ch);
    int         pyds_channel_get_type(void *ch);
    int         pyds_channel_get_enabled(void *ch);
    int         pyds_channel_get_bits(void *ch);
    uint64_t    pyds_channel_get_vdiv(void *ch);
    int         pyds_channel_get_coupling(void *ch);
    uint16_t    pyds_channel_get_offset(void *ch);
    uint64_t    pyds_channel_get_vfactor(void *ch);
    const char *pyds_channel_get_trigger(void *ch);
    uint8_t     pyds_channel_get_trig_value(void *ch);

    /* sr_dev_inst accessors */
    int         pyds_sdi_get_mode(void *sdi_ptr);
    const char *pyds_sdi_get_name(void *sdi_ptr);
    void       *pyds_sdi_get_channels(void *sdi_ptr);
    int         pyds_sdi_get_status(void *sdi_ptr);

    /* memory */
    void pyds_free(void *ptr);
""")

# ---------------------------------------------------------------------------
# Library loading
# ---------------------------------------------------------------------------

_LIB_NAME = "libsigrok4dsl" if sys.platform != "win32" else "sigrok4dsl"


def _find_library() -> str:
    """Locate the shared library, returning the path to dlopen."""
    # 1. Environment variable override
    env_path = os.environ.get("PYDSVIEW_LIB_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. Bundled in _libs/ next to this file
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    libs_dir = os.path.join(pkg_dir, "_libs")
    if sys.platform == "win32":
        candidates = ["sigrok4dsl.dll", "libsigrok4dsl.dll"]
    else:
        candidates = ["libsigrok4dsl.so", "libsigrok4dsl.dylib"]

    for name in candidates:
        p = os.path.join(libs_dir, name)
        if os.path.isfile(p):
            return p

    # 3. DSView build directory (development convenience)
    dsview_build = os.path.join(pkg_dir, "..", "csrc", "build")
    for name in candidates:
        p = os.path.join(dsview_build, name)
        if os.path.isfile(p):
            return p

    # 4. Fall back to system search (just the name, let OS find it)
    return _LIB_NAME


def _load_lib():
    """Load the shared library and return the cffi lib handle."""
    lib_path = _find_library()

    # On Windows, add _libs/ to DLL search path so dependencies are found
    if sys.platform == "win32":
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        libs_dir = os.path.join(pkg_dir, "_libs")
        if os.path.isdir(libs_dir):
            os.add_dll_directory(libs_dir)
            os.environ["PATH"] = libs_dir + os.pathsep + os.environ.get("PATH", "")

    return ffi.dlopen(lib_path)


# Lazy loading: the library is loaded on first access.
# This allows pure-Python modules (_constants, errors, export) to be imported
# without the native library present.
_lib = None


def get_lib():
    """Return the loaded cffi library handle, loading it on first call."""
    global _lib
    if _lib is None:
        _lib = _load_lib()
    return _lib


class _LazyLib:
    """Proxy that loads the native library on first attribute access."""

    def __getattr__(self, name):
        return getattr(get_lib(), name)


lib = _LazyLib()
