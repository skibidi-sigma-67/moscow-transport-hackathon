import argparse
import concurrent.futures
import json
import platform
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np

from research.data.dataset import OUTPUT


def run(
    url, output=OUTPUT / "benchmark.json", arrival_rate=20.0, requests=300, payload=None
):
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    payload = payload or {
        "tr_id": 1,
        "target_stop_id": 1,
        "target_time_begin": (now + timedelta(seconds=720)).isoformat(),
        "current_time_T": now.isoformat(),
        "cur_dev_s": 0,
        "aggregates": {
            "segment_avg_speed": 20,
            "idle_time_s": 0,
            "coverage_ratio": 1,
        },
        "window": {
            "start_time": (now - timedelta(seconds=900)).isoformat(),
            "end_time": now.isoformat(),
            "recent_points": [
                {
                    "timestamp": (now - timedelta(seconds=15 * i)).isoformat(),
                    "longitude": 37.0,
                    "latitude": 55.0,
                    "speed": 20,
                    "course": 90,
                    "location_valid": True,
                    "packet_time": now.isoformat(),
                    "is_historical": False,
                }
                for i in range(50)
            ],
        },
    }
    results = {}
    with httpx.Client(
        base_url=url, timeout=10, limits=httpx.Limits(max_connections=64)
    ) as client:
        health = client.get("/health")
        health.raise_for_status()
        results["environment"] = {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "model": health.json()["model"],
            "telemetry_points": len(payload["recent_telemetry"]),
            "closed_loop_requests_per_concurrency": 300,
        }

        def call(_):
            start = time.perf_counter()
            r = client.post("/predict", json=payload)
            r.raise_for_status()
            assert np.isfinite(r.json()["predicted_delay_s"])
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
        started = time.perf_counter()
        scheduled = [started + i / arrival_rate for i in range(requests)]

        def scheduled_call(at):
            call_start = time.perf_counter()
            response = client.post("/predict", json=payload)
            response.raise_for_status()
            assert np.isfinite(response.json()["predicted_delay_s"])
            return ((call_start - at) * 1000, (time.perf_counter() - at) * 1000)

        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
            futures = []
            for at in scheduled:
                time.sleep(max(0.0, at - time.perf_counter()))
                futures.append(pool.submit(scheduled_call, at))
            open_loop = [future.result() for future in futures]
        first = [lag for _, lag in open_loop[: requests // 2]]
        last = [lag for _, lag in open_loop[requests // 2 :]]
        results["open_loop"] = {
            "target_requests_per_second": arrival_rate,
            "requests": requests,
            "client_start_lag_p95_ms": float(
                np.quantile([lag for lag, _ in open_loop], 0.95)
            ),
            "first_half_response_lag_p95_ms": float(np.quantile(first, 0.95)),
            "last_half_response_lag_p95_ms": float(np.quantile(last, 0.95)),
            "drain_ms": max(
                0.0,
                (
                    max(
                        at + lag / 1000
                        for at, (_, lag) in zip(scheduled, open_loop, strict=True)
                    )
                    - scheduled[-1]
                )
                * 1000,
            ),
            "errors": 0,
        }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8001")
    p.add_argument("--output", type=Path, default=OUTPUT / "benchmark.json")
    p.add_argument("--arrival-rate", type=float, default=20.0)
    p.add_argument("--requests", type=int, default=300)
    p.add_argument("--payload", type=Path)
    args = p.parse_args()
    if args.arrival_rate <= 0 or args.requests < 2:
        p.error("arrival-rate must be positive and requests must be at least 2")
    payload = json.loads(args.payload.read_text()) if args.payload else None
    run(args.url, args.output, args.arrival_rate, args.requests, payload)
