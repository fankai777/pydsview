# pydsview

[![PyPI version](https://img.shields.io/pypi/v/pydsview)](https://pypi.org/project/pydsview/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

[English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

Python bindings for [DSView](https://github.com/DreamSourceLab/DSView)'s `libsigrok4DSL` — control DreamSourceLab logic analyzers and oscilloscopes (DSLogic, DSCope) from Python.

### Installation

```bash
pip install pydsview
```

### Features

- Discover and activate DSLogic/DSCope/Demo devices
- Configure samplerate, sample count, channels, triggers
- Synchronous and asynchronous capture
- NumPy array output
- Export to CSV (with compressed mode), VCD, and DSView session (`.dsl`) format
- Prebuilt Windows DLLs and firmware included — plug and play
- Optional Model Context Protocol (MCP) server for local agent-controlled
  discovery, bounded capture, export, and profile workflows

### Architecture

```
Python user code
    └── pydsview (Python package)
            ├── DSContext  — library lifecycle, device list
            ├── Device     — config, channels, capture
            ├── Capture    — sync/async data collection
            ├── Trigger    — trigger configuration
            └── Exporter   — CSV / VCD / session export
                    └── _binding.py (cffi ABI-mode)
                            └── libsigrok4dsl.dll/.so + shim.c
                                    └── libusb / glib / zlib
```

### Quick Start (Windows)

Prebuilt DLLs and firmware are bundled. Just install and use:

```bash
pip install pydsview
```

For development:

```bash
git clone https://github.com/fankai777/pydsview.git
cd pydsview
pip install -e ".[dev]"
```

```python
import pydsview

with pydsview.DSContext() as ctx:
    for info in ctx.list_devices():
        print(info.name, info.handle)

    dev = ctx.get_device(1)                        # DSLogic Plus
    dev.set_config(pydsview.Config.OPERATION_MODE, 1)  # stream mode
    dev.set_config(pydsview.Config.VTH, 1.0)           # threshold 1.0V
    dev.samplerate = pydsview.SR_MHZ(1)
    dev.sample_count = 1_000_000

    result = dev.capture(timeout=10.0)

    # NumPy data
    data = result.to_numpy()
    ch0 = result.channel_data(0)   # bool array

    # Export (compressed CSV — only writes rows where values change)
    pydsview.export.Exporter.to_csv(result, "data.csv")
    pydsview.export.Exporter.to_vcd(result, "data.vcd")
```

### Building from Source (Linux / rebuild DLL)

If you need to rebuild the native library:

```bash
cd pydsview/csrc
mkdir build && cd build
cmake .. -G "MinGW Makefiles"   # Windows (MSYS2 mingw64)
# cmake .. -G "Unix Makefiles"  # Linux
cmake --build .
cmake --install .               # copies DLL/SO into pydsview/_libs/
```

Build dependencies (same as DSView):
- glib-2.0 (via pkg-config)
- libusb-1.0
- zlib
- pthreads

### API Reference

#### `DSContext(firmware_dir=None, user_data_dir=None)`

Initialize the library. Use as a context manager. Firmware is bundled in `pydsview/res/` and loaded automatically.

- `list_devices()` → `list[DeviceInfo]`
- `get_device(index)` → `Device`
- `load_session_file(path)` → `Device`
- `lib_version` → `str`

#### `Device`

Wraps the currently active device.

- `name`, `mode`, `device_type`, `channels`
- `samplerate` (get/set), `sample_count` (get/set)
- `get_config(key)`, `set_config(key, value)`
- `enable_channel(index, enabled)`, `set_channel_name(index, name)`
- `capture(timeout=None)` → `CaptureResult` (synchronous)
- `start_capture()` → `CaptureSession` (asynchronous)

#### `CaptureResult`

- `to_numpy()` → `np.ndarray`
- `to_channel_arrays()` → `list[np.ndarray]` (per-channel bool arrays)
- `channel_data(index)` → `np.ndarray` (bool, logic only)
- `dso_data()` → `np.ndarray`
- `analog_data()` → `np.ndarray`

#### `TriggerConfig`

- `reset()`, `set_enabled(bool)`, `set_mode(TriggerMode)`
- `set_position(percent)`, `set_channel_trigger(ch, spec)`

#### `Exporter`

- `Exporter.to_csv(result, path, channels=None, time_column=True, compressed=True)`
- `Exporter.to_vcd(result, path, channels=None, timescale="1ns")`
- `Exporter.save_session(result, path)`

### MCP Server

Install the optional MCP dependency:

```bash
pip install "pydsview[mcp]"
```

Run the local stdio server:

```bash
pydsview-mcp --artifact-dir ./captures --max-samples 10000000 --max-duration-ms 10000
```

Example MCP client configuration:

```json
{
  "mcpServers": {
    "pydsview": {
      "command": "pydsview-mcp",
      "args": ["--artifact-dir", "./captures"]
    }
  }
}
```

Available tools:

- `get_library_status`
- `list_devices`
- `get_device_info`
- `configure_device`
- `capture`
- `start_capture`
- `capture_status`
- `stop_capture`
- `export_capture`
- `load_session_file`
- `set_trigger`
- `save_capture_profile`
- `list_capture_profiles`
- `delete_capture_profile`
- `capture_with_profile`

Safety defaults:

- Captures must be bounded by sample count or duration.
- Output artifacts are restricted to the configured artifact directory.
- Existing files are not overwritten unless overwrite is explicitly enabled.
- One capture may run at a time in each server process.
- Each exported capture writes a JSON sidecar with device, library, capture,
  and timing metadata.

Environment variables:

- `PYDSVIEW_MCP_ARTIFACT_DIR`
- `PYDSVIEW_MCP_MAX_SAMPLES`
- `PYDSVIEW_MCP_MAX_DURATION_MS`
- `PYDSVIEW_MCP_ALLOW_OVERWRITE`
- `PYDSVIEW_MCP_DEFAULT_TIMEOUT_S`

### Windows Source Patches

To build `libsigrok4DSL` on Windows (without the Qt GUI event loop), two files in `DSView/libsigrok4DSL/hardware/DSL/` require patching:

#### `dslogic.c`

1. **Dummy source polling** — `libusb_get_pollfds()` returns FDs that Windows `g_poll()` cannot monitor. Three `#ifdef _WIN32` blocks replace real FD polling with a dummy source (`fd=-1, timeout=10ms`) so `receive_data()` is called via the freewheel/timeout path in `sr_session_run()`:
   - `hw_dev_acquisition_start()`: use `sr_source_add(-1, 0, 10, ...)` instead of iterating `libusb_get_pollfds()`
   - `remove_sources()`: remove the single dummy fd instead of iterating `devc->usbfd[]`
   - `receive_data()`: set `libusb_handle_events_timeout` to 10ms (instead of 0) to drive Windows overlapped I/O

2. **Extra `libusb_unref_device`** — Windows needs an additional `libusb_unref_device()` call after firmware upload to properly release the device handle before reconnect.

#### `dsl.c`

3. **`logic.unitsize` assignment** — In `receive_transfer()`, added `logic.unitsize = (dsl_en_ch_num(sdi) + 7) / 8;` so the `SR_DF_LOGIC` packet carries the correct unit size for downstream data decoding.

### Running Tests

```bash
pip install -e ".[dev,mcp]"
pytest tests/
```

`test_export.py` works without hardware. `test_context.py`, `test_device.py`, and `test_capture.py` require the compiled library and use the Demo device.
`test_mcp_tools.py` uses fake devices and does not require analyzer hardware.

### License

GPL-3.0-or-later (same as DSView). Bundled firmware files are from [DreamSourceLab/DSView](https://github.com/DreamSourceLab/DSView) under the same license.

---

<a id="中文"></a>

## 中文

[DSView](https://github.com/DreamSourceLab/DSView) `libsigrok4DSL` 的 Python 绑定 — 用 Python 控制 DreamSourceLab 逻辑分析仪和示波器（DSLogic、DSCope），无需 Qt GUI。

### 安装

```bash
pip install pydsview
```

### 功能

- 发现并激活 DSLogic/DSCope/Demo 设备
- 配置采样率、采样数、通道、触发器
- 同步和异步采集
- NumPy 数组输出
- 导出 CSV（支持压缩模式）、VCD 和 DSView 会话文件（`.dsl`）
- 预编译 Windows DLL 和固件已内置 — 即装即用

### 架构

```
Python 用户代码
    └── pydsview (Python 包)
            ├── DSContext  — 库生命周期、设备列表
            ├── Device     — 配置、通道、采集
            ├── Capture    — 同步/异步数据采集
            ├── Trigger    — 触发器配置
            └── Exporter   — CSV / VCD / 会话导出
                    └── _binding.py (cffi ABI 模式)
                            └── libsigrok4dsl.dll/.so + shim.c
                                    └── libusb / glib / zlib
```

### 快速开始（Windows）

预编译 DLL 和固件已打包，直接安装即可使用：

```bash
pip install pydsview
```

开发模式：

```bash
git clone https://github.com/fankai777/pydsview.git
cd pydsview
pip install -e ".[dev]"
```

```python
import pydsview

with pydsview.DSContext() as ctx:
    for info in ctx.list_devices():
        print(info.name, info.handle)

    dev = ctx.get_device(1)                            # DSLogic Plus
    dev.set_config(pydsview.Config.OPERATION_MODE, 1)  # 流模式
    dev.set_config(pydsview.Config.VTH, 1.0)           # 阈值电压 1.0V
    dev.samplerate = pydsview.SR_MHZ(1)
    dev.sample_count = 1_000_000

    result = dev.capture(timeout=10.0)

    # NumPy 数据
    data = result.to_numpy()
    ch0 = result.channel_data(0)   # bool 数组

    # 导出（压缩 CSV — 仅在信号变化时写入行）
    pydsview.export.Exporter.to_csv(result, "data.csv")
    pydsview.export.Exporter.to_vcd(result, "data.vcd")
```

### 从源码编译（Linux / 重新编译 DLL）

如需重新编译原生库：

```bash
cd pydsview/csrc
mkdir build && cd build
cmake .. -G "MinGW Makefiles"   # Windows (MSYS2 mingw64)
# cmake .. -G "Unix Makefiles"  # Linux
cmake --build .
cmake --install .               # 将 DLL/SO 复制到 pydsview/_libs/
```

编译依赖（与 DSView 相同）：
- glib-2.0（通过 pkg-config）
- libusb-1.0
- zlib
- pthreads

### API 参考

#### `DSContext(firmware_dir=None, user_data_dir=None)`

初始化库，作为上下文管理器使用。固件已打包在 `pydsview/res/` 中，自动加载。

- `list_devices()` → `list[DeviceInfo]`
- `get_device(index)` → `Device`
- `load_session_file(path)` → `Device`
- `lib_version` → `str`

#### `Device`

封装当前激活的设备。

- `name`、`mode`、`device_type`、`channels`
- `samplerate`（读/写）、`sample_count`（读/写）
- `get_config(key)`、`set_config(key, value)`
- `enable_channel(index, enabled)`、`set_channel_name(index, name)`
- `capture(timeout=None)` → `CaptureResult`（同步采集）
- `start_capture()` → `CaptureSession`（异步采集）

#### `CaptureResult`

- `to_numpy()` → `np.ndarray`
- `to_channel_arrays()` → `list[np.ndarray]`（逐通道 bool 数组）
- `channel_data(index)` → `np.ndarray`（bool，仅逻辑模式）
- `dso_data()` → `np.ndarray`
- `analog_data()` → `np.ndarray`

#### `TriggerConfig`

- `reset()`、`set_enabled(bool)`、`set_mode(TriggerMode)`
- `set_position(percent)`、`set_channel_trigger(ch, spec)`

#### `Exporter`

- `Exporter.to_csv(result, path, channels=None, time_column=True, compressed=True)`
- `Exporter.to_vcd(result, path, channels=None, timescale="1ns")`
- `Exporter.save_session(result, path)`

### Windows 源码补丁

在 Windows 上编译 `libsigrok4DSL`（不依赖 Qt GUI 事件循环）需要修改 `DSView/libsigrok4DSL/hardware/DSL/` 下的两个文件：

#### `dslogic.c`

1. **虚拟源轮询** — Windows 上 `libusb_get_pollfds()` 返回的 FD 无法被 `g_poll()` 监听。通过三处 `#ifdef _WIN32` 替换为虚拟源（`fd=-1, timeout=10ms`），使 `receive_data()` 通过 `sr_session_run()` 的超时路径被调用：
   - `hw_dev_acquisition_start()`：使用 `sr_source_add(-1, 0, 10, ...)` 替代遍历 `libusb_get_pollfds()`
   - `remove_sources()`：移除单个虚拟 fd 替代遍历 `devc->usbfd[]`
   - `receive_data()`：`libusb_handle_events_timeout` 设为 10ms（而非 0）以驱动 Windows overlapped I/O

2. **额外的 `libusb_unref_device`** — Windows 需要在固件上传后额外调用一次 `libusb_unref_device()` 以正确释放设备句柄。

#### `dsl.c`

3. **`logic.unitsize` 赋值** — 在 `receive_transfer()` 中添加 `logic.unitsize = (dsl_en_ch_num(sdi) + 7) / 8;`，使 `SR_DF_LOGIC` 数据包携带正确的单位大小，供下游数据解码使用。

### 运行测试

```bash
pytest tests/
```

`test_export.py` 无需硬件即可运行。`test_context.py`、`test_device.py`、`test_capture.py` 需要编译好的库并使用 Demo 设备。

### 许可证

GPL-3.0-or-later（与 DSView 一致）。内置的固件文件来自 [DreamSourceLab/DSView](https://github.com/DreamSourceLab/DSView)，采用相同许可证。
