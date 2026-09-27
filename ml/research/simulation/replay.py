import argparse
import math
import socket
import struct
import time

import pandas as pd

from research.data.dataset import seconds


def packet(row):
    cell = bytearray(26)
    valid = bool(row.location_valid) and all(
        math.isfinite(v) for v in [row.lon, row.lat, row.speed, row.heading]
    )
    lon, lat = (row.lon, row.lat) if valid else (0.0, 0.0)
    dop = (128 if valid else 0) | (32 if lat >= 0 else 0) | (64 if lon >= 0 else 0)
    struct.pack_into(
        "<IIIB",
        cell,
        0,
        int(row.event_seconds),
        round(abs(lon) * 10000000.0),
        round(abs(lat) * 10000000.0),
        dop,
    )
    struct.pack_into(
        "<H", cell, 14, max(0, min(65535, round(row.speed))) if valid else 0
    )
    struct.pack_into("<H", cell, 18, round(row.heading) % 360 if valid else 0)
    body = struct.pack("<HHHI", 10, 101, 0, 0) + b"\x00\x00" + cell
    return (
        struct.pack("<HHHHBIH", 32382, len(body), 0, 0, 1, int(row.unit_id), 0) + body
    )


def run(args):
    df = pd.read_csv(args.traffic, low_memory=False)
    df["event_seconds"] = seconds(df.event_time)
    df["release"] = (
        seconds(df.receive_time).clip(lower=df.event_seconds)
        if args.clock == "receive"
        else df.event_seconds
    )
    if args.vehicle:
        df = df[df.tr_id == args.vehicle]
    df = df.sort_values("release").head(args.limit)
    start = time.monotonic()
    origin = df.release.iloc[0]
    with socket.create_connection((args.host, args.port)) as sock:
        for row in df.itertuples():
            remaining = (row.release - origin) / args.speed - (time.monotonic() - start)
            if remaining > 0:
                time.sleep(remaining)
            sock.sendall(packet(row))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--traffic", default="dataset/test/traffic.csv")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9201)
    p.add_argument("--clock", choices=["event", "receive"], default="receive")
    p.add_argument("--speed", type=float, default=30)
    p.add_argument("--vehicle", type=int)
    p.add_argument("--limit", type=int, default=10000)
    args = p.parse_args()
    if args.speed <= 0:
        p.error("--speed must be positive")
    run(args)
