# pydsview

用 Python 控制 DSLogic 逻辑分析仪采集数据。

**预编译二进制已内置，开箱即用，无需自行编译。**

## 安装

```bash
pip install pydsview
```

或从源码安装：

```bash
git clone https://github.com/fankai777/pydsview.git
pip install dist/pydsview-0.0.1-py3-none-any.whl
```

## 快速开始

```python
from pydsview import DSLogicDevice

with DSLogicDevice() as dev:
    # 通道配置（只用前4个通道）
    dev.enable_channels([0, 1, 2, 3], total=8)

    # 采样率 & 电压阈值（3.3V 系统）
    dev.set_samplerate(10_000_000)       # 10 MHz
    dev.set_voltage_threshold(1.65)      # 3.3V 系统用 1.65V
    dev.set_sample_count(1_000_000)      # 1M 样本

    # 开始采集（同步阻塞）
    data = dev.capture()

print(f"采集到 {len(data):,} 字节")

# 导出文件
dev.export_csv(data, "capture.csv", channels=[0,1,2,3], samplerate=10_000_000)
dev.export_vcd(data, "capture.vcd", channels=[0,1,2,3], samplerate=10_000_000)
```

## Windows 驱动安装

DSLogic 在 Windows 上需要 WinUSB 驱动，用 [Zadig](https://zadig.akeo.ie/) 安装：

1. 打开 Zadig → Options → List All Devices
2. 选择 "DSLogic"
3. 选择 WinUSB → Install Driver

## 完整 API

| 方法 | 说明 |
|------|------|
| `enable_channel(index, enable)` | 启用/禁用单个通道 |
| `enable_channels([0,1,2,3])` | 批量设置通道 |
| `set_samplerate(hz)` | 采样率，如 `10_000_000` |
| `set_voltage_threshold(v)` | 逻辑电平阈值（V） |
| `set_sample_count(n)` | 采集样本数 |
| `capture()` | 同步采集，返回 `bytes` |
| `async_capture(on_data, on_done)` | 异步流式采集 |
| `stop()` | 停止采集 |
| `export_csv(data, path, ...)` | 导出 CSV（含时间戳） |
| `export_vcd(data, path, ...)` | 导出 VCD（GTKWave 可打开） |
| `export_binary(data, path)` | 导出原始二进制 |

## 数据格式

`capture()` 返回 `bytes`，每字节是 8 个通道的电平快照：

```
bit 0 = CH0, bit 1 = CH1, ... bit 7 = CH7
```

## 架构

```
Python (pydsview)
    │
    ▼ ctypes
libsigrok4DSL.so/.dll   ← DreamSourceLab 魔改版 libsigrok（已内置）
    │
    ▼ libusb
DSLogic 硬件
```

预编译二进制基于 [DreamSourceLab/DSView](https://github.com/DreamSourceLab/DSView) 源码编译。
详见 [BINARIES.md](BINARIES.md)。

## 当前状态

- [x] 预编译 libsigrok4DSL（Linux x86_64 + Windows x86_64）
- [x] 通道启用/禁用
- [x] 采样率、电压阈值、样本数配置
- [x] 同步 / 异步采集
- [x] CSV / VCD / Binary 导出
- [ ] 实机测试（进行中）
- [ ] 触发配置
- [ ] numpy 数组输出

## License

GPL-3.0（与 DSView/libsigrok4DSL 保持一致）
