"""
Live failure injection for the replay: nulls, volume, numeric drift
and contract (schema) errors on Observations, contract errors on
Patients, and class drift and contract errors on Encounters.

Each kind is switched on and off separately with scripts/set_injection.py
while the replay keeps running. The changes are made to raw FHIR
resources before they reach Kafka, so the monitor sees the failure
the same way it would see a real upstream bug.
"""

import copy
import random
from typing import Any, Callable

from sentinel.injection.categorical_drift_encounter import (
    inject_fhir_categorical_encounter,
)
from sentinel.injection.control import (
    injection_status,
)
from sentinel.injection.encounter_contract import (
    ENCOUNTER_ERROR_KINDS,
    corrupt_encounter,
)
from sentinel.injection.numeric_drift import (
    INJECTABLE_CODES,
    inject_record,
)
from sentinel.injection.patient_contract import (
    PATIENT_ERROR_KINDS,
    corrupt_patient,
)
from sentinel.injection.schema import (
    SCHEMA_ERROR_KINDS,
    corrupt,
)


# Share of monitored numeric readings sent without a value.
NULL_FRACTION = 0.30

# Share of Observations still sent while a volume drop is ON.
VOLUME_KEEP = 0.25

# Added to every reading of these codes while numeric drift is ON.
# Roughly 0.75 standard deviations of the healthy values.
NUMERIC_SHIFTS = {
    "8867-4": 12.0,   # Heart rate, /min
    "8480-6": 15.0,   # Systolic blood pressure, mmHg
    "2339-0": 20.0,   # Glucose, mg/dL
}

# Share of Observations broken while contract errors are ON.
# Each broken one gets one error kind from injection/schema.py,
# picked at random: number_as_string, missing_patient, invalid_status.
CONTRACT_FRACTION = 0.10

# Share of Patients broken while patient contract errors are ON.
# Only about 12 Patients arrive per minute, so the share is higher
# than for Observations: almost every window gets at least one.
# Each broken one gets one error kind from injection/patient_contract.py.
PATIENT_FRACTION = 0.30

# Share of Encounters broken while Encounter contract errors are ON.
# About 860 Encounters arrive per minute, so 5% is roughly 43 broken
# Encounters a minute: about 4 of each of the 10 error kinds.
# Each broken one gets one error kind from injection/encounter_contract.py.
ENCOUNTER_CONTRACT_FRACTION = 0.05

SEED = 42

LIVE_KINDS = ("nulls", "volume", "numeric", "contract")


def _code_of(
    item: dict[str, Any],
) -> str | None:
    """LOINC code of a raw FHIR Observation or component."""

    coding = (item.get("code") or {}).get("coding") or [{}]
    return coding[0].get("code")


def _monitored_items(
    observation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    The Observation and its components that carry a monitored code.

    Systolic pressure arrives as a component of the blood pressure
    panel, so components are checked too.
    """

    items = [
        observation,
        *(observation.get("component") or []),
    ]

    return [
        item for item in items
        if _code_of(item) in INJECTABLE_CODES
    ]


def drop_numeric_values(
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy with the monitored numeric values removed."""

    out = copy.deepcopy(observation)

    for item in _monitored_items(out):
        quantity = item.get("valueQuantity")

        if isinstance(quantity, dict):
            quantity["value"] = None

    return out


def shift_numeric_values(
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy with every monitored value shifted upward."""

    out = observation

    for code, shift in NUMERIC_SHIFTS.items():
        out = inject_record(out, code, shift)

    return out


def build_failure_transform() -> Callable[
    [dict[str, Any] | None],
    dict[str, Any] | None,
]:
    """
    Build the transform the replay applies to every Observation.

    Returns None for an Observation that should not be sent
    (volume drop); the producer skips it.
    """

    rng = random.Random(SEED)
    last_state: dict[str, bool] | None = None

    def transform(
        observation: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        nonlocal last_state

        if observation is None:
            return None

        status = injection_status()
        state = {kind: status[kind] for kind in LIVE_KINDS}

        if state != last_state:
            print()
            print(
                "Live failure injection: "
                + " | ".join(
                    f"{kind} {'ON' if on else 'OFF'}"
                    for kind, on in state.items()
                )
            )
            last_state = state

        # Volume drop: most Observations are simply not sent.
        if state["volume"] and rng.random() >= VOLUME_KEEP:
            return None

        # Numeric drift: every monitored reading moves up.
        if state["numeric"]:
            observation = shift_numeric_values(observation)

        # Null spike: part of the monitored readings lose their value.
        if (
            state["nulls"]
            and _monitored_items(observation)
            and rng.random() < NULL_FRACTION
        ):
            observation = drop_numeric_values(observation)

        # Contract errors: a share of Observations break one rule.
        if state["contract"] and rng.random() < CONTRACT_FRACTION:
            observation = corrupt(
                observation,
                rng.choice(SCHEMA_ERROR_KINDS),
            )

        return observation

    return transform


def build_patient_transform() -> Callable[
    [dict[str, Any]],
    dict[str, Any],
]:
    """
    Build the transform the replay applies to every Patient.

    While the "patient" kind is ON, a share of Patients break one
    contract rule from injection/patient_contract.py.
    """

    rng = random.Random(SEED)
    last_enabled: bool | None = None

    def transform(
        patient: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal last_enabled

        enabled = injection_status()["patient"]

        if enabled != last_enabled:
            print()
            print(
                "Patient contract injection: "
                + ("ON" if enabled else "OFF")
            )
            last_enabled = enabled

        if enabled and rng.random() < PATIENT_FRACTION:
            return corrupt_patient(
                patient,
                rng.choice(PATIENT_ERROR_KINDS),
            )

        return patient

    return transform


def build_encounter_transform(
    source_class: str,
    target_class: str,
    fraction: float,
    seed: int = SEED,
) -> Callable[
    [dict[str, Any]],
    dict[str, Any],
]:
    """
    Build the transform the replay applies to every Encounter.

    While the "encounter" kind is ON, each Encounter is tried with
    probability ``fraction``; a tried Encounter of ``source_class``
    becomes ``target_class`` (e.g. AMB → EMER). Other classes are never
    changed, so about ``fraction`` of the source class moves.

    Uses inject_fhir_categorical_encounter from
    injection/categorical_drift_encounter.py.
    """

    if not 0.0 <= fraction <= 1.0:
        raise ValueError("Encounter injection fraction must be between 0 and 1.")

    rng = random.Random(seed)
    last_enabled: bool | None = None

    def transform(
        encounter: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal last_enabled

        enabled = injection_status()["encounter"]

        if enabled != last_enabled:
            print()
            print(
                "Encounter class injection: "
                + ("ON" if enabled else "OFF")
            )
            if enabled:
                print(
                    f"Moving about {fraction:.0%} of "
                    f"{source_class} Encounters to {target_class}"
                )
            last_enabled = enabled

        if enabled and rng.random() < fraction:
            return inject_fhir_categorical_encounter(
                encounter,
                source_class=source_class,
                target_class=target_class,
            )

        return encounter

    return transform


def build_encounter_contract_transform() -> Callable[
    [dict[str, Any]],
    dict[str, Any],
]:
    """
    Build the contract-error transform the replay applies to every Encounter.

    While the "encounter_contract" kind is ON, a share of Encounters break
    one contract rule from injection/encounter_contract.py.
    """

    rng = random.Random(SEED)
    last_enabled: bool | None = None

    def transform(
        encounter: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal last_enabled

        enabled = injection_status()["encounter_contract"]

        if enabled != last_enabled:
            print()
            print(
                "Encounter contract injection: "
                + ("ON" if enabled else "OFF")
            )
            last_enabled = enabled

        if enabled and rng.random() < ENCOUNTER_CONTRACT_FRACTION:
            return corrupt_encounter(
                encounter,
                rng.choice(ENCOUNTER_ERROR_KINDS),
            )

        return encounter

    return transform