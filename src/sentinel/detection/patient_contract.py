"""
Contract validation for normalized Patient rows.

Same shape as detection/contract.py (Observation), with Patient rules:
  - required fields are present: patient_id, gender, birth_date
  - gender is one of the allowed FHIR values
  - birth_date is a string, a valid date, and not in the future
  - marital_status_code, when present, is an allowed FHIR value

No baseline is needed: a contract violation is wrong by definition.

The detector returns ONE result per (field, problem) per window,
not one result per bad row, so the dashboard is not flooded.
"""

from collections import defaultdict
from datetime import date


DETECTOR_NAME = "contract"
RESOURCE_TYPE = "Patient"

# Fields every normalized Patient row must have.
REQUIRED_FIELDS = [
    "patient_id",
    "gender",
    "birth_date",
]

# Allowed values for Patient.gender in FHIR R4.
ALLOWED_GENDERS = {"male", "female", "other", "unknown"}

# Allowed codes for Patient.maritalStatus (HL7 v3 MaritalStatus + NullFlavor UNK).
ALLOWED_MARITAL_STATUSES = {
    "A", "D", "I", "L", "M", "C", "P", "T", "U", "S", "W", "UNK",
}


def type_name(value) -> str:
    """Readable type name for evidence, e.g. 'str', 'int'."""
    return type(value).__name__


def parse_date(value: str) -> date | None:
    """Parse the date part of a FHIR date string. None if it is not a valid date."""
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def find_violations(
    row: dict,
    today: date | None = None,
) -> list[tuple[str, str, str, str]]:
    """
    Check one normalized Patient row against the contract.

    Returns a list of violations, each as:
        (field_name, incident_type, expected, observed)
    An empty list means the row is valid.
    """
    today = today or date.today()
    violations = []

    # 1, 2, 4. Required fields
    for field in REQUIRED_FIELDS:
        if row.get(field) in (None, ""):
            violations.append((field, "missing_required_field", "present", "missing"))

    # 3. Allowed gender values
    gender = row.get("gender")
    if gender not in (None, "") and gender not in ALLOWED_GENDERS:
        violations.append(("gender", "invalid_value", "allowed FHIR gender", str(gender)))

    # 5, 6. birth_date must be a valid date string, not in the future
    birth_date = row.get("birth_date")
    if birth_date not in (None, ""):
        if not isinstance(birth_date, str):
            violations.append(("birth_date", "type_mismatch", "str", type_name(birth_date)))
        else:
            born = parse_date(birth_date)
            if born is None:
                violations.append(("birth_date", "invalid_value", "valid date", birth_date))
            elif born > today:
                violations.append(("birth_date", "invalid_value", "date not in future", birth_date))

    # 8. Allowed marital status codes (optional field)
    marital = row.get("marital_status_code")
    if marital not in (None, "") and marital not in ALLOWED_MARITAL_STATUSES:
        violations.append((
            "marital_status_code", "invalid_value", "allowed FHIR marital status", str(marital),
        ))

    return violations


def check(rows: list[dict], window: dict, baseline: dict | None = None) -> list[dict]:
    """
    Validate all Patient rows in one window and return aggregated results.

    rows:     normalized Patient rows (output of normalize_patient)
    window:   {"window_start": ..., "window_end": ...}
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
                group["examples"].append(row.get("patient_id") or "missing-id")

    results = []

    for (field, incident_type, expected), group in grouped.items():
        results.append({
            "detector": DETECTOR_NAME,
            "resource_type": RESOURCE_TYPE,
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
                "example_patient_ids": group["examples"],
            },
        })

    # Healthy window: still return one result so the dashboard can show "all good".
    if not results:
        results.append({
            "detector": DETECTOR_NAME,
            "resource_type": RESOURCE_TYPE,
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