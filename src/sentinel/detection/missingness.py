from statistics import median


def detect_missingness_spike(
    observed_null_rate: float,
    baseline_null_rates: list[float],
    min_increase: float = 0.10,
    mad_multiplier: float = 3.0,
) -> dict:
    """Detect an unusual increase in a field's null rate.

    Rates are proportions between 0.0 and 1.0.
    For example, 0.10 means 10%.
    """

    if not 0.0 <= observed_null_rate <= 1.0:
        raise ValueError("observed_null_rate must be between 0 and 1.")

    if not baseline_null_rates:
        raise ValueError("baseline_null_rates cannot be empty.")

    if any(not 0.0 <= rate <= 1.0 for rate in baseline_null_rates):
        raise ValueError("Baseline null rates must be between 0 and 1.")

    if min_increase < 0 or mad_multiplier < 0:
        raise ValueError("Thresholds cannot be negative.")

    baseline_rate = median(baseline_null_rates)
    deviations = [
        abs(rate - baseline_rate)
        for rate in baseline_null_rates
    ]
    mad = median(deviations)

    statistical_threshold = mad_multiplier * mad
    threshold = max(min_increase, statistical_threshold)

    increase = observed_null_rate - baseline_rate
    is_anomaly = increase > threshold

    if not is_anomaly:
        severity = "none"
    elif increase >= 0.30:
        severity = "high"
    else:
        severity = "medium"

    return {
        "detector": "missingness",
        "observed_null_rate": observed_null_rate,
        "baseline_null_rate": baseline_rate,
        "threshold": threshold,
        "increase": increase,
        "is_anomaly": is_anomaly,
        "severity": severity,
    }
