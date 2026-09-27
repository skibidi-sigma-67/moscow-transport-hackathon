import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from research.data.dataset import OUTPUT


def ready(url):
    try:
        with urllib.request.urlopen(url, timeout=0.2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def run(port, output, count):
    url = f"http://127.0.0.1:{port}/health"
    if ready(url):
        raise RuntimeError(f"An API is already listening at {url}")
    samples = []
    for _ in range(count):
        started = time.perf_counter()
        process = subprocess.Popen(
            [sys.executable, "-m", "ml.main"],
            env={**os.environ, "APP__PORT": str(port)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            while not ready(url):
                if process.poll() is not None:
                    raise RuntimeError(f"ML API exited with code {process.returncode}")
                if time.perf_counter() - started > 10:
                    raise TimeoutError("ML API did not become ready within 10 seconds")
                time.sleep(0.02)
            samples.append((time.perf_counter() - started) * 1000)
        finally:
            process.terminate()
            process.wait(timeout=5)
    result = {
        "environment": platform.platform(),
        "python": platform.python_version(),
        "samples_ms": samples,
        "median_ms": float(np.median(samples)),
        "max_ms": max(samples),
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18001)
    parser.add_argument("--output", type=Path, default=OUTPUT / "startup.json")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("runs must be positive")
    run(args.port, args.output, args.runs)
