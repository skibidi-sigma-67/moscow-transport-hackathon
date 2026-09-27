from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from ml.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def request():
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    return {
        "tr_id": 1,
        "target_stop_id": 1,
        "current_time_T": now.isoformat(),
        "target_time_begin": (now + timedelta(seconds=720)).isoformat(),
        "cur_dev_s": -40,
        "cur_dev_source": "provided",
        "recent_telemetry": [
            {
                "timestamp": now.isoformat(),
                "longitude": 37,
                "latitude": 55,
                "speed": 20,
                "course": 90,
            }
        ],
    }


def test_api_future_invariance_and_status(client):
    r = request()
    a = client.post("/predict", json=r)
    assert a.status_code == 200
    assert 0 <= a.json()["p_late"] <= 1
    r["recent_telemetry"].append(
        {
            "timestamp": "2026-01-06T12:01:00Z",
            "longitude": 38,
            "latitude": 56,
            "speed": 100,
            "course": 90,
        }
    )
    b = client.post("/predict", json=r)
    assert a.json()["predicted_delay_s"] == b.json()["predicted_delay_s"]
    r["cur_dev_s"] = None
    r["recent_telemetry"] = []
    assert client.post("/predict", json=r).json()["status"] == "UNAVAILABLE"
    r["target_time_begin"] = "2026-01-06T12:10:00Z"
    assert client.post("/predict", json=r).json()["status"] == "NO_TARGET"
    assert client.get("/health").status_code == 200
