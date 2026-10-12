"""
Numeric distribution drift for monitored Observation codes.

Answers one question: did the distribution of a numeric value change
compared with the healthy baseline?

Rule: drift = KS test is significant AND the KS statistic passes a
practical guardrail (so tiny shifts in large windows do not alert).

Severity follows chk_incidents_severity in sql/schema.sql:
low (no drift), then medium, high, critical by drift size.

Same signature and result shape as the other detectors.
One result per monitored code per window.
"""

import numpy as np
from scipy.stats import ks_2samp

from sentinel.profiling.numeric import profile_numeric


DETECTOR_NAME = "numeric_drift"
FIELD_NAME = "numeric_value"

# Measurements we monitor (LOINC code -> readable name).
MONITORED_CODES = {
    "8867-4": "Heart rate",
    "8480-6": "Systolic Blood Pressure",
    "2339-0": "Glucose",
}

ALPHA = 0.05            # KS p-value below this = the difference is not chance
MIN_EFFECT = 0.15       # KS statistic at or above this = the difference is big enough to matter
HIGH_EFFECT = 0.20      # KS statistic at or above this = the drift is large
CRITICAL_EFFECT = 0.25  # KS statistic at or above this = the drift is severe
MIN_SAMPLES = 30        # fewer current values than this = not enough data to judge


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


def severity_for(ks_statistic: float) -> str:
    """Map drift size to a level allowed by chk_incidents_severity in sql/schema.sql."""
    if ks_statistic >= CRITICAL_EFFECT:
        return "critical"
    if ks_statistic >= HIGH_EFFECT:
        return "high"
    if ks_statistic >= MIN_EFFECT:
        return "medium"
    return "low"


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
    code_rows = [row for row in rows if row.get("code") == code]
    profile = profile_numeric(code_rows, FIELD_NAME)

    current = profile["values"]
    reference = reference or []

    evidence = {
        "code": code,
        "name": MONITORED_CODES.get(code),
        "reference_n": len(reference),
        "current_n": profile["valid_count"],
        "null_count": profile["null_count"],
        "invalid_count": profile["invalid_count"],
    }

    if not reference:
        return _result(window, "no_baseline", False, "low", None, None, evidence)

    if len(current) < MIN_SAMPLES:
        evidence["min_samples"] = MIN_SAMPLES
        return _result(window, "insufficient_data", False, "low", None, None, evidence)

    stats = detect_drift(reference, current)
    evidence.update({
        "test": "ks_2samp",
        "ks_statistic": stats["ks_statistic"],
        "p_value": stats["p_value"],
        "alpha": ALPHA,
        "significant": stats["significant"],
        "guardrail_min_effect": MIN_EFFECT,
        "guardrail_passed": stats["practical"],
        "high_effect": HIGH_EFFECT,
        "critical_effect": CRITICAL_EFFECT,
        "median_shift": round(stats["current_median"] - stats["reference_median"], 2),
    })

    if stats["drift_detected"]:
        return _result(window, "distribution_drift", True, severity_for(stats["ks_statistic"]),
                       stats["reference_median"], stats["current_median"], evidence)

    return _result(window, "numeric_drift_ok", False, "low",
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