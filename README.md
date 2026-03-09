# pydsview

用 Python 控制 DSLogic 逻辑分析仪采集数据。

## 架构

```
Python (pydsview)
    │
    ▼ ctypes
libsigrok4DSL.so/.dll   ← DSView 内的 C 库（DreamSourceLab 魔改版 libsigrok）
    │
    ▼ libusb
DSLogic 硬件
```

## 快速开始

```python
from pydsview import DSLogicDevice

with DSLogicDevice() as dev:
    dev.set_samplerate(10_000_000)   # 10 MHz
    dev.set_sample_count(1_000_000)  # 1M 样本
    data = dev.capture()             # 阻塞直到采完

# data 是 bytes，每个字节对应 8 个通道在同一时刻的电平
# bit 0 = CH0, bit 1 = CH1, ...
print(f"采集到 {len(data)} 字节")
```

异步采集（流式）：

```python
def on_data(chunk: bytes):
    print(f"收到 {len(chunk)} 字节")

with DSLogicDevice() as dev:
    dev.set_samplerate(10_000_000)
    dev.set_sample_count(1_000_000)
    t = dev.async_capture(on_data)
    t.join()
```

## 安装

```bash
pip install -e .
```

## 编译 libsigrok4DSL（必须先做这步）

libsigrok4DSL 是 DSView 源码内的 C 库，需要从源码编译。

### Windows（使用 WSL2）

```bash
# 1. 在 WSL2 中安装依赖
sudo apt update
sudo apt install -y cmake gcc g++ libglib2.0-dev libusb-1.0-0-dev \
    libzip-dev pkg-config

# 2. 克隆 DSView 源码
git clone https://github.com/DreamSourceLab/DSView.git
cd DSView

# 3. 编译 libsigrok4DSL
mkdir build && cd build
cmake ../libsigrok4DSL -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# 编译产物在 build/libsigrok4DSL.so
```

### Linux

同上，不需要 WSL2，直接在终端运行。

### 指定库路径

将编译好的 `.so` 或 `.dll` 放到 `pydsview/` 目录下，或通过环境变量指定：

```bash
export LIBSIGROK4DSL_PATH=/path/to/libsigrok4DSL.so
```

或在代码中指定：

```python
from pydsview import DSLogicDevice
dev = DSLogicDevice(lib_path="/path/to/libsigrok4DSL.so")
```

## Windows 驱动安装

DSLogic 在 Windows 上需要 WinUSB 或 libusb-win32 驱动。  
推荐用 [Zadig](https://zadig.akeo.ie/) 安装 WinUSB 驱动：

1. 打开 Zadig → Options → List All Devices
2. 选择 "DSLogic"
3. 选择 WinUSB → Install Driver

## 数据格式

`capture()` 返回 `bytes`，每个字节代表所有通道在某一采样时刻的电平：

```
Byte N = 通道状态快照
  bit 0 → CH0
  bit 1 → CH1
  ...
  bit 7 → CH7
```

如果启用了 32 通道模式，unitsize=4（每个样本 4 字节），此时：

```python
import struct
samples = [struct.unpack_from('<I', data, i)[0] for i in range(0, len(data), 4)]
```

## 项目结构

```
pydsview/
├── __init__.py      # 对外 API
├── core.py          # DSLogicDevice 主类
├── lib.py           # ctypes 加载 libsigrok4DSL
├── structs.py       # C 结构体（ctypes.Structure）
├── constants.py     # SR_CONF_* / SR_DF_* 常量
└── exceptions.py    # 自定义异常
examples/
└── basic_capture.py # 基础采集示例
```

## 当前状态

- [x] 库框架、常量、结构体定义
- [x] ctypes 函数签名绑定
- [x] DSLogicDevice 设备控制类
- [x] 同步采集（capture）
- [x] 异步采集（async_capture）
- [ ] 实机测试（需要编译好 libsigrok4DSL）
- [ ] 触发配置 API
- [ ] 多设备支持
- [ ] numpy 数组输出

## License

GPL-3.0（与 DSView/libsigrok4DSL 保持一致）
