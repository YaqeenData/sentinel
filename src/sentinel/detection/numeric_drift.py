"""
Numeric distribution drift for monitored Observation codes.

Answers one question: did the distribution of a numeric value change
compared with the healthy baseline?

Rule: drift = KS test is significant AND the KS statistic passes a
practical guardrail (so tiny shifts in large windows do not alert).

Same signature and result shape as the other detectors.
One result per monitored code per window.
"""

import numpy as np
from scipy.stats import ks_2samp


DETECTOR_NAME = "numeric_drift"
FIELD_NAME = "numeric_value"

# Measurements we monitor (LOINC code -> readable name).
MONITORED_CODES = {
    "8867-4": "Heart rate",
    "8480-6": "Systolic Blood Pressure",
    "2339-0": "Glucose",
}

ALPHA = 0.05        # KS p-value below this = the difference is not chance
MIN_EFFECT = 0.15   # KS statistic at or above this = the difference is big enough to matter
MIN_SAMPLES = 30    # fewer current values than this = not enough data to judge


def is_number(value) -> bool:
    """True for int or float. bool is excluded because True is an int in Python."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def detect_drift(reference, current, alpha: float = ALPHA, min_effect: float = MIN_EFFECT) -> dict:
    """Compare two sets of numbers. Pure statistics, no pipeline knowledge."""
    reference = np.asarray(reference, dtype=float)
    current = np.asarray(current, dtype=float)
    result = ks_2samp(reference, current)

    significant = bool(result.pvalue < alpha)
    practical = bool(result.statistic >= min_effect)

    return {
        "drift_detected": significant and practical,
        "ks_statistic": round(float(result.statistic), 4),
        "p_value": float(result.pvalue),
        "significant": significant,
        "practical": practical,
        "reference_median": float(np.median(reference)),
        "current_median": float(np.median(current)),
    }


def _result(window: dict, incident_type: str, is_anomaly: bool, severity: str,
            baseline_value, current_value, evidence: dict) -> dict:
    """Build one result in the shape every detector returns."""
    return {
        "detector": DETECTOR_NAME,
        "resource_type": window.get("resource_type", "Observation"),
        "field_name": FIELD_NAME,
        "incident_type": incident_type,
        "baseline_value": baseline_value,
        "current_value": current_value,
        "is_anomaly": is_anomaly,
        "severity": severity,
        "window_start": window.get("window_start"),
        "window_end": window.get("window_end"),
        "evidence": evidence,
    }


def check_code(code: str, rows: list[dict], window: dict, reference) -> dict:
    """Check one monitored code in one window and return one result."""
    current = [
        row["numeric_value"]
        for row in rows
        if row.get("code") == code and is_number(row.get("numeric_value"))
    ]
    reference = reference or []

    evidence = {
        "code": code,
        "name": MONITORED_CODES.get(code),
        "reference_n": len(reference),
        "current_n": len(current),
    }

    if not reference:
        return _result(window, "no_baseline", False, "info", None, None, evidence)

    if len(current) < MIN_SAMPLES:
        evidence["min_samples"] = MIN_SAMPLES
        return _result(window, "insufficient_data", False, "info", None, None, evidence)

    stats = detect_drift(reference, current)
    evidence.update({
        "test": "ks_2samp",
        "ks_statistic": stats["ks_statistic"],
        "p_value": stats["p_value"],
        "alpha": ALPHA,
        "significant": stats["significant"],
        "guardrail_min_effect": MIN_EFFECT,
        "guardrail_passed": stats["practical"],
        "median_shift": round(stats["current_median"] - stats["reference_median"], 2),
    })

    if stats["drift_detected"]:
        return _result(window, "distribution_drift", True, "warning",
                       stats["reference_median"], stats["current_median"], evidence)

    return _result(window, "numeric_drift_ok", False, "info",
                   stats["reference_median"], stats["current_median"], evidence)


def check(rows: list[dict], window: dict, baseline: dict | None = None) -> list[dict]:
    """
    Check every monitored code in one window.

    rows:     normalized Observation rows (output of normalize_observation)
    window:   {"resource_type": ..., "window_start": ..., "window_end": ...}
    baseline: {code: [healthy numeric values]}, e.g. {"8867-4": [72.0, 80.0, ...]}
    """
    baseline = baseline or {}
    return [check_code(code, rows, window, baseline.get(code)) for code in MONITORED_CODES]


def demo(baseline: dict, n: int = 200) -> None:
    """Check a healthy window, then drift each monitored code in turn and check again."""
    from sentinel.injection.numeric_drift import inject_record, sample_healthy, shift_for

    window = {"resource_type": "Observation", "window_start": "demo", "window_end": "demo"}

    def make_rows(seed: int) -> list[dict]:
        rows = []
        for code in MONITORED_CODES:
            for value in sample_healthy(baseline[code], n=n, seed=seed):
                rows.append({"code": code, "value_type": "numeric", "numeric_value": float(value)})
        return rows

    def show(title: str, rows: list[dict]) -> None:
        print(f"\n--- {title} ---")
        print(f"{'name':<26}{'incident_type':<22}{'anomaly':<9}{'D':>7}{'median_shift':>14}")
        for result in check(rows, window, baseline):
            evidence = result["evidence"]
            print(f"{evidence['name']:<26}{result['incident_type']:<22}{str(result['is_anomaly']):<9}"
                  f"{evidence['ks_statistic']:>7.3f}{evidence['median_shift']:>14.2f}")

    show("HEALTHY WINDOW (nothing injected)", make_rows(seed=42))

    for drifted_code, name in MONITORED_CODES.items():
        shift = shift_for(baseline[drifted_code])
        drifted_rows = [inject_record(row, drifted_code, shift) for row in make_rows(seed=43)]
        show(f"DRIFTED WINDOW ({name} shifted by {shift})", drifted_rows)


if __name__ == "__main__":
    from sentinel.injection.numeric_drift import load_baseline

    demo(load_baseline())