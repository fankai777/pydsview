"""
trigger_capture.py — Capture with a simple edge trigger on one channel.

Arms a rising-edge trigger on CH0 at 50% of the buffer. The capture will
not complete until an edge is seen (or the timeout fires), which is how
we verify the trigger actually took effect — a misconfigured trigger
degenerates into a free-running capture.

Usage:
    python trigger_capture.py
"""

import time
import pydsview

FIRMWARE_DIR = "D:/wanzi/dsview/DSView/DSView/res"

# Flip this to try other conditions — see TriggerConfig.set_channel_trigger.
TRIGGER_CHANNEL = 0
TRIGGER_SPEC    = "R"   # R / F / 1 / 0 / C
TRIGGER_POS_PCT = 50
TIMEOUT_SEC     = 10.0

with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
    dev = ctx.get_device(1)
    print(f"Active: {dev}  mode={dev.mode.name}  channels={len(dev.channels)}")

    samplerate = pydsview.SR_MHZ(5)
    dev.set_config(pydsview.Config.OPERATION_MODE, 1)
    dev.set_config(pydsview.Config.VTH, 1.0)
    dev.samplerate = samplerate
    dev.sample_count = samplerate * 1            # 1 second buffer
    dev.set_config(pydsview.Config.RLE, False)
    dev.set_config(pydsview.Config.LOOP_MODE, False)

    # Configure trigger — must happen before start_capture().
    trig = pydsview.TriggerConfig()
    trig.reset()
    trig.set_mode(pydsview.TriggerMode.SIMPLE)
    trig.set_position(TRIGGER_POS_PCT)
    trig.set_channel_trigger(TRIGGER_CHANNEL, TRIGGER_SPEC)
    trig.set_enabled(True)

    print(f"Trigger: CH{TRIGGER_CHANNEL} {TRIGGER_SPEC!r} @ {TRIGGER_POS_PCT}% "
          f"(enabled={trig.enabled}, pos={trig.position})")

    print("Starting triggered capture...")
    session = dev.start_capture()
    t0 = time.time()

    while not session.is_done():
        elapsed = time.time() - t0
        print(f"  [{elapsed:.1f}s] waiting for trigger...")
        time.sleep(1.0)
        if elapsed > TIMEOUT_SEC:
            print("  Timeout — no trigger seen. Stopping.")
            session.stop()
            time.sleep(0.5)
            break

    elapsed = time.time() - t0
    try:
        result = session.wait(timeout=5.0)
        print(f"Capture finished in {elapsed:.1f}s: "
              f"{len(result.raw_data)} bytes, sr={result.samplerate} Hz")
        if result.raw_data:
            ch_arrays = result.to_channel_arrays()
            ch = ch_arrays[TRIGGER_CHANNEL] if TRIGGER_CHANNEL < len(ch_arrays) else None
            if ch is not None and ch.size:
                edges = int(((ch[1:] != ch[:-1])).sum())
                print(f"  CH{TRIGGER_CHANNEL}: {ch.size} samples, {edges} edges observed")
    except Exception as e:
        print(f"  wait() error: {e}")
