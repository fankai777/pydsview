"""
capture_compare_loop.py — Continuous triggered capture + background anomaly
detection.

Comparison rule: CH4/6/8/10 (even group) must all match; CH5/7/9/11 (odd
group) must all match. If any channel in a group differs from the rest of
the group, the capture is anomalous.

- Normal captures → discarded (nothing written).
- Anomalous captures → written to anomalies/anomaly_<timestamp>_<id>.csv.

Threading layout:
- Main thread: triggers captures in a tight loop. As soon as a capture
  finishes, hand the raw result off to the worker queue and start the next
  capture. Main NEVER blocks on comparison work.
- Worker thread: pops results, decodes per-channel arrays, compares, writes
  CSV if anomalous.

This way a slow compare (or a large anomaly write) never causes a missed
capture. Queue depth is monitored; if it grows, the worker is falling behind.

Stop with Ctrl+C — current capture finishes, queue drains, CSVs flush.
"""

import os
import queue
import signal
import threading
import time
from datetime import datetime

import numpy as np
import pydsview

# ---- config ---------------------------------------------------------------
FIRMWARE_DIR    = "D:/wanzi/dsview/DSView/DSView/res"
DEVICE_INDEX    = 1
CHANNELS        = list(range(4, 12))
EVEN_GROUP      = [4, 6, 8, 10]
ODD_GROUP       = [5, 7, 9, 11]
SAMPLERATE      = pydsview.SR_MHZ(25)
VTH             = 1.6
DURATION_SEC    = 5
TRIGGER_CHANNEL = 4
TRIGGER_SPEC    = "F"
TRIGGER_POS_PCT = 50
TIMEOUT_SEC     = 60.0         # per-capture trigger timeout
MAX_CAPTURES    = 0            # 0 = forever (Ctrl+C to stop)
OUTPUT_DIR      = "anomalies"
# Channels are flagged as anomalous only if mismatched samples exceed this
# fraction of total samples. 0.001 = 0.1% — comfortably above the edge-jitter
# noise floor (~0.01%) we saw in calibration.
TOLERANCE_FRAC  = 0.001
# ---------------------------------------------------------------------------

_shutdown = threading.Event()


def compare_group(ch_map, group, tolerance_frac):
    """Return list of (ch, mismatch_count) for channels whose mismatch exceeds
    tolerance_frac * total_samples."""
    ref = ch_map[group[0]]
    threshold = int(len(ref) * tolerance_frac)
    diffs = []
    for c in group[1:]:
        arr = ch_map[c]
        mismatches = int((ref != arr).sum())
        if mismatches > threshold:
            diffs.append((c, mismatches))
    return diffs


def write_anomaly_csv(path, ch_map, samplerate):
    """Write compressed CSV using the vectorized Exporter writer."""
    pydsview.export.Exporter.write_logic_csv(
        path, ch_map, CHANNELS, samplerate,
        time_column=True, compressed=True,
    )


def compare_worker(q, output_dir, stats):
    """Worker: decode + compare + write CSV (or discard)."""
    while True:
        item = q.get()
        if item is None:
            q.task_done()
            return
        cap_id, samplerate, channel_indices, raw_data, unitsize, ch_count = item
        t0 = time.time()

        # Decode per-channel arrays from raw bytes.
        # Mirror capture.CaptureResult.to_channel_arrays() — CROSS_DATA format.
        n_ch = ch_count
        words = np.frombuffer(raw_data, dtype=np.uint64)
        n_groups = len(words) // n_ch if n_ch else 0
        if n_groups == 0:
            print(f"  [worker] #{cap_id} empty data, skipping")
            q.task_done()
            continue
        words = words[: n_groups * n_ch].reshape(n_groups, n_ch)
        bits = np.arange(64, dtype=np.uint64)

        ch_map = {}
        for i, idx in enumerate(channel_indices):
            w = words[:, i]
            unpacked = ((w[:, None] >> bits[None, :]) & 1).astype(bool)
            ch_map[idx] = unpacked.ravel()

        even_diffs = compare_group(ch_map, EVEN_GROUP, TOLERANCE_FRAC)
        odd_diffs  = compare_group(ch_map, ODD_GROUP, TOLERANCE_FRAC)
        elapsed = time.time() - t0

        if not (even_diffs or odd_diffs):
            stats["ok"] += 1
            raw_even = [(c, int((ch_map[EVEN_GROUP[0]] != ch_map[c]).sum())) for c in EVEN_GROUP[1:]]
            raw_odd  = [(c, int((ch_map[ODD_GROUP[0]]  != ch_map[c]).sum())) for c in ODD_GROUP[1:]]
            print(f"  [worker] #{cap_id} OK ({elapsed:.2f}s) even={raw_even} odd={raw_odd}  [ok={stats['ok']} anom={stats['anom']}]")
        else:
            stats["anom"] += 1
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(output_dir, f"anomaly_{ts}_{cap_id:04d}.csv")
            write_anomaly_csv(path, ch_map, samplerate)
            reasons = []
            if even_diffs:
                reasons.append("even " + ",".join(f"CH{c}({m})" for c, m in even_diffs))
            if odd_diffs:
                reasons.append("odd "  + ",".join(f"CH{c}({m})" for c, m in odd_diffs))
            print(f"  [worker] #{cap_id} ANOMALY ({elapsed:.2f}s) "
                  f"{'; '.join(reasons)} -> {os.path.basename(path)}")
        q.task_done()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    def _sig(*_):
        if _shutdown.is_set():
            return  # ignore second Ctrl+C
        print("\n[!] Interrupt — finishing current capture, then stopping.")
        _shutdown.set()
    signal.signal(signal.SIGINT, _sig)

    q: "queue.Queue" = queue.Queue()
    stats = {"ok": 0, "anom": 0}
    worker = threading.Thread(target=compare_worker, args=(q, OUTPUT_DIR, stats))
    worker.start()

    total = 0
    with pydsview.DSContext(firmware_dir=FIRMWARE_DIR) as ctx:
        dev = ctx.get_device(DEVICE_INDEX)
        print(f"Active: {dev}  channels={len(dev.channels)}")
        dev.set_config(pydsview.Config.OPERATION_MODE, 1)
        dev.set_config(pydsview.Config.VTH, VTH)
        dev.samplerate = SAMPLERATE
        dev.sample_count = SAMPLERATE * DURATION_SEC
        dev.set_config(pydsview.Config.RLE, False)
        dev.set_config(pydsview.Config.LOOP_MODE, False)
        for ch in dev.channels:
            dev.enable_channel(ch.index, ch.index in CHANNELS)
        trig = pydsview.TriggerConfig()

        print(f"Config:  {dev.samplerate} Hz, {dev.sample_count} samples, VTH={VTH} V")
        print(f"Trigger: CH{TRIGGER_CHANNEL} {TRIGGER_SPEC!r} @ {TRIGGER_POS_PCT}%")
        print(f"Compare: even={EVEN_GROUP}, odd={ODD_GROUP}, tol={TOLERANCE_FRAC*100:.3g}%")
        print(f"Output:  {OUTPUT_DIR}/   (Ctrl+C to stop)\n")

        while not _shutdown.is_set():
            if MAX_CAPTURES and total >= MAX_CAPTURES:
                break
            total += 1
            print(f"=== capture #{total} (queue depth={q.qsize()}) ===")

            trig.reset()
            trig.set_mode(pydsview.TriggerMode.SIMPLE)
            trig.set_position(TRIGGER_POS_PCT)
            trig.set_channel_trigger(TRIGGER_CHANNEL, TRIGGER_SPEC)
            trig.set_enabled(True)

            try:
                session = dev.start_capture()
            except Exception as e:
                print(f"  [cap #{total}] start_capture failed: {e}")
                time.sleep(1.0)
                continue

            t0 = time.time()
            timed_out = False
            while not session.is_done():
                if _shutdown.is_set():
                    session.stop()
                    break
                if time.time() - t0 > TIMEOUT_SEC:
                    print(f"  [cap #{total}] trigger timeout, stopping")
                    session.stop()
                    timed_out = True
                    break
                time.sleep(0.3)

            try:
                result = session.wait(timeout=5.0)
            except Exception as e:
                print(f"  [cap #{total}] wait failed: {e}")
                continue

            if _shutdown.is_set():
                break
            if timed_out or not result.raw_data:
                print(f"  [cap #{total}] no data (timeout={timed_out}), skip")
                continue

            # Hand off to worker. We pass the raw bytearray as immutable bytes
            # so the worker can process independently while main starts the
            # next capture.
            q.put((
                total,
                result.samplerate,
                list(result.channel_indices),
                bytes(result.raw_data),
                result.unitsize,
                result.channel_count,
            ))
            elapsed = time.time() - t0
            print(f"  [cap #{total}] triggered & done in {elapsed:.1f}s, queued")

    print("\nDraining worker...")
    q.put(None)
    q.join()
    worker.join(timeout=10.0)
    print(f"Finished. captures={total}  ok={stats['ok']}  anomalies={stats['anom']}")
    print(f"Anomaly CSVs in: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
