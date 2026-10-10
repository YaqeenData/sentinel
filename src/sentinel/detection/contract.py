"""
Contract validation for normalized Observation rows.

Answers one question: does each row follow the agreed data contract?
  - required fields are present (not None / empty)
  - status is one of the allowed FHIR values
  - the value matches its value_type (e.g. numeric_value is really a number)

No baseline is needed: a contract violation is wrong by definition.

The detector returns ONE result per (field, problem) per window,
not one result per bad row, so the dashboard is not flooded.
"""

from collections import defaultdict


DETECTOR_NAME = "contract"

# Fields every normalized row must have.
REQUIRED_FIELDS = [
    "observation_id",
    "patient_id",
    "status",
    "code",
    "value_type",
]

# Allowed values for Observation.status in FHIR R4.
ALLOWED_STATUSES = {
    "registered",
    "preliminary",
    "final",
    "amended",
    "corrected",
    "cancelled",
    "entered-in-error",
    "unknown",
}

ALLOWED_VALUE_TYPES = {"numeric", "categorical", "string"}


def is_number(value) -> bool:
    """True for int or float. bool is excluded because True is an int in Python."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def type_name(value) -> str:
    """Readable type name for evidence, e.g. 'str', 'NoneType'."""
    return type(value).__name__


def find_violations(row: dict) -> list[tuple[str, str, str, str]]:
    """
    Check one normalized row against the contract.

    Returns a list of violations, each as:
        (field_name, incident_type, expected, observed)
    An empty list means the row is valid.
    """
    violations = []

    # 1. Required fields
    for field in REQUIRED_FIELDS:
        if row.get(field) in (None, ""):
            violations.append((field, "missing_required_field", "present", "missing"))

    # 2. Allowed status values
    status = row.get("status")
    if status is not None and status not in ALLOWED_STATUSES:
        violations.append(("status", "invalid_value", "allowed FHIR status", str(status)))

    # 3. Value must match its value_type
    value_type = row.get("value_type")

    if value_type is not None and value_type not in ALLOWED_VALUE_TYPES:
        violations.append(("value_type", "invalid_value", "numeric/categorical/string", str(value_type)))

    elif value_type == "numeric":
        value = row.get("numeric_value")
        if value is None:
            violations.append(("numeric_value", "missing_required_field", "number", "missing"))
        elif not is_number(value):
            violations.append(("numeric_value", "type_mismatch", "number", type_name(value)))

    elif value_type == "categorical":
        if not isinstance(row.get("categorical_code"), str):
            violations.append(("categorical_code", "type_mismatch", "str", type_name(row.get("categorical_code"))))

    elif value_type == "string":
        if not isinstance(row.get("string_value"), str):
            violations.append(("string_value", "type_mismatch", "str", type_name(row.get("string_value"))))

    return violations


def check(rows: list[dict], window: dict, baseline: dict | None = None) -> list[dict]:
    """
    Validate all rows in one window and return aggregated results.

    rows:     normalized Observation rows (output of normalize_observation)
    window:   {"resource_type": ..., "window_start": ..., "window_end": ...}
    baseline: not used by this detector; kept so every detector has the same signature
    """
    total = len(rows)

    # (field, incident_type, expected) -> {"count": n, "observed": {...}, "examples": [...]}
    grouped = defaultdict(lambda: {"count": 0, "observed": set(), "examples": []})

    for row in rows:
        for field, incident_type, expected, observed in find_violations(row):
            group = grouped[(field, incident_type, expected)]
            group["count"] += 1
            group["observed"].add(observed)
            if len(group["examples"]) < 3:
                group["examples"].append(row.get("observation_id"))

    results = []

    for (field, incident_type, expected), group in grouped.items():
        results.append({
            "detector": DETECTOR_NAME,
            "resource_type": window.get("resource_type", "Observation"),
            "field_name": field,
            "incident_type": incident_type,
            "baseline_value": expected,
            "current_value": ", ".join(sorted(group["observed"])),
            "is_anomaly": True,
            "severity": "critical",
            "window_start": window.get("window_start"),
            "window_end": window.get("window_end"),
            "evidence": {
                "bad_rows": group["count"],
                "total_rows": total,
                "example_observation_ids": group["examples"],
            },
        })

    # Healthy window: still return one result so the dashboard can show "all good".
    if not results:
        results.append({
            "detector": DETECTOR_NAME,
            "resource_type": window.get("resource_type", "Observation"),
            "field_name": None,
            "incident_type": "contract_ok",
            "baseline_value": None,
            "current_value": None,
            "is_anomaly": False,
            "severity": "info",
            "window_start": window.get("window_start"),
            "window_end": window.get("window_end"),
            "evidence": {"bad_rows": 0, "total_rows": total},
        })

    return results