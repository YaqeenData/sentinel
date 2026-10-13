"""
Contract validation for normalized Encounter rows.

Same shape as the Patient and Observation contracts, with Encounter rules:
  - required fields are present: encounter_id, patient_id, status,
    class_code, start_time
  - status is one of the allowed FHIR Encounter.status values
  - class_code is one of the allowed FHIR encounter class codes
  - start_time is a valid date-time and not in the future
  - end_time, when present, is a valid date-time not before start_time
  - encounter_id is not repeated inside the same window (stored as invalid_value)

No baseline is needed: a contract violation is wrong by definition.

Why this matters for drift: the Encounter class drift detector compares the
class_code mix with Silver. An unknown or missing class_code is a broken
record, not drift, so the contract reports it separately.

The detector returns ONE result per (field, problem) per window,
not one result per bad row, so the dashboard is not flooded.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone


DETECTOR_NAME = "contract"
RESOURCE_TYPE = "Encounter"

# Fields every normalized Encounter row must have.
REQUIRED_FIELDS = [
    "encounter_id",
    "patient_id",
    "status",
    "class_code",
    "start_time",
]

# Allowed values for Encounter.status in FHIR R4.
ALLOWED_STATUSES = {
    "planned",
    "arrived",
    "triaged",
    "in-progress",
    "onleave",
    "finished",
    "cancelled",
    "entered-in-error",
    "unknown",
}

# Allowed codes for Encounter.class in FHIR R4 (v3 ActEncounterCode).
ALLOWED_CLASS_CODES = {
    "AMB",     # ambulatory
    "EMER",    # emergency
    "FLD",     # field
    "HH",      # home health
    "IMP",     # inpatient encounter
    "ACUTE",   # inpatient acute
    "NONAC",   # inpatient non-acute
    "OBSENC",  # observation encounter
    "PRENC",   # pre-admission
    "SS",      # short stay
    "VR",      # virtual
}


def type_name(value) -> str:
    """Readable type name for evidence, e.g. 'str', 'int'."""
    return type(value).__name__


def parse_datetime(value: str) -> datetime | None:
    """
    Parse a FHIR dateTime string. None if it is not a valid date-time.

    A value without a time zone is treated as UTC so it can be compared
    with now and with the other period bound.
    """
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _check_datetime(row: dict, field: str, violations: list) -> datetime | None:
    """
    Validate one date-time field. Adds violations, returns the parsed value
    (or None when the field is empty or broken).
    """
    value = row.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        violations.append((field, "type_mismatch", "str", type_name(value)))
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        violations.append((field, "invalid_value", "valid date-time", value))
    return parsed


def find_violations(
    row: dict,
    now: datetime | None = None,
) -> list[tuple[str, str, str, str]]:
    """
    Check one normalized Encounter row against the contract.

    Returns a list of violations, each as:
        (field_name, incident_type, expected, observed)
    An empty list means the row is valid.
    """
    now = now or datetime.now(timezone.utc)
    violations = []

    # 1. Required fields
    for field in REQUIRED_FIELDS:
        if row.get(field) in (None, ""):
            violations.append((field, "missing_required_field", "present", "missing"))

    # 2. Allowed status values
    status = row.get("status")
    if status not in (None, "") and status not in ALLOWED_STATUSES:
        violations.append(("status", "invalid_value", "allowed FHIR status", str(status)))

    # 3. Allowed class codes
    class_code = row.get("class_code")
    if class_code not in (None, "") and class_code not in ALLOWED_CLASS_CODES:
        violations.append(("class_code", "invalid_value", "allowed FHIR encounter class", str(class_code)))

    # 4. start_time: valid date-time, not in the future
    start = _check_datetime(row, "start_time", violations)
    if start is not None and start > now:
        violations.append(("start_time", "invalid_value", "date-time not in future", row["start_time"]))

    # 5. end_time (optional): valid date-time, not before start_time
    end = _check_datetime(row, "end_time", violations)
    if start is not None and end is not None and end < start:
        violations.append(("end_time", "invalid_value", "not before start_time", row["end_time"]))

    return violations


def check(rows: list[dict], window: dict, baseline: dict | None = None) -> list[dict]:
    """
    Validate all Encounter rows in one window and return aggregated results.

    rows:     normalized Encounter rows (output of normalize_encounter)
    window:   {"window_start": ..., "window_end": ...}
    baseline: not used by this detector; kept so every detector has the same signature
    """
    total = len(rows)

    # (field, incident_type, expected) -> {"count": n, "observed": {...}, "examples": [...]}
    grouped = defaultdict(lambda: {"count": 0, "observed": set(), "examples": []})

    def record(field, incident_type, expected, observed, example):
        group = grouped[(field, incident_type, expected)]
        group["count"] += 1
        group["observed"].add(observed)
        if len(group["examples"]) < 3:
            group["examples"].append(example)

    for row in rows:
        for field, incident_type, expected, observed in find_violations(row):
            record(field, incident_type, expected, observed, row.get("encounter_id") or "missing-id")

    # 6. Duplicate encounter_id in the same window (e.g. a Kafka message
    #    delivered twice). Needs the whole window, so it is checked here,
    #    not in find_violations. Every extra copy counts as one bad row.
    #    Stored as invalid_value: the schema and the monitor only know the
    #    three contract incident types, and (invalid_value, encounter_id)
    #    never clashes with another Encounter rule.
    ids = Counter(row.get("encounter_id") for row in rows if row.get("encounter_id") not in (None, ""))
    for encounter_id, seen in ids.items():
        for _ in range(seen - 1):
            record("encounter_id", "invalid_value", "unique per window", f"{seen}x", encounter_id)

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
                "example_encounter_ids": group["examples"],
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