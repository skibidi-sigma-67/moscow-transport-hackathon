import csv
import math
import re
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from ml.features import timestamp

ROUTE_FEATURES = frozenset(
    {
        "cur_dev_s",
        "cur_dev_missing",
        "horizon_s",
        "hour_sin",
        "hour_cos",
        "stops_ahead",
        "target_lon",
        "target_lat",
        "distance_target_m",
        "gps_age_s",
        "last_lon",
        "last_lat",
        "last_speed",
        "heading_alignment",
        "target_east_m",
        "target_north_m",
    }
)
GEOMETRY = re.compile(r"POINT\s*\(\s*([^\s()]+)\s+([^\s()]+)\s*\)")


class Stop(NamedTuple):
    time: float
    lon: float | None
    lat: float | None
    stop_id: int


@dataclass(frozen=True)
class Observation:
    time: float
    lon: float
    lat: float
    speed: float
    heading: float = 0.0
    valid: bool = True


def clean(history, now):
    rows = sorted(
        (point for point in history if now - 900 <= point.time <= now),
        key=lambda point: (point.time, point.valid, str(point)),
    )
    dedup = {point.time: point for point in rows}
    return [
        point
        for point in dedup.values()
        if point.valid
        and all(
            math.isfinite(value)
            for value in (point.lon, point.lat, point.speed, point.heading)
        )
        and -180 <= point.lon <= 180
        and -90 <= point.lat <= 90
        and point.lon != 0
        and point.lat != 0
        and 0 <= point.speed <= 130
    ]


class ScheduleCatalog:
    def __init__(self, path):
        by_vehicle = defaultdict(list)
        by_stop = defaultdict(list)
        with Path(path).open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                vehicle = int(row["tr_id"])
                stop_id = int(row["tt_action_item_id"])
                match = GEOMETRY.fullmatch((row.get("geom") or "").strip())
                lon = lat = None
                if match is not None:
                    try:
                        longitude, latitude = map(float, match.groups())
                    except ValueError:
                        longitude = latitude = math.nan
                    if (
                        math.isfinite(longitude)
                        and math.isfinite(latitude)
                        and -180 <= longitude <= 180
                        and -90 <= latitude <= 90
                    ):
                        lon, lat = longitude, latitude
                stop = Stop(
                    timestamp(datetime.fromisoformat(row["time_begin"])),
                    lon,
                    lat,
                    stop_id,
                )
                by_vehicle[vehicle].append(stop.time)
                by_stop[vehicle, stop_id].append(stop)
        if not any(stop.lon is not None for stops in by_stop.values() for stop in stops):
            raise ValueError("No valid schedule geometry")
        self.by_vehicle = {
            vehicle: tuple(sorted(stops))
            for vehicle, stops in by_vehicle.items()
        }
        self.by_stop = by_stop

    def resolve(self, request):
        planned = timestamp(request.target_time_begin)
        candidates = [
            stop
            for stop in self.by_stop.get((request.tr_id, request.target_stop_id), ())
            if abs(stop.time - planned) <= 0.001
        ]
        if len(candidates) != 1 or candidates[0].lon is None:
            return None
        return candidates[0], self.by_vehicle[request.tr_id]


def distance(a, b):
    if not all(math.isfinite(value) for value in (*a, *b)):
        return math.nan
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(min(1, math.sqrt(max(0, h))))


def schedule_features(request, target, stop_times):
    now = timestamp(request.current_time_T)
    start = timestamp(request.window_start_time)
    end = timestamp(request.window_end_time)
    rows = clean(
        [
            Observation(
                timestamp(point.timestamp),
                point.longitude,
                point.latitude,
                point.speed,
                point.course,
                point.location_valid,
            )
            for point in request.recent_telemetry
            if start <= timestamp(point.timestamp) <= end
            and timestamp(point.packet_time) <= now
        ],
        now,
    )
    result = {
        "cur_dev_s": request.cur_dev_s,
        "cur_dev_missing": 0.0,
        "horizon_s": target.time - now,
        "hour_sin": math.sin(2 * math.pi * (now % 86400) / 86400),
        "hour_cos": math.cos(2 * math.pi * (now % 86400) / 86400),
        "stops_ahead": float(
            bisect_right(stop_times, target.time) - bisect_right(stop_times, now)
        ),
        "target_lon": target.lon,
        "target_lat": target.lat,
        "gps_age_s": now - rows[-1].time if rows else 3600.0,
    }
    if rows:
        latest = rows[-1]
        lon, lat, speed, heading = (
            latest.lon,
            latest.lat,
            latest.speed,
            latest.heading,
        )
        result["distance_target_m"] = distance((lon, lat), (target.lon, target.lat))
        east = (
            math.radians(target.lon - lon)
            * 6371000
            * math.cos(math.radians((lat + target.lat) / 2))
        )
        north = math.radians(target.lat - lat) * 6371000
        bearing = math.degrees(math.atan2(east, north))
        result.update(
            last_lon=lon,
            last_lat=lat,
            last_speed=speed,
            heading_alignment=math.cos(math.radians(bearing - heading)),
            target_east_m=east,
            target_north_m=north,
        )
    else:
        result.update(
            distance_target_m=math.nan,
            last_lon=math.nan,
            last_lat=math.nan,
            last_speed=math.nan,
            heading_alignment=math.nan,
            target_east_m=math.nan,
            target_north_m=math.nan,
        )
    return result
