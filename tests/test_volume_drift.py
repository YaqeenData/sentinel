import pytest

from sentinel.detection.volume import detect_volume_drift


BASELINE = [95, 100, 105, 98, 102]


def test_detects_volume_drop():
    result = detect_volume_drift(25, BASELINE)

    assert result["is_anomaly"] is True
    assert result["direction"] == "drop"
    assert result["severity"] == "high"
    assert result["observed_count"] == 25
    assert result["expected_count"] == 100


def test_detects_volume_spike():
    result = detect_volume_drift(180, BASELINE)

    assert result["is_anomaly"] is True
    assert result["direction"] == "spike"
    assert result["severity"] == "high"


def test_normal_volume_does_not_trigger_alert():
    result = detect_volume_drift(110, BASELINE)

    assert result["is_anomaly"] is False
    assert result["direction"] == "normal"
    assert result["severity"] == "none"


def test_empty_baseline_raises_error():
    with pytest.raises(ValueError):
        detect_volume_drift(100, [])


def test_negative_observed_count_raises_error():
    with pytest.raises(ValueError):
        detect_volume_drift(-1, BASELINE)
