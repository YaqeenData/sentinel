from copy import deepcopy
from typing import Any
import random

def inject_fhir_categorical_encounter(
    encounter: dict[str, Any],
    *,
    source_class: str,
    target_class: str,
) -> dict[str, Any]:
    """
    Change the class code of one raw FHIR Encounter.

    The original Encounter is not modified.

    Only Encounters whose class code equals the configured
    source class are changed.
    """

    injected = deepcopy(encounter)

    if injected.get("resourceType") != "Encounter":
        return injected

    encounter_class = injected.get("class")

    if not isinstance(encounter_class, dict):
        return injected

    if encounter_class.get("code") != source_class:
        return injected

    encounter_class["code"] = target_class

    return injected

def inject_encounter_class_drift(
    encounters: list[dict[str, Any]],
    *,
    source_class: str,
    target_class: str,
    drift_rate: float,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """
    Shift a share of Encounters from the source class to the target class.

    drift_rate is the share of source-class Encounters that are changed.
    The same seed always changes the same Encounters.
    """

    if not 0.0 <= drift_rate <= 1.0:
        raise ValueError("drift_rate must be between 0 and 1.")

    rng = random.Random(seed)
    drifted = []

    for encounter in encounters:
        if rng.random() < drift_rate:
            encounter = inject_fhir_categorical_encounter(
                encounter,
                source_class=source_class,
                target_class=target_class,
            )

        drifted.append(encounter)

    return drifted