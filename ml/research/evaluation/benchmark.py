import argparse
import concurrent.futures
import json
import platform
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np


def run(url):
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    payload = {
        "tr_id": 1,
        "target_stop_id": 1,
        "target_time_begin": (now + timedelta(seconds=720)).isoformat(),
        "current_time_T": now.isoformat(),
        "cur_dev_s": None,
        "cur_dev_source": "gps",
        "planned_stops": [
            {
                "stop_id": 1,
                "time_begin": (now + timedelta(seconds=720)).isoformat(),
                "longitude": 37.1,
                "latitude": 55.1,
            }
        ],
        "recent_telemetry": [
            {
                "timestamp": (now - timedelta(seconds=15 * i)).isoformat(),
                "longitude": 37.0,
                "latitude": 55.0,
                "speed": 20,
                "course": 90,
                "location_valid": True,
            }
            for i in range(60)
        ],
    }
    results = {}
    with httpx.Client(
        base_url=url, timeout=10, limits=httpx.Limits(max_connections=64)
    ) as client:
        client.get("/health").raise_for_status()

        def call(_):
            start = time.perf_counter()
            r = client.post("/predict", json=payload)
            r.raise_for_status()
            assert r.json()["status"] == "DEGRADED"
            return (time.perf_counter() - start) * 1000

        for _ in range(10):
            call(0)
        for concurrency in [1, 8, 32]:
            start = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                latency = list(pool.map(call, range(300)))
            elapsed = time.perf_counter() - start
            results[str(concurrency)] = {
                "p50_ms": float(np.quantile(latency, 0.5)),
                "p95_ms": float(np.quantile(latency, 0.95)),
                "p99_ms": float(np.quantile(latency, 0.99)),
                "requests_per_second": 300 / elapsed,
                "errors": 0,
            }
    report = {
        "hardware": platform.platform(),
        "cpu": platform.processor(),
        "scope": "Local loopback HTTP, 60 telemetry points per request. Does not measure full NDTP/backend chain.",
        "results": results,
    }
    Path("ml/artifacts/benchmark.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8001")
    run(p.parse_args().url)
