import csv
import math
import re
from collections import defaultdict
from datetime import datetime

from commons.contracts.v1.ml.requests import RouteFeatures
from ml.features import history, timestamp

_POINT = re.compile(r"^POINT\s*\(([-\d.]+)\s+([-\d.]+)\)$")
_EARTH_RADIUS_M = 6371000.0


class SchedulePlan:
    def __init__(self, path):
        by_vehicle = defaultdict(list)
        with open(path, newline="") as file:
            for row in csv.DictReader(file):
                match = _POINT.fullmatch(row["geom"].strip())
                if match is None:
                    continue
                lon, lat = map(float, match.groups())
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    continue
                by_vehicle[int(row["tr_id"])].append(
                    (
                        timestamp(datetime.fromisoformat(row["time_begin"])),
                        int(row["tt_action_item_id"]),
                        lon,
                        lat,
                    )
                )
        self.by_vehicle = {
            vehicle: sorted(stops) for vehicle, stops in by_vehicle.items()
        }

    def route_features(self, request):
        stops = self.by_vehicle.get(request.tr_id, ())
        target_time = timestamp(request.target_time_begin)
        target = next(
            (
                stop
                for stop in stops
                if stop[1] == request.target_stop_id and stop[0] == target_time
            ),
            None,
        )
        if target is None:
            return None

        now = timestamp(request.current_time_T)
        _, _, target_lon, target_lat = target
        rows = history(request, keep_last=True)
        if rows:
            last_time, lon, lat, speed, heading = rows[-1]
            east = (
                math.radians(target_lon - lon)
                * _EARTH_RADIUS_M
                * math.cos(math.radians((lat + target_lat) / 2))
            )
            north = math.radians(target_lat - lat) * _EARTH_RADIUS_M
            lat1, lat2 = math.radians(lat), math.radians(target_lat)
            haversine = (
                math.sin((lat2 - lat1) / 2) ** 2
                + math.cos(lat1)
                * math.cos(lat2)
                * math.sin(math.radians(target_lon - lon) / 2) ** 2
            )
            distance = 2 * _EARTH_RADIUS_M * math.asin(
                min(1.0, math.sqrt(max(0.0, haversine)))
            )
            bearing = math.degrees(math.atan2(east, north))
            alignment = math.cos(math.radians(bearing - heading))
            gps_age = now - last_time
        else:
            lon = lat = speed = east = north = distance = alignment = math.nan
            gps_age = 3600.0

        angle = 2 * math.pi * (now % 86400) / 86400
        return RouteFeatures(
            cur_dev_missing=0.0,
            horizon_s=target_time - now,
            hour_sin=math.sin(angle),
            hour_cos=math.cos(angle),
            stops_ahead=float(sum(now < stop[0] <= target_time for stop in stops)),
            target_lon=target_lon,
            target_lat=target_lat,
            distance_target_m=distance,
            gps_age_s=gps_age,
            last_lon=lon,
            last_lat=lat,
            last_speed=speed,
            heading_alignment=alignment,
            target_east_m=east,
            target_north_m=north,
        )
