from scipy.spatial.distance import jensenshannon


def detect_categorical_drift(
    baseline_proportions: dict[str, float],
    current_proportions: dict[str, float],
    current_count: int,
    threshold: float = 0.20,
    min_samples: int = 30,
) -> dict:
    """
    Compare a healthy categorical distribution with the current distribution
    using Jensen-Shannon distance.

    Drift is evaluated only when enough current observations are available.
    """

    if not baseline_proportions:
        raise ValueError("Baseline proportions cannot be empty.")

    if current_count < 0:
        raise ValueError("current_count cannot be negative.")

    if min_samples <= 0:
        raise ValueError("min_samples must be greater than 0.")

    categories = sorted(
        set(baseline_proportions)
        | set(current_proportions)
    )

    baseline = {
        category: baseline_proportions.get(category, 0.0)
        for category in categories
    }

    current = {
        category: current_proportions.get(category, 0.0)
        for category in categories
    }

    if current_count < min_samples:
        return {
            "categories": categories,
            "baseline_proportions": baseline,
            "current_proportions": current,
            "current_count": current_count,
            "min_samples": min_samples,
            "js_distance": None,
            "threshold": threshold,
            "drift_detected": False,
            "sufficient_data": False,
            "reason": "insufficient_samples",
        }

    if not current_proportions:
        raise ValueError(
            "Current proportions cannot be empty when enough samples exist."
        )

    baseline_values = list(baseline.values())
    current_values = list(current.values())

    distance = float(
        jensenshannon(
            baseline_values,
            current_values,
            base=2,
        )
    )

    return {
        "categories": categories,
        "baseline_proportions": baseline,
        "current_proportions": current,
        "current_count": current_count,
        "min_samples": min_samples,
        "js_distance": distance,
        "threshold": threshold,
        "drift_detected": distance > threshold,
        "sufficient_data": True,
        "reason": None,
    }
