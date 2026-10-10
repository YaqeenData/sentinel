def extract_reference_id(reference: str | None) -> str | None:
    """
    Convert a FHIR reference such as:
        Patient/abc-123
    into:
        abc-123
    """
    if not reference:
        return None

    return reference.rsplit("/", 1)[-1]


def get_code_info(codeable_concept: dict) -> tuple[str | None, str | None]:
    """
    Extract the first coding code and its human-readable display.
    """
    coding = codeable_concept.get("coding", [])

    if not coding:
        return None, codeable_concept.get("text")

    first = coding[0]

    return (
        first.get("code"),
        first.get("display") or codeable_concept.get("text"),
    )
    
def extract_value(element: dict) -> dict:
    """
    Normalize a FHIR value[x] representation.
    """

    result = {
        "value_type": None,
        "numeric_value": None,
        "categorical_code": None,
        "categorical_display": None,
        "string_value": None,
        "unit": None,
    }

    if "valueQuantity" in element:
        quantity = element["valueQuantity"]

        result["value_type"] = "numeric"
        result["numeric_value"] = quantity.get("value")
        result["unit"] = quantity.get("code") or quantity.get("unit")

    elif "valueCodeableConcept" in element:
        concept = element["valueCodeableConcept"]
        code, display = get_code_info(concept)

        result["value_type"] = "categorical"
        result["categorical_code"] = code
        result["categorical_display"] = display

    elif "valueString" in element:
        result["value_type"] = "string"
        result["string_value"] = element["valueString"]

    return result

def normalize_observation(observation: dict) -> list[dict]:
    """
    Convert one FHIR Observation into one or more
    normalized Silver rows.
    """

    observation_id = observation.get("id")

    patient_id = extract_reference_id(
        observation.get("subject", {}).get("reference")
    )

    encounter_id = extract_reference_id(
        observation.get("encounter", {}).get("reference")
    )

    parent_code, parent_display = get_code_info(
        observation.get("code", {})
    )

    common = {
        "observation_id": observation_id,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "parent_code": parent_code,
        "parent_display": parent_display,
        "event_time": observation.get("effectiveDateTime"),
        "issued_time": observation.get("issued"),
        "status": observation.get("status"),
    }

    rows = []

    # Compound observation, e.g. blood pressure
    if "component" in observation:

        for component in observation["component"]:

            code, display = get_code_info(
                component.get("code", {})
            )

            row = {
                **common,
                "code": code,
                "display": display,
                **extract_value(component),
            }

            rows.append(row)

    # Simple observation
    else:

        row = {
            **common,
            "code": parent_code,
            "display": parent_display,
            **extract_value(observation),
        }

        rows.append(row)

    return rows