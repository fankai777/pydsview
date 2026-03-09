# 预编译二进制说明

`pydsview/` 目录下包含预编译的二进制文件，用户无需自行编译即可使用。

## libsigrok4DSL

| 文件 | 平台 | 编译时间 | 来源版本 |
|------|------|---------|---------|
| `libsigrok4DSL.so` | Linux x86_64 | 2026-03-09 | DreamSourceLab/DSView master |
| `libsigrok4DSL.dll` | Windows x86_64 | 2026-03-09 | DreamSourceLab/DSView master |

**来源仓库：** https://github.com/DreamSourceLab/DSView

**编译环境：**
- Linux：WSL2 Ubuntu 24.04，gcc，cmake
- Windows：MSYS2 mingw64，gcc 15.2.0，cmake，ninja

**编译脚本：** 见 `build_linux.sh` 和 `build_windows.ps1`

## Windows 运行时依赖 DLL

以下 DLL 来自 MSYS2 mingw64，与 `libsigrok4DSL.dll` 一同打包：

| 文件 | 版本来源 |
|------|---------|
| `libwinpthread-1.dll` | mingw-w64 runtime |
| `libglib-2.0-0.dll` | GLib 2.x |
| `libusb-1.0.dll` | libusb 1.x |
| `libminizip-1.dll` | minizip |
| `zlib1.dll` | zlib |
| `libbz2-1.dll` | bzip2 |
| `libintl-8.dll` | gettext |
| `libiconv-2.dll` | libiconv |
| `libpcre2-8-0.dll` | PCRE2 |

## 更新二进制

DSView 上游更新时，重新编译并替换：

```bash
# Linux
bash build_linux.sh

# Windows（PowerShell）
.\build_windows.ps1
```

替换后 commit 并更新此文件的编译时间。
