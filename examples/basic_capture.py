"""
basic_capture.py —— 最基础的 DSLogic 采集示例

运行前确保：
  1. libsigrok4DSL 已编译（见 README）
  2. DSLogic 设备已通过 USB 连接
  3. 驱动已安装（Windows 需要 WinUSB/libusb-win32）
"""

import sys
import os

# 如果从源码目录运行，把上级目录加到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydsview import DSLogicDevice, LibraryNotFoundError, DeviceNotFoundError


def main():
    print("pydsview 采集示例")
    print("=" * 40)

    try:
        with DSLogicDevice() as dev:
            # 配置
            samplerate = 10_000_000   # 10 MHz
            sample_count = 1_000_000  # 1M 样本

            print(f"采样率: {samplerate / 1e6:.0f} MHz")
            print(f"样本数: {sample_count:,}")

            dev.set_samplerate(samplerate)
            dev.set_sample_count(sample_count)

            print("开始采集...")
            data = dev.capture()

            print(f"采集完成！收到 {len(data):,} 字节")
            print(f"（每个字节代表 8 个通道的一个时刻）")

            # 简单分析：统计每个通道的高/低比例
            if data:
                print("\n各通道高电平占比（前 1000 个样本）:")
                sample = data[:1000]
                for ch in range(8):
                    mask = 1 << ch
                    high_count = sum(1 for b in sample if b & mask)
                    print(f"  CH{ch}: {high_count / len(sample) * 100:.1f}%")

    except LibraryNotFoundError as e:
        print(f"\n[错误] 找不到 libsigrok4DSL：\n{e}")
        print("\n请按 README 的步骤编译库文件。")
        sys.exit(1)

    except DeviceNotFoundError as e:
        print(f"\n[错误] 找不到 DSLogic 设备：{e}")
        print("请检查 USB 连接，以及驱动是否正确安装。")
        sys.exit(1)

    except Exception as e:
        print(f"\n[错误] {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
