# build_windows.ps1 —— 在 Windows 下用 MSYS2 编译 libsigrok4DSL.dll
# 用法：在 PowerShell 里运行：.\build_windows.ps1
# 前提：已安装 MSYS2 到 C:\msys64（脚本会自动装，或手动从 https://msys2.org 安装）
# 产物：pydsview\libsigrok4DSL.dll + 运行时 DLL

$ErrorActionPreference = "Stop"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$SRC = "$SCRIPT_DIR\dsview_src"
$BUILD = "C:\tmp\build_win_sigrok"
$OUT = "$SCRIPT_DIR\pydsview"
$MSYS2 = "C:\msys64"

# 1. 检查 MSYS2
if (-not (Test-Path "$MSYS2\usr\bin\bash.exe")) {
    Write-Host "MSYS2 未找到，正在下载安装..."
    $installer = "$env:TEMP\msys2-installer.exe"
    Invoke-WebRequest -Uri "https://github.com/msys2/msys2-installer/releases/download/2024-01-13/msys2-x86_64-20240113.exe" -OutFile $installer -UseBasicParsing
    Start-Process -FilePath $installer -ArgumentList "install --root $MSYS2 --confirm-command" -Wait
}

# 2. 安装 mingw64 依赖
Write-Host "=== 安装 MSYS2 依赖 ==="
& "$MSYS2\usr\bin\bash.exe" -lc "pacman -Sy --noconfirm mingw-w64-x86_64-gcc mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja mingw-w64-x86_64-glib2 mingw-w64-x86_64-libusb mingw-w64-x86_64-libzip mingw-w64-x86_64-minizip"

# 3. 生成 CMakeLists.txt（用正斜杠路径）
$SRC_POSIX = $SRC -replace '\\', '/'
New-Item -ItemType Directory -Path $BUILD -Force | Out-Null

$cmake_content = @"
cmake_minimum_required(VERSION 3.10)
project(sigrok4DSL C)
find_package(PkgConfig REQUIRED)
pkg_search_module(GLIB REQUIRED glib-2.0)
pkg_search_module(LIBUSB REQUIRED libusb-1.0)
pkg_search_module(LIBZIP REQUIRED libzip)
pkg_search_module(MINIZIP REQUIRED minizip)
include_directories(`${SRC_POSIX}/DSView `${SRC_POSIX}/libsigrok4DSL `${SRC_POSIX}/common)
include_directories(SYSTEM `${GLIB_INCLUDE_DIRS} `${LIBUSB_INCLUDE_DIRS} `${LIBZIP_INCLUDE_DIRS} `${MINIZIP_INCLUDE_DIRS})
add_library(sigrok4DSL SHARED
    `${SRC_POSIX}/libsigrok4DSL/version.c `${SRC_POSIX}/libsigrok4DSL/strutil.c
    `${SRC_POSIX}/libsigrok4DSL/std.c `${SRC_POSIX}/libsigrok4DSL/session_driver.c
    `${SRC_POSIX}/libsigrok4DSL/session.c `${SRC_POSIX}/libsigrok4DSL/log.c
    `${SRC_POSIX}/libsigrok4DSL/hwdriver.c `${SRC_POSIX}/libsigrok4DSL/error.c
    `${SRC_POSIX}/libsigrok4DSL/backend.c `${SRC_POSIX}/libsigrok4DSL/output/output.c
    `${SRC_POSIX}/libsigrok4DSL/input/input.c `${SRC_POSIX}/libsigrok4DSL/hardware/demo/demo.c
    `${SRC_POSIX}/libsigrok4DSL/input/in_binary.c `${SRC_POSIX}/libsigrok4DSL/input/in_vcd.c
    `${SRC_POSIX}/libsigrok4DSL/input/in_wav.c `${SRC_POSIX}/libsigrok4DSL/output/csv.c
    `${SRC_POSIX}/libsigrok4DSL/output/gnuplot.c `${SRC_POSIX}/libsigrok4DSL/output/srzip.c
    `${SRC_POSIX}/libsigrok4DSL/output/vcd.c `${SRC_POSIX}/libsigrok4DSL/hardware/DSL/dslogic.c
    `${SRC_POSIX}/libsigrok4DSL/hardware/common/usb.c `${SRC_POSIX}/libsigrok4DSL/hardware/common/ezusb.c
    `${SRC_POSIX}/libsigrok4DSL/trigger.c `${SRC_POSIX}/libsigrok4DSL/dsdevice.c
    `${SRC_POSIX}/libsigrok4DSL/hardware/DSL/dscope.c `${SRC_POSIX}/libsigrok4DSL/hardware/DSL/command.c
    `${SRC_POSIX}/libsigrok4DSL/hardware/DSL/dsl.c `${SRC_POSIX}/libsigrok4DSL/lib_main.c
    `${SRC_POSIX}/common/log/xlog.c
)
target_link_libraries(sigrok4DSL `${GLIB_LIBRARIES} `${LIBUSB_LIBRARIES} `${LIBZIP_LIBRARIES} `${MINIZIP_LIBRARIES})
"@
# 替换反引号转义的占位符
$cmake_content = $cmake_content -replace '`\$', '$'
Set-Content "$BUILD\CMakeLists.txt" $cmake_content

# 4. 编译
Write-Host "=== 编译 ==="
$BUILD_MSYS = $BUILD -replace 'C:\\', '/c/' -replace '\\', '/'
& "$MSYS2\msys2_shell.cmd" -mingw64 -defterm -no-start -c "cd '$BUILD_MSYS' && cmake . -G Ninja -DCMAKE_BUILD_TYPE=Release && ninja -j4"

# 5. 复制产物
Write-Host "=== 复制 DLL ==="
Copy-Item "$BUILD\libsigrok4DSL.dll" $OUT
$runtime_dlls = @("libwinpthread-1.dll","libglib-2.0-0.dll","libusb-1.0.dll","libminizip-1.dll","zlib1.dll","libbz2-1.dll","libintl-8.dll","libiconv-2.dll","libpcre2-8-0.dll")
foreach ($dll in $runtime_dlls) {
    Copy-Item "$MSYS2\mingw64\bin\$dll" $OUT -ErrorAction SilentlyContinue
}
Write-Host "完成：$OUT\libsigrok4DSL.dll"
