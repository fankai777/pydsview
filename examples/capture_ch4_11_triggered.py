"""
capture_ch4_11_triggered.py — Capture CH4..CH11 with a simple edge trigger,
25 MHz samplerate, 1.6 V threshold, and save the raw (uncompressed) CSV.

Trigger: rising edge on CH4 at 50% of the buffer. Change TRIGGER_CHANNEL /
TRIGGER_SPEC below if you want a different condition.
"""

import time
import pydsview

# ---- user-tunable ---------------------------------------------------------
FIRMWARE_DIR    = "D:/wanzi/dsview/DSView/DSView/res"
DEVICE_INDEX    = 1                   # matches the other examples
CHANNELS        = list(range(4, 12))  # CH4..CH11
SAMPLERATE      = pydsview.SR_MHZ(25)
VTH             = 1.6                 # volts
DURATION_SEC    = 1                   # capture window
TRIGGER_CHANNEL = 4
TRIGGER_SPEC    = "F"                 # R / F / 1 / 0 / C
TRIGGER_POS_PCT = 50
TIMEOUT_SEC     = 30.0
OUT_CSV         = "capture_ch4_11_25mhz.csv"
# ---------------------------------------------------------------------------


with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
    dev = ctx.get_device(DEVICE_INDEX)
    print(f"Active: {dev}  mode={dev.mode.name}  channels={len(dev.channels)}")

    # Logic config — mirror the DSView GUI sequence.
    dev.set_config(pydsview.Config.OPERATION_MODE, 1)    # 1 = stream
    dev.set_config(pydsview.Config.VTH, VTH)
    dev.samplerate = SAMPLERATE
    dev.sample_count = SAMPLERATE * DURATION_SEC
    dev.set_config(pydsview.Config.RLE, False)
    dev.set_config(pydsview.Config.LOOP_MODE, False)

    # Enable only CH4..CH11.
    for ch in dev.channels:
        dev.enable_channel(ch.index, ch.index in CHANNELS)
    enabled = [c.index for c in dev.channels if c.enabled]
    print(f"Enabled channels: {enabled}")
    print(f"Samplerate: {dev.samplerate} Hz   samples: {dev.sample_count}   VTH: {VTH} V")

    # Trigger setup — must be *before* start_capture().
    trig = pydsview.TriggerConfig()
    trig.reset()
    trig.set_mode(pydsview.TriggerMode.SIMPLE)
    trig.set_position(TRIGGER_POS_PCT)
    trig.set_channel_trigger(TRIGGER_CHANNEL, TRIGGER_SPEC)
    trig.set_enabled(True)
    print(f"Trigger: CH{TRIGGER_CHANNEL} {TRIGGER_SPEC!r} @ {TRIGGER_POS_PCT}%")

    print("Starting triggered capture...")
    session = dev.start_capture()
    t0 = time.time()

    while not session.is_done():
        elapsed = time.time() - t0
        bytes_so_far = len(session._state.result.raw_data)
        print(f"  [{elapsed:.1f}s] waiting... ({bytes_so_far} bytes)")
        time.sleep(1.0)
        if elapsed > TIMEOUT_SEC:
            print("  Timeout — no trigger. Stopping.")
            session.stop()
            time.sleep(0.5)
            break

    elapsed = time.time() - t0
    result = session.wait(timeout=5.0)
    print(f"Capture finished in {elapsed:.1f}s: "
          f"{len(result.raw_data)} bytes, sr={result.samplerate} Hz")

    if not result.raw_data:
        print("No data captured — nothing to export.")
        raise SystemExit(1)

    pydsview.export.Exporter.to_csv(
        result, OUT_CSV,
        channels=CHANNELS,
        compressed=True,        # "压缩数据" — only write rows where values change
    )
    print(f"Wrote raw CSV: {OUT_CSV}")
