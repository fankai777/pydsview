"""
capture_ch4_11_fixed.py — Same capture as capture_ch4_11_triggered.py, but
bypasses the buggy export.to_csv() bit-shift logic and writes the CSV directly
from to_channel_arrays(). Run once to confirm CH4..CH11 all show activity.
"""

import csv
import time
import pydsview

FIRMWARE_DIR    = "D:/wanzi/dsview/DSView/DSView/res"
DEVICE_INDEX    = 1
CHANNELS        = list(range(4, 12))
SAMPLERATE      = pydsview.SR_MHZ(25)
VTH             = 1.6
DURATION_SEC    = 1
TRIGGER_CHANNEL = 4
TRIGGER_SPEC    = "F"
TRIGGER_POS_PCT = 50
TIMEOUT_SEC     = 30.0
OUT_CSV         = "capture_ch4_11_fixed.csv"
COMPRESSED      = True

with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
    dev = ctx.get_device(DEVICE_INDEX)
    print(f"Active: {dev}  mode={dev.mode.name}  channels={len(dev.channels)}")

    dev.set_config(pydsview.Config.OPERATION_MODE, 1)
    dev.set_config(pydsview.Config.VTH, VTH)
    dev.samplerate = SAMPLERATE
    dev.sample_count = SAMPLERATE * DURATION_SEC
    dev.set_config(pydsview.Config.RLE, False)
    dev.set_config(pydsview.Config.LOOP_MODE, False)

    for ch in dev.channels:
        dev.enable_channel(ch.index, ch.index in CHANNELS)
    enabled_indices = [c.index for c in dev.channels if c.enabled]
    print(f"Enabled (in device order): {enabled_indices}")

    trig = pydsview.TriggerConfig()
    trig.reset()
    trig.set_mode(pydsview.TriggerMode.SIMPLE)
    trig.set_position(TRIGGER_POS_PCT)
    trig.set_channel_trigger(TRIGGER_CHANNEL, TRIGGER_SPEC)
    trig.set_enabled(True)

    session = dev.start_capture()
    t0 = time.time()
    while not session.is_done():
        elapsed = time.time() - t0
        print(f"  [{elapsed:.1f}s] waiting...")
        time.sleep(1.0)
        if elapsed > TIMEOUT_SEC:
            print("  Timeout.")
            session.stop()
            time.sleep(0.5)
            break

    result = session.wait(timeout=5.0)
    print(f"Done: {len(result.raw_data)} bytes, channel_count={result.channel_count}, "
          f"unitsize={result.unitsize}")

    # Per-channel decode — to_channel_arrays() returns arrays in *enabled* order,
    # so index i corresponds to enabled_indices[i].
    ch_arrays = result.to_channel_arrays()
    print(f"Decoded {len(ch_arrays)} arrays, {len(ch_arrays[0]) if ch_arrays else 0} samples each")

    # Per-channel toggle counts (quick sanity check)
    for idx, arr in zip(enabled_indices, ch_arrays):
        toggles = int((arr[1:] != arr[:-1]).sum()) if arr.size > 1 else 0
        print(f"  CH{idx}: first={int(arr[0]) if arr.size else '?'}  toggles={toggles}")

    # Build CSV directly from ch_arrays — bypassing to_numpy/to_csv.
    sr = result.samplerate or 1
    period = 1.0 / sr
    ch_map = {idx: arr for idx, arr in zip(enabled_indices, ch_arrays)}
    n_samples = len(ch_arrays[0]) if ch_arrays else 0

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Time(s)"] + [str(c) for c in CHANNELS])
        prev = None
        for i in range(n_samples):
            values = [int(ch_map[c][i]) if c in ch_map else 0 for c in CHANNELS]
            if COMPRESSED and prev is not None and values == prev:
                continue
            prev = values
            w.writerow([f"{i * period:.15g}"] + values)

    print(f"Wrote {OUT_CSV}")
