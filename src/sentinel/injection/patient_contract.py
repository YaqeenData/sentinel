from copy import deepcopy
from typing import Any


PATIENT_ERROR_KINDS = (
    "missing_patient_id",
    "missing_gender",
    "invalid_gender",
    "missing_birth_date",
    "birth_date_as_number",
    "future_birth_date",
    "invalid_marital_status",
)

INVALID_GENDER = "x"
FUTURE_BIRTH_DATE = "2099-01-01"
INVALID_MARITAL_STATUS = "Z"


def _birth_date_as_number(birth_date: Any) -> Any:
    """
    Turn "1980-01-01" into 19800101.

    Returns the value unchanged if it is not a date string.
    """

    if not isinstance(birth_date, str):
        return birth_date

    digits = birth_date.replace("-", "")

    return int(digits) if digits.isdigit() else birth_date


def _set_marital_code(patient: dict[str, Any], code: str) -> None:
    """Replace every maritalStatus coding code with the given code."""

    marital_status = patient.get("maritalStatus")

    if not isinstance(marital_status, dict):
        return

    for coding in marital_status.get("coding") or []:
        if isinstance(coding, dict):
            coding["code"] = code


def corrupt_patient(
    patient: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    """
    Return a copy of one raw FHIR Patient with one contract error.

    Kinds (rule broken)
    -------------------
    missing_patient_id      (1) removes id
    missing_gender          (2) removes gender
    invalid_gender          (3) gender outside male/female/other/unknown
    missing_birth_date      (4) removes birthDate
    birth_date_as_number    (5) birthDate stored as a number
    future_birth_date       (6) birthDate in the future
    invalid_marital_status  (8) marital status code outside FHIR values

    The original Patient is not modified.
    """

    if kind not in PATIENT_ERROR_KINDS:
        raise ValueError(
            f"Unknown Patient error kind: {kind}. "
            f"Expected one of {PATIENT_ERROR_KINDS}."
        )

    corrupted = deepcopy(patient)

    if corrupted.get("resourceType") != "Patient":
        return corrupted

    if kind == "missing_patient_id":
        corrupted.pop("id", None)

    elif kind == "missing_gender":
        corrupted.pop("gender", None)

    elif kind == "invalid_gender":
        corrupted["gender"] = INVALID_GENDER

    elif kind == "missing_birth_date":
        corrupted.pop("birthDate", None)

    elif kind == "birth_date_as_number":
        corrupted["birthDate"] = _birth_date_as_number(
            corrupted.get("birthDate")
        )

    elif kind == "future_birth_date":
        corrupted["birthDate"] = FUTURE_BIRTH_DATE

    elif kind == "invalid_marital_status":
        _set_marital_code(corrupted, INVALID_MARITAL_STATUS)

    return corrupted