import math

WINDOWS = (60, 180, 300, 900)
MAX_GAP_S = 30.0


def motion(rows, now):
    totals = {w: [0.0] * 6 for w in WINDOWS}
    stop_start = None
    last_moving = None
    stops = 0
    jumps = 0
    previous = None
    for row in rows:
        t, lon, lat, speed, _ = row
        moving = speed >= 3
        if moving:
            last_moving = t
            stop_start = None
        elif previous is None or t - previous[0] > MAX_GAP_S or previous[3] >= 3:
            stop_start = t
            stops += 1
        if previous is not None:
            pt, plon, plat, pspeed, _ = previous
            dt = t - pt
            if 0 < dt <= MAX_GAP_S:
                dx = math.radians(lon - plon) * math.cos(math.radians((lat + plat) / 2))
                dy = math.radians(lat - plat)
                distance = 6371000 * math.hypot(dx, dy)
                valid_distance = distance <= 130 / 3.6 * dt + 20
                jumps += int(not valid_distance)
                for w, values in totals.items():
                    duration = max(0.0, t - max(pt, now - w))
                    if not duration:
                        continue
                    values[0] += duration
                    values[1] += pspeed * duration
                    values[2] += pspeed * pspeed * duration
                    values[3] += (pspeed < 3) * duration
                    if valid_distance:
                        values[4] += distance * duration / dt
                        values[5] += duration
        previous = row
    result = {}
    for w, (
        duration,
        speed_sum,
        square_sum,
        idle,
        distance,
        gps_duration,
    ) in totals.items():
        mean = speed_sum / duration if duration else math.nan
        result[f"time_speed_{w}"] = mean
        result[f"time_speed_std_{w}"] = (
            math.sqrt(max(0, square_sum / duration - mean * mean))
            if duration
            else math.nan
        )
        result[f"time_idle_{w}"] = idle / duration if duration else math.nan
        result[f"time_coverage_{w}"] = duration / w
        result[f"safe_distance_{w}"] = distance if gps_duration else math.nan
        result[f"safe_speed_{w}"] = (
            distance / gps_duration * 3.6 if gps_duration else math.nan
        )
    fresh = bool(rows) and now - rows[-1][0] <= MAX_GAP_S
    result["current_stop_s"] = (
        rows[-1][0] - stop_start
        if fresh and stop_start is not None
        else 0.0
        if fresh
        else math.nan
    )
    result["since_moving_s"] = (
        now - last_moving if last_moving is not None else math.nan
    )
    result["stop_count_900"] = stops
    result["gps_jumps_900"] = jumps
    result["time_speed_change"] = result["time_speed_60"] - result["time_speed_900"]
    return result
