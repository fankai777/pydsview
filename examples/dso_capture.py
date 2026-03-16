"""
dso_capture.py — Capture oscilloscope data (requires DSCope or Demo in DSO mode).

Usage:
    python dso_capture.py
"""

import pydsview

FIRMWARE_DIR = None

with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
    dev = ctx.get_device(0)
    print(f"Active: {dev}")

    if dev.mode != pydsview.DeviceMode.DSO:
        print("Device is not in DSO mode. This example requires a DSO-capable device.")
        print(f"Current mode: {dev.mode.name}")
        exit(0)

    # Configure
    dev.samplerate = pydsview.SR_MHZ(10)
    dev.sample_count = 10_000

    # Capture
    print("Capturing DSO data...")
    result = dev.capture(timeout=10.0)

    dso = result.dso_data()
    print(f"  DSO samples: {dso.size}")
    print(f"  Min: {dso.min()}, Max: {dso.max()}, Mean: {dso.mean():.1f}")

    # Export
    pydsview.export.Exporter.to_csv(result, "dso_capture.csv")
    print("Exported to dso_capture.csv")

    # Optional: plot if matplotlib is available
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 4))
        plt.plot(dso[:1000])
        plt.title("DSO Capture (first 1000 samples)")
        plt.xlabel("Sample")
        plt.ylabel("ADC Value")
        plt.savefig("dso_capture.png", dpi=100)
        print("Plot saved to dso_capture.png")
    except ImportError:
        pass
