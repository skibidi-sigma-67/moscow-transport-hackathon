from datetime import datetime, timedelta

import numpy as np
from ml.features import SUPPORTED_FEATURES, features
from ml.schedule import ScheduleCatalog, schedule_features
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


def test_empty_telemetry_has_missing_speed_and_finite_hint():
    data = payload()
    data["recent_telemetry"] = []
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


def test_schedule_features_require_matching_target(tmp_path):
    data = payload()
    now = datetime.fromisoformat(data["current_time_T"])
    path = tmp_path / "schedule_plan.csv"
    path.write_text(
        "tr_id,tt_action_item_id,time_begin,geom\n"
        f"1,2,{(now + timedelta(seconds=660)).isoformat()},\n"
        f"1,1,{data['target_time_begin']},POINT (37.2 55.2)\n"
        f"1,1,{(now + timedelta(days=1)).isoformat()},POINT (37.3 55.3)\n"
    )
    request = MLPredictionRequest.model_validate(data)
    catalog = ScheduleCatalog(path)
    matched = catalog.resolve(request)
    assert matched is not None
    result = schedule_features(request, *matched)
    assert result["stops_ahead"] == 2
    assert np.isfinite(result["target_east_m"])
    changed = request.model_copy(
        update={"target_time_begin": request.target_time_begin + timedelta(seconds=1)}
    )
    assert catalog.resolve(changed) is None
    path.write_text(
        path.read_text()
        + f"1,1,{data['target_time_begin']},POINT (37.4 55.4)\n"
    )
    assert ScheduleCatalog(path).resolve(request) is None
