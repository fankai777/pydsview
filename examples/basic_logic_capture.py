"""
basic_logic_capture.py — Capture logic data with DSLogic Plus.

Uses the same configuration sequence as DSView GUI for reliable captures.

Usage:
    python basic_logic_capture.py
"""

import time
import pydsview
import numpy as np

FIRMWARE_DIR = "D:/wanzi/dsview/DSView/DSView/res"

with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
    # List available devices
    print("Available devices:")
    for info in ctx.list_devices():
        print(f"  {info.name}  (handle={info.handle:#x})")

    # Activate the DSLogic Plus (index 1)
    dev = ctx.get_device(1)
    print(f"\nActive: {dev}")
    print(f"  Mode:       {dev.mode.name}")
    print(f"  Channels:   {len(dev.channels)}")
    print(f"  Samplerate: {dev.samplerate} Hz")

    # Configure — mirror DSView GUI sequence
    samplerate = pydsview.SR_MHZ(5)
    duration_sec = 2

    dev.set_config(pydsview.Config.OPERATION_MODE, 1)  # 1=stream mode (INT16)
    dev.set_config(pydsview.Config.VTH, 1.0)           # voltage threshold 1V
    dev.samplerate = samplerate                         # 5 MHz
    dev.sample_count = samplerate * duration_sec        # 2 seconds
    dev.set_config(pydsview.Config.RLE, False)
    dev.set_config(pydsview.Config.LOOP_MODE, False)
    # Note: SR_CONF_INSTANT is only handled for DSO mode in the driver,
    # so setting it has no effect in LOGIC mode.

    print(f"\nConfig applied:")
    print(f"  Samplerate:    {dev.samplerate} Hz")
    print(f"  Sample count:  {dev.sample_count}")

    # Show enabled channels
    channels = dev.channels
    enabled_ch = [ch for ch in channels if ch.enabled]
    ch_indices = [4]
    print(f"  Enabled channels ({len(enabled_ch)}): {ch_indices}")

    # Use async capture to observe progress
    print("\nStarting async capture...")
    session = dev.start_capture()

    t0 = time.time()
    while not session.is_done():
        elapsed = time.time() - t0
        print(f"  [{elapsed:.1f}s] waiting... (raw_data so far: {len(session._state.result.raw_data)} bytes)")
        time.sleep(1.0)
        if elapsed > 15.0:
            print("  Timeout! Stopping capture...")
            session.stop()
            time.sleep(1.0)
            break

    elapsed = time.time() - t0
    print(f"\nCapture finished in {elapsed:.1f}s")

    try:
        result = session.wait(timeout=5.0)
        print(f"  Got {len(result.raw_data)} bytes of data")
        print(f"  Samplerate: {result.samplerate} Hz")
        print(f"  Unitsize: {result.unitsize}")
        print(f"  Channel count: {result.channel_count}")
        print(f"  Data format: {result.data_format}")

        if result.raw_data:
            # Show first 64 raw bytes in hex
            print(f"  First 64 raw bytes: {result.raw_data[:64].hex(' ')}")

            # Decode LA_CROSS_DATA into per-channel arrays
            ch_arrays = result.to_channel_arrays()
            print(f"  Decoded {len(ch_arrays)} channels, {len(ch_arrays[0]) if ch_arrays else 0} samples each")

            # Check each channel for activity
            for i, ch_data in enumerate(ch_arrays):
                high = ch_data.sum()
                total = ch_data.size
                pct = high / total * 100 if total else 0
                ch_idx = ch_indices[i] if i < len(ch_indices) else i
                if pct > 0.1:
                    print(f"  CH{ch_idx}: {high}/{total} high ({pct:.1f}%)")

            # Also verify to_numpy() reconstructs packed data
            packed = result.to_numpy()
            nonzero = np.count_nonzero(packed)
            print(f"\n  to_numpy(): shape={packed.shape}, dtype={packed.dtype}, non-zero={nonzero}/{packed.size}")

            if nonzero == 0:
                print("  WARNING: All data is zero - no signal detected on any channel")

        # Export as CSV
        pydsview.export.Exporter.to_csv(
            result, "capture_5mhz.csv",
            channels=ch_indices,
        )
        pydsview.export.Exporter.save_session(
            result, "capture_5mhz.dsl", 
            channel_indices=ch_indices,
        )
        print(f"\nExported to capture_5mhz.csv ({len(ch_indices)} channels)")
    except Exception as e:
        import traceback
        print(f"  Error: {e}")
        traceback.print_exc()
