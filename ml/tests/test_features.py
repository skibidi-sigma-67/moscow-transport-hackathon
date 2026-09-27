import numpy as np
from ml.features import features
from test_api import payload

from commons.contracts.v1.ml.requests import MLPredictionRequest


def test_future_invalid_and_duplicate_points_do_not_change_features():
    data = payload()
    original = MLPredictionRequest.model_validate(data)
    point = data["recent_telemetry"][0]
    data["recent_telemetry"] += [
        point,
        dict(point, timestamp="2026-01-06T12:01:00Z"),
        dict(point, location_valid=False),
        dict(point, packet_time="2026-01-06T12:01:00Z"),
    ]
    modified = MLPredictionRequest.model_validate(data)
    before, after = features(original), features(modified)
    assert before.keys() == after.keys()
    for key in before:
        assert (
            before[key] == after[key]
            or isinstance(before[key], float)
            and np.isnan(before[key])
            and np.isnan(after[key])
        )


def test_empty_telemetry_has_missing_motion_and_finite_hint():
    data = payload()
    data["recent_telemetry"] = []
    values = features(MLPredictionRequest.model_validate(data))
    assert values["cur_dev_s"] == -40
    assert values["coverage_900"] == 0
    assert np.isnan(values["idle_900"])


def test_time_weighted_motion_ignores_gaps_and_gps_jumps():
    from datetime import datetime, timedelta

    data = payload()
    point = data["recent_telemetry"][0]
    now = datetime.fromisoformat(data["current_time_T"])
    data["recent_telemetry"] = [
        dict(
            point,
            timestamp=(now - timedelta(seconds=age)).isoformat(),
            speed=speed,
            longitude=longitude,
        )
        for age, speed, longitude in [
            (100, 0, 37),
            (30, 0, 37),
            (10, 20, 38),
            (0, 20, 38),
        ]
    ]
    values = features(MLPredictionRequest.model_validate(data))
    assert values["time_coverage_900"] == 30 / 900
    assert values["time_idle_900"] == 20 / 30
    assert values["time_speed_900"] == 200 / 30
    assert values["gps_jumps_900"] == 1
    assert values["safe_distance_900"] == 0


def test_selected_features_match_full_computation():
    request = MLPredictionRequest.model_validate(payload())
    full = features(request)
    names = ["cur_dev_s", "time_idle_180", "safe_speed_900", "current_stop_s"]
    selected = features(request, names)
    for name in names:
        assert (
            selected[name] == full[name]
            or np.isnan(selected[name])
            and np.isnan(full[name])
        )
