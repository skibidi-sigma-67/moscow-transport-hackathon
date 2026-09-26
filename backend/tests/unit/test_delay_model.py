from datetime import UTC, datetime, timedelta

import pytest

from backend.ml_service.model import DelayPredictionModel
from commons.contracts.v1.ml.requests import MLPredictionRequest, TelemetryPoint
from commons.enums import IncidentPattern, RiskLevel


def _request(
    tr_id: int,
    cur_dev_s: float,
    idle_time_s: float = 0.0,
) -> MLPredictionRequest:
    current_time = datetime(2026, 1, 6, 12, 0, tzinfo=UTC)
    return MLPredictionRequest(
        tr_id=tr_id,
        target_stop_id=1010,
        target_time_begin=current_time + timedelta(minutes=12),
        current_time_T=current_time,
        cur_dev_s=cur_dev_s,
        segment_avg_speed=20.0,
        idle_time_s=idle_time_s,
        recent_telemetry=[
            TelemetryPoint(
                timestamp=current_time,
                longitude=37.6173,
                latitude=55.7558,
                speed=20.0,
                course=180.0,
            )
        ],
    )


def test_predict_blends_current_delay_with_vehicle_history():
    model = DelayPredictionModel(
        blend_cur_dev=0.6,
        global_mean=50.0,
        tr_id_means={"131672": 51.85087719298246},
    )

    response = model.predict(_request(tr_id=131672, cur_dev_s=274.0))

    assert response.predicted_delay_s == pytest.approx(185.140350877193)
    assert response.risk_level == RiskLevel.RED
    assert response.pattern_reason == IncidentPattern.UNKNOWN_DELAY


def test_predict_uses_global_mean_for_unknown_vehicle():
    model = DelayPredictionModel(
        blend_cur_dev=0.6,
        global_mean=50.0,
        tr_id_means={},
    )

    response = model.predict(_request(tr_id=999999, cur_dev_s=10.0))

    assert response.predicted_delay_s == pytest.approx(26.0)
    assert response.risk_level == RiskLevel.GREEN
    assert response.pattern_reason is None


def test_predict_marks_low_speed_delay_as_traffic_jam():
    model = DelayPredictionModel(blend_cur_dev=1.0, global_mean=0.0, tr_id_means={})

    response = model.predict(
        _request(tr_id=131672, cur_dev_s=140.0, idle_time_s=90.0)
    )

    assert response.risk_level == RiskLevel.YELLOW
    assert response.pattern_reason == IncidentPattern.TRAFFIC_JAM

