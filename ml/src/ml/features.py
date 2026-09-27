import itertools
import math
from datetime import UTC

import numpy as np

FEATURE_VERSION = 5
SUPPORTED_FEATURES = {
    "cur_dev_s",
    "horizon_s",
    "hour_sin",
    "hour_cos",
    "gps_age_s",
    "cur_dev_zero",
    "cur_dev_per_horizon",
    "speed_change",
    "vehicle",
    "last_speed",
    "longitude",
    "latitude",
} | {
    f"{name}_{window}"
    for name, windows in (
        ("speed_mean", (60, 180, 300, 900)),
        ("speed_std", (60, 180, 300, 900)),
        ("idle", (60, 180, 300, 900)),
        ("coverage", (60, 180, 300, 900)),
        ("distance", (180, 900)),
        ("effective_speed", (180, 900)),
        ("speed_max", (180, 900)),
    )
    for window in windows
}


def timestamp(value):
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).timestamp()


def history(request, keep_last=False):
    now = timestamp(request.current_time_T)
    start = max(now - 900, timestamp(request.window.start_time))
    end = min(now, timestamp(request.window.end_time))
    rows = {}
    for p in request.window.recent_points:
        t = timestamp(p.timestamp)
        if not start <= t <= end or timestamp(p.packet_time) > now:
            continue
        if not p.location_valid or not all(
            math.isfinite(v) for v in (p.longitude, p.latitude, p.speed, p.course)
        ):
            continue
        if not (
            -180 <= p.longitude <= 180
            and -90 <= p.latitude <= 90
            and 0 <= p.speed <= 130
        ):
            continue
        if p.longitude == p.latitude == 0:
            continue
        row = (t, p.longitude, p.latitude, p.speed, p.course)
        rows[t] = row if keep_last else min(rows.get(t, row), row)
    return sorted(rows.values())


def features(request, names=None):
    if names is not None:
        names = set(names)
        if "speed_change" in names:
            names.update(("speed_mean_60", "speed_mean_900"))
    now = timestamp(request.current_time_T)
    horizon = timestamp(request.target_time_begin) - now
    if not 600 < horizon <= 900:
        raise ValueError("Target must be in (T + 600, T + 900] seconds")
    start, end = (
        timestamp(request.window.start_time),
        timestamp(request.window.end_time),
    )
    if not start <= end <= now:
        raise ValueError("Invalid telemetry window")
    if not all(
        math.isfinite(v)
        for v in (
            request.cur_dev_s,
            request.aggregates.segment_avg_speed,
            request.aggregates.idle_time_s,
            request.aggregates.coverage_ratio,
        )
    ):
        raise ValueError("Non-finite request aggregates")
    if (
        request.aggregates.segment_avg_speed < 0
        or request.aggregates.idle_time_s < 0
        or not 0 <= request.aggregates.coverage_ratio <= 1
    ):
        raise ValueError("Invalid request aggregates")
    rows = history(request)
    angle = now % 86400 / 86400 * 2 * math.pi
    result = {
        "cur_dev_s": request.cur_dev_s,
        "horizon_s": horizon,
        "hour_sin": math.sin(angle),
        "hour_cos": math.cos(angle),
    }
    result["gps_age_s"] = now - rows[-1][0] if rows else 901.0
    for window in (60, 180, 300, 900):
        if names is not None and not any(
            f"{prefix}_{window}" in names
            for prefix in ("speed_mean", "speed_std", "idle", "coverage")
        ):
            continue
        recent = [p for p in rows if p[0] >= now - window]
        speed = [p[3] for p in recent]
        mean = sum(speed) / len(speed) if speed else np.nan
        result[f"speed_mean_{window}"] = mean
        result[f"speed_std_{window}"] = (
            math.sqrt(sum((v - mean) ** 2 for v in speed) / len(speed))
            if speed
            else np.nan
        )
        result[f"idle_{window}"] = (
            sum(v < 3 for v in speed) / len(speed) if speed else np.nan
        )
        result[f"coverage_{window}"] = min(1.0, len(recent) * 10 / window)
    result["cur_dev_zero"] = float(request.cur_dev_s == 0)
    result["cur_dev_per_horizon"] = request.cur_dev_s / horizon
    if names is None or "speed_change" in names:
        result["speed_change"] = result["speed_mean_60"] - result["speed_mean_900"]
    for window in (180, 900):
        if names is not None and not any(
            f"{prefix}_{window}" in names
            for prefix in ("distance", "effective_speed", "speed_max")
        ):
            continue
        recent = [p for p in rows if p[0] >= now - window]
        elapsed = recent[-1][0] - recent[0][0] if len(recent) > 1 else 0
        distance = 0.0
        for a, b in itertools.pairwise(recent):
            dx = math.radians(b[1] - a[1]) * math.cos(math.radians((a[2] + b[2]) / 2))
            dy = math.radians(b[2] - a[2])
            distance += 6371000 * math.hypot(dx, dy)
        result[f"distance_{window}"] = distance if elapsed else np.nan
        result[f"effective_speed_{window}"] = (
            distance / elapsed * 3.6 if elapsed else np.nan
        )
        result[f"speed_max_{window}"] = max((p[3] for p in recent), default=np.nan)
    result["vehicle"] = str(request.tr_id)
    result["last_speed"] = rows[-1][3] if rows else np.nan
    result["longitude"] = rows[-1][1] if rows else np.nan
    result["latitude"] = rows[-1][2] if rows else np.nan
    return result
