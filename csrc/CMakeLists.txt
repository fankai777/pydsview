##
## CMakeLists.txt — Build libsigrok4dsl as a standalone shared library for pydsview
##
## Usage:
##   mkdir build && cd build
##   cmake .. -G "MinGW Makefiles"    # or "Unix Makefiles" on Linux
##   cmake --build .
##
## Prerequisites (same as DSView):
##   - glib-2.0 (pkg-config)
##   - libusb-1.0
##   - zlib
##   - pthreads
##

cmake_minimum_required(VERSION 3.10)
project(pydsview_native C)

set(CMAKE_C_STANDARD 99)

# Root of DSView source tree (one level up)
set(DSVIEW_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../DSView")

# ---- Dependencies ----
find_package(PkgConfig REQUIRED)
pkg_check_modules(GLIB2 REQUIRED glib-2.0)
find_package(Threads REQUIRED)

# libusb-1.0
list(APPEND CMAKE_MODULE_PATH "${DSVIEW_ROOT}/cmake")
find_package(libusb-1.0 REQUIRED)

find_package(ZLIB REQUIRED)

# ---- Include paths ----
include_directories(
    ${DSVIEW_ROOT}
    ${DSVIEW_ROOT}/libsigrok4DSL
    ${DSVIEW_ROOT}/common
    ${DSVIEW_ROOT}/common/minizip
    ${DSVIEW_ROOT}/common/log
    ${GLIB2_INCLUDE_DIRS}
    ${LIBUSB_1_INCLUDE_DIRS}
    ${ZLIB_INCLUDE_DIRS}
)

link_directories(${GLIB2_LIBRARY_DIRS})

# ---- Source files (from DSView/CMakeLists.txt) ----
set(LIBSIGROK_SOURCES
    ${DSVIEW_ROOT}/libsigrok4DSL/version.c
    ${DSVIEW_ROOT}/libsigrok4DSL/strutil.c
    ${DSVIEW_ROOT}/libsigrok4DSL/std.c
    ${DSVIEW_ROOT}/libsigrok4DSL/session_driver.c
    ${DSVIEW_ROOT}/libsigrok4DSL/session.c
    ${DSVIEW_ROOT}/libsigrok4DSL/log.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hwdriver.c
    ${DSVIEW_ROOT}/libsigrok4DSL/error.c
    ${DSVIEW_ROOT}/libsigrok4DSL/backend.c
    ${DSVIEW_ROOT}/libsigrok4DSL/output/output.c
    ${DSVIEW_ROOT}/libsigrok4DSL/input/input.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hardware/demo/demo.c
    ${DSVIEW_ROOT}/libsigrok4DSL/input/in_binary.c
    ${DSVIEW_ROOT}/libsigrok4DSL/input/in_vcd.c
    ${DSVIEW_ROOT}/libsigrok4DSL/input/in_wav.c
    ${DSVIEW_ROOT}/libsigrok4DSL/output/csv.c
    ${DSVIEW_ROOT}/libsigrok4DSL/output/gnuplot.c
    ${DSVIEW_ROOT}/libsigrok4DSL/output/srzip.c
    ${DSVIEW_ROOT}/libsigrok4DSL/output/vcd.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hardware/DSL/dslogic.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hardware/common/usb.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hardware/common/ezusb.c
    ${DSVIEW_ROOT}/libsigrok4DSL/trigger.c
    ${DSVIEW_ROOT}/libsigrok4DSL/dsdevice.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hardware/DSL/dscope.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hardware/DSL/command.c
    ${DSVIEW_ROOT}/libsigrok4DSL/hardware/DSL/dsl.c
    ${DSVIEW_ROOT}/libsigrok4DSL/lib_main.c
)

set(COMMON_SOURCES
    ${DSVIEW_ROOT}/common/minizip/zip.c
    ${DSVIEW_ROOT}/common/minizip/unzip.c
    ${DSVIEW_ROOT}/common/minizip/ioapi.c
    ${DSVIEW_ROOT}/common/log/xlog.c
)

# ---- Shim (GVariant/GSList helpers for Python) ----
set(SHIM_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/shim.c
)

# ---- Build shared library ----
add_library(sigrok4dsl SHARED
    ${LIBSIGROK_SOURCES}
    ${COMMON_SOURCES}
    ${SHIM_SOURCES}
)

# On Windows, export all ds_* / pyds_* / sr_* symbols.
# The header redefines SR_API to empty, so we use the linker flag instead.
if(WIN32)
    target_compile_definitions(sigrok4dsl PRIVATE
        SR_PRIV=
        PYDS_API=__declspec\(dllexport\)
    )
    target_link_options(sigrok4dsl PRIVATE -Wl,--export-all-symbols)
else()
    target_compile_definitions(sigrok4dsl PRIVATE
        PYDS_API=__attribute__\(\(visibility\("default"\)\)\)
    )
endif()

# Common defines matching DSView's config.h expectations
target_compile_definitions(sigrok4dsl PRIVATE
    HAVE_LIBUSB_1_0=1
    HAVE_LA_DEMO=1
    HAVE_DSL_DEVICE=1
)

target_compile_options(sigrok4dsl PRIVATE -Wall -Wextra -Wno-unused-parameter -O2)

target_link_libraries(sigrok4dsl
    ${GLIB2_LIBRARIES}
    ${LIBUSB_1_LIBRARIES}
    ${ZLIB_LIBRARIES}
    ${CMAKE_THREAD_LIBS_INIT}
)

# Install the shared library next to the Python package
install(TARGETS sigrok4dsl
    RUNTIME DESTINATION "${CMAKE_CURRENT_SOURCE_DIR}/../pydsview/_libs"
    LIBRARY DESTINATION "${CMAKE_CURRENT_SOURCE_DIR}/../pydsview/_libs"
)
