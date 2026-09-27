import pytest
from ml.features import features
from test_api import payload

from commons.contracts.v1.ml.requests import MLPredictionRequest


def test_backend_contract_window_validation():
    data = payload()
    data["window_end_time"] = "2026-01-06T12:01:00Z"
    with pytest.raises(ValueError, match="window"):
        features(MLPredictionRequest.model_validate(data))
