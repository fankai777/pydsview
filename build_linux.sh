#!/usr/bin/env bash
# build_linux.sh —— 在 WSL2/Linux 下编译 libsigrok4DSL.so
# 用法：bash build_linux.sh
# 产物：pydsview/libsigrok4DSL.so

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/dsview_src"
BUILD="/tmp/build_libsigrok4dsl_linux"
OUT="$SCRIPT_DIR/pydsview/libsigrok4DSL.so"

echo "=== 检查依赖 ==="
if ! command -v cmake &>/dev/null; then
    echo "安装依赖..."
    sudo apt-get install -y cmake libglib2.0-dev libusb-1.0-0-dev libzip-dev libminizip-dev
fi

echo "=== 生成 CMakeLists ==="
mkdir -p "$BUILD"
python3 - <<PYEOF
src = "$SRC"
content = f"""cmake_minimum_required(VERSION 3.10)
project(sigrok4DSL C)
find_package(PkgConfig REQUIRED)
pkg_search_module(GLIB REQUIRED glib-2.0)
pkg_search_module(LIBUSB REQUIRED libusb-1.0)
pkg_search_module(LIBZIP REQUIRED libzip)
pkg_search_module(MINIZIP REQUIRED minizip)
include_directories({src}/DSView {src}/libsigrok4DSL {src}/common)
include_directories(SYSTEM \${{GLIB_INCLUDE_DIRS}} \${{LIBUSB_INCLUDE_DIRS}} \${{LIBZIP_INCLUDE_DIRS}} \${{MINIZIP_INCLUDE_DIRS}})
add_library(sigrok4DSL SHARED
    {src}/libsigrok4DSL/version.c {src}/libsigrok4DSL/strutil.c
    {src}/libsigrok4DSL/std.c {src}/libsigrok4DSL/session_driver.c
    {src}/libsigrok4DSL/session.c {src}/libsigrok4DSL/log.c
    {src}/libsigrok4DSL/hwdriver.c {src}/libsigrok4DSL/error.c
    {src}/libsigrok4DSL/backend.c {src}/libsigrok4DSL/output/output.c
    {src}/libsigrok4DSL/input/input.c {src}/libsigrok4DSL/hardware/demo/demo.c
    {src}/libsigrok4DSL/input/in_binary.c {src}/libsigrok4DSL/input/in_vcd.c
    {src}/libsigrok4DSL/input/in_wav.c {src}/libsigrok4DSL/output/csv.c
    {src}/libsigrok4DSL/output/gnuplot.c {src}/libsigrok4DSL/output/srzip.c
    {src}/libsigrok4DSL/output/vcd.c {src}/libsigrok4DSL/hardware/DSL/dslogic.c
    {src}/libsigrok4DSL/hardware/common/usb.c {src}/libsigrok4DSL/hardware/common/ezusb.c
    {src}/libsigrok4DSL/trigger.c {src}/libsigrok4DSL/dsdevice.c
    {src}/libsigrok4DSL/hardware/DSL/dscope.c {src}/libsigrok4DSL/hardware/DSL/command.c
    {src}/libsigrok4DSL/hardware/DSL/dsl.c {src}/libsigrok4DSL/lib_main.c
    {src}/common/log/xlog.c
)
target_link_libraries(sigrok4DSL \${{GLIB_LIBRARIES}} \${{LIBUSB_LIBRARIES}} \${{LIBZIP_LIBRARIES}} \${{MINIZIP_LIBRARIES}})
"""
with open("$BUILD/CMakeLists.txt", "w") as f:
    f.write(content)
PYEOF

echo "=== 编译 ==="
cd "$BUILD"
cmake . -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

echo "=== 复制到 pydsview/ ==="
cp "$BUILD/libsigrok4DSL.so" "$OUT"
echo "完成：$OUT"
