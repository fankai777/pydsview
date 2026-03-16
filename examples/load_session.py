"""
load_session.py — Load a saved DSView session file and extract data.

Usage:
    python load_session.py recording.dsl
"""

import sys
import pydsview

if len(sys.argv) < 2:
    print("Usage: python load_session.py <file.dsl>")
    sys.exit(1)

session_file = sys.argv[1]

with pydsview.DSContext() as ctx:
    print(f"Loading session: {session_file}")
    dev = ctx.load_session_file(session_file)

    print(f"  Device: {dev.name}")
    print(f"  Mode:   {dev.mode.name}")

    channels = dev.channels
    print(f"  Channels: {len(channels)}")
    for ch in channels:
        print(f"    {ch}")

    # Replay the data from the file
    print("\nReplaying capture...")
    result = dev.capture(timeout=30.0)

    data = result.to_numpy()
    print(f"  Data shape: {data.shape}, dtype: {data.dtype}")
    print(f"  Samplerate: {result.samplerate} Hz")

    # Export to CSV
    out_csv = session_file.rsplit(".", 1)[0] + "_export.csv"
    pydsview.export.Exporter.to_csv(result, out_csv)
    print(f"\nExported to {out_csv}")
