/**
 * shim.c — GVariant / GSList / sr_channel accessors for pydsview.
 *
 * Python (via cffi) should never touch GLib types directly. This shim
 * provides typed helper functions so the binding layer only deals with
 * plain C scalars and opaque pointers.
 */

#include <glib.h>
#include <stdlib.h>
#include <string.h>
#include "libsigrok.h"
#include "libsigrok-internal.h"

/* On Windows the export macro is set by CMake; on other platforms fall back. */
#ifndef PYDS_API
#  ifdef _WIN32
#    define PYDS_API __declspec(dllexport)
#  else
#    define PYDS_API __attribute__((visibility("default")))
#  endif
#endif

/* ------------------------------------------------------------------ */
/*  GVariant helpers                                                   */
/* ------------------------------------------------------------------ */

PYDS_API GVariant *pyds_gvariant_new_uint64(uint64_t val)
{
    return g_variant_new_uint64(val);
}

PYDS_API GVariant *pyds_gvariant_new_uint32(uint32_t val)
{
    return g_variant_new_uint32(val);
}

PYDS_API GVariant *pyds_gvariant_new_int16(int16_t val)
{
    return g_variant_new_int16(val);
}

PYDS_API GVariant *pyds_gvariant_new_boolean(int val)
{
    return g_variant_new_boolean(val ? TRUE : FALSE);
}

PYDS_API GVariant *pyds_gvariant_new_string(const char *val)
{
    return g_variant_new_string(val ? val : "");
}

PYDS_API GVariant *pyds_gvariant_new_double(double val)
{
    return g_variant_new_double(val);
}

PYDS_API uint64_t pyds_gvariant_get_uint64(GVariant *v)
{
    if (!v) return 0;
    return g_variant_get_uint64(v);
}

PYDS_API uint32_t pyds_gvariant_get_uint32(GVariant *v)
{
    if (!v) return 0;
    return g_variant_get_uint32(v);
}

PYDS_API int16_t pyds_gvariant_get_int16(GVariant *v)
{
    if (!v) return 0;
    return g_variant_get_int16(v);
}

PYDS_API int pyds_gvariant_get_boolean(GVariant *v)
{
    if (!v) return 0;
    return g_variant_get_boolean(v) ? 1 : 0;
}

PYDS_API const char *pyds_gvariant_get_string(GVariant *v)
{
    if (!v) return "";
    return g_variant_get_string(v, NULL);
}

PYDS_API double pyds_gvariant_get_double(GVariant *v)
{
    if (!v) return 0.0;
    return g_variant_get_double(v);
}

PYDS_API void pyds_gvariant_unref(GVariant *v)
{
    if (v) g_variant_unref(v);
}

PYDS_API void pyds_gvariant_ref_sink(GVariant *v)
{
    if (v) g_variant_ref_sink(v);
}

/* ------------------------------------------------------------------ */
/*  GSList traversal helpers                                           */
/* ------------------------------------------------------------------ */

PYDS_API int pyds_gslist_length(GSList *list)
{
    return (int)g_slist_length(list);
}

PYDS_API void *pyds_gslist_nth_data(GSList *list, int n)
{
    return g_slist_nth_data(list, (guint)n);
}

/* ------------------------------------------------------------------ */
/*  sr_channel field accessors                                         */
/* ------------------------------------------------------------------ */

PYDS_API int pyds_channel_get_index(void *ch)
{
    if (!ch) return -1;
    return ((struct sr_channel *)ch)->index;
}

PYDS_API const char *pyds_channel_get_name(void *ch)
{
    if (!ch) return "";
    const char *name = ((struct sr_channel *)ch)->name;
    return name ? name : "";
}

PYDS_API int pyds_channel_get_type(void *ch)
{
    if (!ch) return -1;
    return ((struct sr_channel *)ch)->type;
}

PYDS_API int pyds_channel_get_enabled(void *ch)
{
    if (!ch) return 0;
    return ((struct sr_channel *)ch)->enabled ? 1 : 0;
}

PYDS_API int pyds_channel_get_bits(void *ch)
{
    if (!ch) return 0;
    return ((struct sr_channel *)ch)->bits;
}

PYDS_API uint64_t pyds_channel_get_vdiv(void *ch)
{
    if (!ch) return 0;
    return ((struct sr_channel *)ch)->vdiv;
}

PYDS_API int pyds_channel_get_coupling(void *ch)
{
    if (!ch) return 0;
    return ((struct sr_channel *)ch)->coupling;
}

PYDS_API uint16_t pyds_channel_get_offset(void *ch)
{
    if (!ch) return 0;
    return ((struct sr_channel *)ch)->offset;
}

PYDS_API uint64_t pyds_channel_get_vfactor(void *ch)
{
    if (!ch) return 0;
    return ((struct sr_channel *)ch)->vfactor;
}

PYDS_API const char *pyds_channel_get_trigger(void *ch)
{
    if (!ch) return "";
    const char *t = ((struct sr_channel *)ch)->trigger;
    return t ? t : "";
}

PYDS_API uint8_t pyds_channel_get_trig_value(void *ch)
{
    if (!ch) return 0;
    return ((struct sr_channel *)ch)->trig_value;
}

/* ------------------------------------------------------------------ */
/*  sr_dev_inst field accessors                                        */
/* ------------------------------------------------------------------ */

PYDS_API int pyds_sdi_get_mode(void *sdi_ptr)
{
    if (!sdi_ptr) return -1;
    return ((struct sr_dev_inst *)sdi_ptr)->mode;
}

PYDS_API const char *pyds_sdi_get_name(void *sdi_ptr)
{
    if (!sdi_ptr) return "";
    const char *n = ((struct sr_dev_inst *)sdi_ptr)->name;
    return n ? n : "";
}

PYDS_API void *pyds_sdi_get_channels(void *sdi_ptr)
{
    if (!sdi_ptr) return NULL;
    return ((struct sr_dev_inst *)sdi_ptr)->channels;
}

PYDS_API int pyds_sdi_get_status(void *sdi_ptr)
{
    if (!sdi_ptr) return -1;
    return ((struct sr_dev_inst *)sdi_ptr)->status;
}

/* ------------------------------------------------------------------ */
/*  Memory helpers                                                     */
/* ------------------------------------------------------------------ */

PYDS_API void pyds_free(void *ptr)
{
    if (ptr) g_free(ptr);
}

/* ------------------------------------------------------------------ */
/*  GVariant list extraction (for config_list results)                 */
/* ------------------------------------------------------------------ */

PYDS_API int pyds_gvariant_tuple_nchildren(GVariant *v)
{
    if (!v) return 0;
    return (int)g_variant_n_children(v);
}

PYDS_API uint64_t pyds_gvariant_tuple_get_uint64(GVariant *v, int index)
{
    if (!v) return 0;
    GVariant *child = g_variant_get_child_value(v, (gsize)index);
    uint64_t val = g_variant_get_uint64(child);
    g_variant_unref(child);
    return val;
}
