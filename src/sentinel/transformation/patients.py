"""
Normalize FHIR Patient resources into Silver rows.

"""

from sentinel.transformation.observations import get_code_info


def first_item(items: list | None) -> dict:
    if not items:
        return {}

    return items[0]


def normalize_patient(patient: dict) -> list[dict]:
   
    address = first_item(patient.get("address"))
    communication = first_item(patient.get("communication"))

    marital_code, marital_display = get_code_info(
        patient.get("maritalStatus", {})
    )

    language_code, language_display = get_code_info(
        communication.get("language", {})
    )

    row = {
        "patient_id": patient.get("id"),
        "gender": patient.get("gender"),
        "birth_date": patient.get("birthDate"),
        "deceased_time": patient.get("deceasedDateTime"),
        "marital_status_code": marital_code,
        "marital_status_display": marital_display,
        "city": address.get("city"),
        "state": address.get("state"),
        "postal_code": address.get("postalCode"),
        "country": address.get("country"),
        "language_code": language_code,
        "language_display": language_display,
    }

    return [row]