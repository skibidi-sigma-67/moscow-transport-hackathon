import itertools
import math
from dataclasses import dataclass

from ml.schedule import Observation, clean, distance

FEATURE_VERSION = "v1"


@dataclass(frozen=True)
class Stop:
    time: float
    lon: float
    lat: float
    stop_id: int


def select_target(stops, now):
    return next(
        (s for s in sorted(stops, key=lambda s: s.time) if 600 < s.time - now <= 900),
        None,
    )


def reconstruct_deviation(history, stops, now, radius=75):
    rows = clean(history, now)
    ordered = sorted(stops, key=lambda s: s.time)
    last_index = -1
    candidate = None
    first = None
    result = (None, None)
    for p in rows:
        matches = [
            i
            for i, s in enumerate(ordered)
            if i > last_index
            and s.time <= now
            and distance((p.lon, p.lat), (s.lon, s.lat)) <= radius
        ]
        if len(matches) != 1 or p.speed > 12:
            candidate = first = None
            continue
        i = matches[0]
        if candidate == i and 2 <= p.time - first <= 45:
            result = (first - ordered[i].time, now - first)
            last_index = i
            candidate = first = None
        else:
            candidate, first = i, p.time
    return result


def features(history, stops, target, now, cur_dev=None):
    rows = clean(history, now)
    f = {
        "cur_dev_s": float(cur_dev) if cur_dev is not None else math.nan,
        "cur_dev_missing": float(cur_dev is None),
        "horizon_s": target.time - now,
        "hour_sin": math.sin(2 * math.pi * (now % 86400) / 86400),
        "hour_cos": math.cos(2 * math.pi * (now % 86400) / 86400),
        "stops_ahead": float(sum(now < s.time <= target.time for s in stops)),
        "target_lon": target.lon,
        "target_lat": target.lat,
        "gps_age_s": now - rows[-1].time if rows else 3600.0,
        "distance_target_m": distance(
            (rows[-1].lon, rows[-1].lat), (target.lon, target.lat)
        )
        if rows
        else math.nan,
    }
    if rows and math.isfinite(f["distance_target_m"]):
        latest = rows[-1]
        east = (
            math.radians(target.lon - latest.lon)
            * 6371000
            * math.cos(math.radians((latest.lat + target.lat) / 2))
        )
        north = math.radians(target.lat - latest.lat) * 6371000
        bearing = math.degrees(math.atan2(east, north))
        f["last_lon"] = latest.lon
        f["last_lat"] = latest.lat
        f["last_speed"] = latest.speed
        f["heading_alignment"] = math.cos(math.radians(bearing - latest.heading))
        f["required_speed_kmh"] = f["distance_target_m"] * 3.6 / f["horizon_s"]
        f["distance_per_stop_m"] = f["distance_target_m"] / max(1.0, f["stops_ahead"])
        f["target_east_m"] = east
        f["target_north_m"] = north
    else:
        for name in (
            "last_lon",
            "last_lat",
            "last_speed",
            "heading_alignment",
            "required_speed_kmh",
            "distance_per_stop_m",
            "target_east_m",
            "target_north_m",
        ):
            f[name] = math.nan
    for window in (60, 180, 300, 600, 900):
        points = [p for p in rows if p.time >= now - window]
        durations = [
            min(
                30.0,
                max(0.0, (points[i + 1].time if i + 1 < len(points) else now) - p.time),
            )
            for i, p in enumerate(points)
        ]
        total = sum(durations)
        speeds = [p.speed for p in points]
        f.update(
            {
                f"speed_{window}": sum(p.speed * d for p, d in zip(points, durations))
                / total
                if total
                else math.nan,
                f"idle_{window}": sum(
                    d for p, d in zip(points, durations) if p.speed < 3
                )
                / total
                if total
                else math.nan,
                f"coverage_{window}": total / window,
                f"count_{window}": float(len(points)),
                f"trend_{window}": speeds[-1] - speeds[0] if speeds else math.nan,
                f"max_gap_{window}": max(
                    [b.time - a.time for a, b in itertools.pairwise(points)]
                    + [now - points[-1].time if points else float(window)]
                ),
            }
        )
    return f


def sequence(history, now):
    rows = clean(history, now)
    result, j, last = [], 0, None
    for t in range(60):
        tick = now - 885 + t * 15
        while j < len(rows) and rows[j].time <= tick:
            last = rows[j]
            j += 1
        age = min(900.0, tick - last.time) if last else 900.0
        fresh = last is not None and age <= 30
        result.append(
            [
                last.speed / 100 if fresh else 0.0,
                math.sin(math.radians(last.heading)) if fresh else 0.0,
                math.cos(math.radians(last.heading)) if fresh else 0.0,
                float(last.speed < 3) if fresh else 0.0,
                float(fresh),
                age / 900,
            ]
        )
    return result
