"""
Controlled categorical-drift injection for raw FHIR Encounters.

The monitored field is ``Encounter.class.code`` (for example AMB, EMER,
IMP). Injection moves a share of Encounters from one class to another so
the Encounter class-drift detector can be tested against a known failure.
"""

import random
from copy import deepcopy
from typing import Any


def inject_fhir_categorical_encounter(
    encounter: dict[str, Any],
    *,
    source_class: str,
    target_class: str,
    target_display: str | None = None,
) -> dict[str, Any]:
    """
    Change the class code of one raw FHIR Encounter.

    The original Encounter is not modified.

    Only Encounters whose class code equals the configured source class
    are changed; anything else is returned as an unchanged copy.

    If the class Coding already carries a ``display``, it would contradict
    the new code. It is replaced by ``target_display`` when given, and
    removed otherwise.
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

    if target_display is not None:
        encounter_class["display"] = target_display
    else:
        encounter_class.pop("display", None)

    return injected


def _has_source_class(
    encounter: dict[str, Any],
    source_class: str,
) -> bool:
    if encounter.get("resourceType") != "Encounter":
        return False

    encounter_class = encounter.get("class")

    return (
        isinstance(encounter_class, dict)
        and encounter_class.get("code") == source_class
    )


def inject_encounter_class_drift(
    encounters: list[dict[str, Any]],
    *,
    source_class: str,
    target_class: str,
    drift_rate: float,
    seed: int = 42,
    target_display: str | None = None,
) -> list[dict[str, Any]]:
    """
    Shift a share of Encounters from the source class to the target class.

    ``drift_rate`` is the share of source-class Encounters that are
    changed, rounded down. Encounters of other classes are never touched
    and never count toward the share. The same seed always changes the
    same Encounters.

    The original list and its Encounters are not modified.
    """

    if not 0.0 <= drift_rate <= 1.0:
        raise ValueError("drift_rate must be between 0 and 1.")

    if source_class == target_class:
        raise ValueError(
            "source_class and target_class must be different."
        )

    drifted = deepcopy(encounters)

    eligible_indexes = [
        index
        for index, encounter in enumerate(drifted)
        if _has_source_class(encounter, source_class)
    ]

    number_to_change = int(len(eligible_indexes) * drift_rate)

    if number_to_change == 0:
        return drifted

    rng = random.Random(seed)

    for index in rng.sample(eligible_indexes, k=number_to_change):
        drifted[index] = inject_fhir_categorical_encounter(
            drifted[index],
            source_class=source_class,
            target_class=target_class,
            target_display=target_display,
        )

    return drifted