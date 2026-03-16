# pydsview

Python bindings for [DSView](https://github.com/DreamSourceLab/DSView)'s `libsigrok4DSL` — control DreamSourceLab logic analyzers and oscilloscopes (DSLogic, DSCope) from Python.

## Features

- Discover and activate DSLogic/DSCope/Demo devices
- Configure samplerate, sample count, channels, triggers
- Synchronous and asynchronous capture
- NumPy array output
- Export to CSV, VCD, and DSView session (`.dsl`) format
- Pure-Python export layer — no extra native dependencies

## Architecture

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

## Prerequisites

1. **Build the native library** (one-time):

```bash
cd pydsview/csrc
mkdir build && cd build
cmake .. -G "MinGW Makefiles"   # Windows with MinGW
# cmake .. -G "Unix Makefiles"  # Linux
cmake --build .
cmake --install .               # copies DLL/SO into pydsview/_libs/
```

Dependencies (same as building DSView):
- glib-2.0 (via pkg-config)
- libusb-1.0
- zlib
- pthreads

2. **Install the Python package**:

```bash
cd pydsview
pip install -e ".[dev]"
```

## Quick Start

```python
import pydsview

with pydsview.DSContext() as ctx:
    # List devices
    for info in ctx.list_devices():
        print(info.name, info.handle)

    # Activate Demo device
    dev = ctx.get_device(0)

    # Configure
    dev.samplerate = 1_000_000   # 1 MHz
    dev.sample_count = 10_000

    # Capture
    result = dev.capture(timeout=5.0)

    # NumPy data
    data = result.to_numpy()
    ch0 = result.channel_data(0)   # bool array

    # Export
    pydsview.export.Exporter.to_csv(result, "data.csv")
    pydsview.export.Exporter.to_vcd(result, "data.vcd")
```

## API Reference

### `DSContext(firmware_dir=None, user_data_dir=None)`

Initialize the library. Use as a context manager. Firmware files are bundled in `pydsview/res/` and loaded automatically — no need to specify `firmware_dir` unless you want to override.

- `list_devices()` → `list[DeviceInfo]`
- `get_device(index)` → `Device`
- `load_session_file(path)` → `Device`
- `lib_version` → `str`

### `Device`

Wraps the currently active device.

- `name`, `mode`, `device_type`, `channels`
- `samplerate` (get/set), `sample_count` (get/set)
- `get_config(key)`, `set_config(key, value)`
- `enable_channel(index, enabled)`, `set_channel_name(index, name)`
- `capture(timeout=None)` → `CaptureResult` (synchronous)
- `start_capture()` → `CaptureSession` (asynchronous)

### `CaptureResult`

- `to_numpy()` → `np.ndarray`
- `channel_data(index)` → `np.ndarray` (bool, logic only)
- `dso_data()` → `np.ndarray`
- `analog_data()` → `np.ndarray`

### `TriggerConfig`

- `reset()`, `set_enabled(bool)`, `set_mode(TriggerMode)`
- `set_position(percent)`, `set_channel_trigger(ch, spec)`

### `Exporter`

- `Exporter.to_csv(result, path, channels=None, time_column=True, compressed=True)`
- `Exporter.to_vcd(result, path, channels=None, timescale="1ns")`
- `Exporter.save_session(result, path)`

## Windows Source Patches

To make `libsigrok4DSL` work on Windows (without the Qt GUI event loop), two files in `DSView/libsigrok4DSL/hardware/DSL/` require patching before building:

### `dslogic.c`

1. **Dummy source polling** — `libusb_get_pollfds()` returns FDs that Windows `g_poll()` cannot monitor. Three `#ifdef _WIN32` blocks replace the real FD polling with a single dummy source (`fd=-1, timeout=10ms`) so that `receive_data()` is called via the freewheel/timeout path in `sr_session_run()`:
   - `hw_dev_acquisition_start()`: use `sr_source_add(-1, 0, 10, ...)` instead of iterating `libusb_get_pollfds()`
   - `remove_sources()`: remove the single dummy fd instead of iterating `devc->usbfd[]`
   - `receive_data()`: set `libusb_handle_events_timeout` to 10ms (instead of 0) to drive Windows overlapped I/O

2. **Extra `libusb_unref_device`** — Windows needs an additional `libusb_unref_device()` call after firmware upload to properly release the device handle before reconnect.

### `dsl.c`

3. **`logic.unitsize` assignment** — In `receive_transfer()`, added `logic.unitsize = (dsl_en_ch_num(sdi) + 7) / 8;` so that the `SR_DF_LOGIC` packet carries the correct unit size. Without this, downstream code (including pydsview's data callback) cannot determine bytes-per-sample.

## Running Tests

```bash
pytest tests/
```

The `test_export.py` tests work without hardware. The `test_context.py`, `test_device.py`, and `test_capture.py` tests require the compiled library and use the Demo device.

## License

GPL-3.0-or-later (same as DSView)
