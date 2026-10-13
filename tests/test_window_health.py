from datetime import datetime, timezone

from sentinel.streaming.health import persist_window_health, window_health_metrics
from sentinel.streaming.windows import Window


START = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 13, 9, 1, tzinfo=timezone.utc)


def make_window(rows):
    return Window(window_start=START, window_end=END, rows=rows)


def test_metrics_for_a_window():
    window = make_window(
        [
            {"value_type": "numeric", "numeric_value": 72.0},
            {"value_type": "numeric", "numeric_value": None},
            {"value_type": "categorical", "numeric_value": None},
            {"value_type": "numeric", "numeric_value": 120.0},
        ]
    )

    metrics = {m["metric_name"]: m for m in window_health_metrics(window)}

    assert metrics["record_count"]["metric_value"] == 4
    assert metrics["record_count"]["field_name"] is None
    # 1 missing value out of 3 numeric rows; the categorical row is not counted
    assert metrics["null_rate"]["metric_value"] == 1 / 3
    assert metrics["null_rate"]["field_name"] == "numeric_value"


def test_empty_window_has_zero_null_rate():
    metrics = {m["metric_name"]: m for m in window_health_metrics(make_window([]))}

    assert metrics["record_count"]["metric_value"] == 0
    assert metrics["null_rate"]["metric_value"] == 0.0


def test_persist_writes_both_metrics_with_window_bounds():
    calls = []

    def fake_save(**kwargs):
        calls.append(kwargs)
        return len(calls)

    window = make_window([{"value_type": "numeric", "numeric_value": 1.0}])
    persist_window_health(window, save=fake_save)

    assert [c["metric_name"] for c in calls] == ["record_count", "null_rate"]
    for call in calls:
        assert call["resource_type"] == "Observation"
        assert call["window_start"] == START
        assert call["window_end"] == END
