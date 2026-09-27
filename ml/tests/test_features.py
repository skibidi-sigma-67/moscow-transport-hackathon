import math

from ml.data.dataset import seconds

from commons.ml_features import (
    Observation,
    Stop,
    features,
    reconstruct_deviation,
    select_target,
    sequence,
)

NOW = 1767665400.0
STOP = Stop(NOW + 720, 37.1, 55.1, 1)
HISTORY = [
    Observation(NOW - 30, 37.0, 55.0, 10, 90),
    Observation(NOW - 10, 37.01, 55.01, 0, 90),
]


def same(a, b):
    assert a.keys() == b.keys()
    for k in a:
        assert a[k] == b[k] or (math.isnan(a[k]) and math.isnan(b[k]))


def test_future_and_invalid_points_do_not_change_features():
    extra = [
        Observation(NOW + 1, 38, 56, 100),
        Observation(NOW - 5, 0, 0, 999),
        Observation(NOW - 3, 37, 55, 20, valid=False),
    ]
    same(
        features(HISTORY, [STOP], STOP, NOW, 20),
        features(HISTORY + extra, [STOP], STOP, NOW, 20),
    )
    assert sequence(HISTORY, NOW) == sequence(HISTORY + extra, NOW)


def test_order_duplicates():
    same(
        features(HISTORY, [STOP], STOP, NOW),
        features(list(reversed(HISTORY)) * 2, [STOP], STOP, NOW),
    )


def test_target_boundaries():
    assert select_target([Stop(NOW + 600, 0, 0, 1)], NOW) is None
    assert select_target([Stop(NOW + 900, 0, 0, 2)], NOW).stop_id == 2
    assert select_target([Stop(NOW + 901, 0, 0, 3)], NOW) is None


def test_missing_and_gap_are_not_idle():
    f = features([Observation(NOW - 800, 37, 55, 0)], [STOP], STOP, NOW)
    assert f["coverage_900"] == 30 / 900
    assert f["gps_age_s"] == 800
    assert math.isnan(f["cur_dev_s"])
    assert f["cur_dev_missing"] == 1


def test_confirm_and_ambiguous_visits():
    rows = [Observation(NOW - 20, 37, 55, 0), Observation(NOW - 10, 37, 55, 0)]
    s = Stop(NOW - 50, 37, 55, 10)
    assert reconstruct_deviation(rows, [s], NOW) == (30, 20)
    assert reconstruct_deviation(rows, [s, Stop(NOW - 300, 37, 55, 11)], NOW) == (
        None,
        None,
    )


def test_timestamp_seconds():
    import pandas as pd

    assert seconds(pd.Series(["2026-01-06 02:10:00"])).iloc[0] == NOW
