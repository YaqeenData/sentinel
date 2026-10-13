"""
Normalize FHIR Encounter resources into Silver rows.

"""
from sentinel.transformation.observations import (
    extract_reference_id,
    get_code_info,
)
from sentinel.transformation.patients import first_item


def normalize_encounter(encounter: dict) -> list[dict]:

    
    patient_id = extract_reference_id(
        encounter.get("subject", {}).get("reference")
    )

    
    type_code, type_display = get_code_info(
        first_item(encounter.get("type"))
    )

    reason_code, reason_display = get_code_info(
        first_item(encounter.get("reasonCode"))
    )

    period = encounter.get("period", {})

    row = {
        "encounter_id": encounter.get("id"),
        "patient_id": patient_id,
        "status": encounter.get("status"),
        # class is a single Coding (not a list), e.g. AMB, EMER, IMP
        "class_code": encounter.get("class", {}).get("code"),
        "type_code": type_code,
        "type_display": type_display,
        "start_time": period.get("start"),
        "end_time": period.get("end"),
        "reason_code": reason_code,
        "reason_display": reason_display,
        "organization_name": encounter.get(
            "serviceProvider", {}
        ).get("display"),
    }

    return [row]