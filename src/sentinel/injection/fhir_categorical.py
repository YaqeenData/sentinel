from copy import deepcopy
from typing import Any


def _has_code(
    codeable_concept: dict[str, Any] | None,
    code: str,
) -> bool:
    """
    Return True when a FHIR CodeableConcept contains the given code.
    """

    if not codeable_concept:
        return False

    for coding in codeable_concept.get("coding", []):
        if coding.get("code") == code:
            return True

    return False


def inject_fhir_categorical_observation(
    observation: dict[str, Any],
    *,
    observation_code: str,
    source_category: str,
    target_category: str,
    target_display: str,
) -> dict[str, Any]:
    """
    Change one raw FHIR Observation categorical value.

    The original Observation is not modified.

    Only Observations matching both:
    - the monitored Observation code
    - the configured source categorical value

    are changed.
    """

    injected = deepcopy(observation)

    if injected.get("resourceType") != "Observation":
        return injected

    if not _has_code(
        injected.get("code"),
        observation_code,
    ):
        return injected

    value = injected.get(
        "valueCodeableConcept"
    )

    if not _has_code(
        value,
        source_category,
    ):
        return injected

    for coding in value.get("coding", []):
        if coding.get("code") == source_category:
            coding["code"] = target_category
            coding["display"] = target_display

    if value.get("text"):
        value["text"] = target_display

    return injected