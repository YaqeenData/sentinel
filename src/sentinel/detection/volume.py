from statistics import median


def detect_volume_drift(
    observed_count: int,
    baseline_counts: list[int],
    min_change_percent: float = 30.0,
    mad_multiplier: float = 3.0,
) -> dict:
    """Detect unusually low or high record counts."""

    if observed_count < 0:
        raise ValueError("observed_count cannot be negative.")

    if not baseline_counts:
        raise ValueError("baseline_counts cannot be empty.")

    if any(count < 0 for count in baseline_counts):
        raise ValueError("Baseline counts cannot be negative.")

    if min_change_percent < 0 or mad_multiplier < 0:
        raise ValueError("Thresholds cannot be negative.")

    expected_count = median(baseline_counts)
    deviations = [
        abs(count - expected_count)
        for count in baseline_counts
    ]
    mad = median(deviations)

    # Use a minimum of 1 to avoid a zero threshold.
    statistical_threshold = max(1.0, mad_multiplier * mad)
    percentage_threshold = expected_count * min_change_percent / 100
    threshold = max(statistical_threshold, percentage_threshold)

    difference = observed_count - expected_count
    is_anomaly = abs(difference) > threshold

    if not is_anomaly:
        direction = "normal"
        severity = "none"
    elif difference < 0:
        direction = "drop"
        severity = "high" if expected_count > 0 and observed_count < expected_count * 0.5 else "medium"
    else:
        direction = "spike"
        severity = "high" if expected_count > 0 and observed_count > expected_count * 1.5 else "medium"

    change_percent = (
        (difference / expected_count) * 100
        if expected_count > 0
        else None
    )

    return {
        "detector": "volume_drift",
        "observed_count": observed_count,
        "expected_count": expected_count,
        "threshold": threshold,
        "difference": difference,
        "change_percent": change_percent,
        "is_anomaly": is_anomaly,
        "direction": direction,
        "severity": severity,
    }
