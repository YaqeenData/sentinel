"""
Contract errors for raw FHIR Encounters (live injection).

Same shape as injection/patient_contract.py: each kind breaks exactly one
rule of detection/encounter_contract.py, on the raw FHIR resource, before
it reaches Kafka.

Duplicate encounter_id (rule 6) is not injected here: a transform gets one
Encounter and returns one, so it cannot send the same message twice.
"""

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any


ENCOUNTER_ERROR_KINDS = (
    "missing_encounter_id",
    "missing_patient",
    "missing_status",
    "invalid_status",
    "missing_class",
    "invalid_class",
    "missing_start",
    "start_as_number",
    "future_start",
    "end_before_start",
)

INVALID_STATUS = "done"
INVALID_CLASS = "XYZ"
FUTURE_START = "2099-01-01T10:00:00+00:00"
FUTURE_END = "2099-01-01T11:00:00+00:00"


def _start_as_number(start: Any) -> Any:
    """
    Turn "2020-01-01T10:00:00+03:00" into 20200101.

    Returns the value unchanged if it is not a date string.
    """

    if not isinstance(start, str):
        return start

    digits = start[:10].replace("-", "")

    return int(digits) if digits.isdigit() else start


def _day_before(start: Any) -> str | None:
    """One day before a FHIR dateTime string, or None if it cannot be read."""

    if not isinstance(start, str):
        return None

    try:
        moment = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        return None

    return (moment - timedelta(days=1)).isoformat()


def corrupt_encounter(
    encounter: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    """
    Return a copy of one raw FHIR Encounter with one contract error.

    Kinds (rule broken)
    -------------------
    missing_encounter_id  (1) removes id
    missing_patient       (1) removes subject, so patient_id is empty
    missing_status        (1) removes status
    invalid_status        (2) status outside the FHIR values
    missing_class         (1) removes class
    invalid_class         (3) class code outside the FHIR values
    missing_start         (1) removes period.start
    start_as_number       (4) period.start stored as a number
    future_start          (4) period.start in the future (end moved with it)
    end_before_start      (5) period.end one day before period.start

    The original Encounter is not modified.
    """

    if kind not in ENCOUNTER_ERROR_KINDS:
        raise ValueError(
            f"Unknown Encounter error kind: {kind}. "
            f"Expected one of {ENCOUNTER_ERROR_KINDS}."
        )

    corrupted = deepcopy(encounter)

    if corrupted.get("resourceType") != "Encounter":
        return corrupted

    period = corrupted.get("period")
    if not isinstance(period, dict):
        period = {}
        corrupted["period"] = period

    if kind == "missing_encounter_id":
        corrupted.pop("id", None)

    elif kind == "missing_patient":
        corrupted.pop("subject", None)

    elif kind == "missing_status":
        corrupted.pop("status", None)

    elif kind == "invalid_status":
        corrupted["status"] = INVALID_STATUS

    elif kind == "missing_class":
        corrupted.pop("class", None)

    elif kind == "invalid_class":
        encounter_class = corrupted.get("class")
        if isinstance(encounter_class, dict):
            encounter_class["code"] = INVALID_CLASS
        else:
            corrupted["class"] = {"code": INVALID_CLASS}

    elif kind == "missing_start":
        period.pop("start", None)

    elif kind == "start_as_number":
        period["start"] = _start_as_number(period.get("start"))

    elif kind == "future_start":
        # The end moves too, so only the "future" rule breaks,
        # not "end before start".
        period["start"] = FUTURE_START
        if "end" in period:
            period["end"] = FUTURE_END

    elif kind == "end_before_start":
        earlier = _day_before(period.get("start"))
        if earlier is not None:
            period["end"] = earlier

    return corrupted