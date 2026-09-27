import numpy as np
from ml.features import SUPPORTED_FEATURES, features
from test_api import payload

from commons.contracts.v1.ml.requests import MLPredictionRequest


def test_future_invalid_and_duplicate_points_do_not_change_features():
    data = payload()
    original = MLPredictionRequest.model_validate(data)
    point = data["window"]["recent_points"][0]
    data["window"]["recent_points"] += [
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


def test_empty_telemetry_has_missing_speed_and_finite_hint():
    data = payload()
    data["window"]["recent_points"] = []
    values = features(MLPredictionRequest.model_validate(data))
    assert values["cur_dev_s"] == -40
    assert values["coverage_900"] == 0
    assert np.isnan(values["idle_900"])


def test_selected_features_match_full_computation():
    request = MLPredictionRequest.model_validate(payload())
    full = features(request)
    assert set(full) == SUPPORTED_FEATURES
    names = ["cur_dev_s", "idle_180", "distance_900", "longitude"]
    selected = features(request, names)
    for name in names:
        assert (
            selected[name] == full[name]
            or np.isnan(selected[name])
            and np.isnan(full[name])
        )
