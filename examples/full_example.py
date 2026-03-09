"""
full_example.py —— 完整功能示例

展示：通道选择、采样率、电压阈值、开始/停止、导出文件
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydsview import DSLogicDevice, LibraryNotFoundError, DeviceNotFoundError


def main():
    try:
        with DSLogicDevice() as dev:

            # ── 1. 通道配置 ──────────────────────────
            # 只启用 CH0~CH3，禁用其余通道
            dev.enable_channels([0, 1, 2, 3], total=8)
            print("通道：CH0~CH3 已启用")

            # ── 2. 采样率 ────────────────────────────
            samplerate = 10_000_000  # 10 MHz
            dev.set_samplerate(samplerate)
            print(f"采样率：{samplerate / 1e6:.0f} MHz")

            # ── 3. 电压阈值 ──────────────────────────
            # 3.3V 系统用 1.65V，1.8V 系统用 0.9V
            dev.set_voltage_threshold(1.65)
            print("电压阈值：1.65V（适合 3.3V 系统）")

            # ── 4. 采样数量 ──────────────────────────
            sample_count = 1_000_000  # 1M 样本
            dev.set_sample_count(sample_count)
            print(f"采样数：{sample_count:,}")

            # ── 5. 开始采集（同步阻塞） ──────────────
            print("开始采集...")
            data = dev.capture()
            print(f"采集完成，共 {len(data):,} 字节")

            # ── 6. 导出文件 ──────────────────────────
            # CSV（带时间戳，只导出 CH0~CH3）
            dev.export_csv(data, "capture.csv",
                           channels=[0, 1, 2, 3],
                           samplerate=samplerate)
            print("已导出：capture.csv")

            # VCD（可用 GTKWave 打开）
            dev.export_vcd(data, "capture.vcd",
                           channels=[0, 1, 2, 3],
                           samplerate=samplerate)
            print("已导出：capture.vcd")

            # 原始二进制
            dev.export_binary(data, "capture.bin")
            print("已导出：capture.bin")

    except LibraryNotFoundError as e:
        print(f"[错误] 找不到库：{e}")
        sys.exit(1)
    except DeviceNotFoundError as e:
        print(f"[错误] 找不到设备：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
