import pytest

from sentinel.detection.missingness import detect_missingness_spike


BASELINE = [0.01, 0.02, 0.03, 0.02, 0.01]


def test_detects_null_spike():
    result = detect_missingness_spike(0.30, BASELINE)

    assert result["is_anomaly"] is True
    assert result["observed_null_rate"] == 0.30
    assert result["baseline_null_rate"] == 0.02
    assert result["severity"] == "medium"


def test_normal_null_rate_does_not_trigger_alert():
    result = detect_missingness_spike(0.05, BASELINE)

    assert result["is_anomaly"] is False
    assert result["severity"] == "none"


def test_large_null_spike_is_high_severity():
    result = detect_missingness_spike(0.50, BASELINE)

    assert result["is_anomaly"] is True
    assert result["severity"] == "high"


def test_empty_baseline_raises_error():
    with pytest.raises(ValueError):
        detect_missingness_spike(0.20, [])


def test_invalid_observed_rate_raises_error():
    with pytest.raises(ValueError):
        detect_missingness_spike(1.2, BASELINE)


def test_invalid_baseline_rate_raises_error():
    with pytest.raises(ValueError):
        detect_missingness_spike(0.20, [0.01, 1.5])
