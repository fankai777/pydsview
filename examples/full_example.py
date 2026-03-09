"""
full_example.py —— 完整功能示例

包含两种采集模式：
  1. 手动停止模式（推荐）：start() → 等待 → stop_and_get()
  2. 固定样本数模式：set_sample_count() → capture()
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydsview import DSLogicDevice, LibraryNotFoundError, DeviceNotFoundError


def main():
    try:
        with DSLogicDevice() as dev:

            # ── 1. 通道配置 ──────────────────────────
            dev.enable_channels([0, 1, 2, 3], total=8)

            # ── 2. 采样率 & 电压阈值 ─────────────────
            samplerate = 10_000_000          # 10 MHz
            dev.set_samplerate(samplerate)
            dev.set_voltage_threshold(1.65)  # 3.3V 系统

            # ════════════════════════════════════════
            # 模式 A：手动停止（推荐）
            # ════════════════════════════════════════
            print("开始采集（手动停止模式）...")
            dev.start()

            # 这里可以做任何事：等待按键、等待信号、固定时长...
            time.sleep(1)   # 采集 1 秒

            data = dev.stop_and_get()
            print(f"采集完成，共 {len(data):,} 字节 "
                  f"({len(data) / samplerate * 1000:.1f} ms)")

            # ════════════════════════════════════════
            # 模式 B：固定样本数（自动停止）
            # ════════════════════════════════════════
            # dev.set_sample_count(1_000_000)
            # data = dev.capture()

            # ── 3. 导出文件 ──────────────────────────
            dev.export_csv(data, "capture.csv",
                           channels=[0, 1, 2, 3],
                           samplerate=samplerate)
            print("已导出：capture.csv")

            dev.export_vcd(data, "capture.vcd",
                           channels=[0, 1, 2, 3],
                           samplerate=samplerate)
            print("已导出：capture.vcd")

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
