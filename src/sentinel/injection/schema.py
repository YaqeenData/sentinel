"""
Schema / contract failure injection for the LIVE stream only.

Corrupts a share of new FHIR Observations before they are sent to Kafka,
so the contract detector has real problems to catch in the demo.
Historical data in GCS is never touched: it stays clean for the baseline.

Each kind breaks exactly one contract rule in sentinel.detection.contract:
    number_as_string -> numeric value sent as text   -> type_mismatch
    missing_patient  -> patient reference left empty  -> missing_required_field
    invalid_status   -> status outside FHIR values    -> invalid_value
"""

import copy
import random
from collections.abc import Iterable, Iterator

SCHEMA_ERROR_KINDS = ("number_as_string", "missing_patient", "invalid_status")
INVALID_STATUS = "done"   # not an allowed FHIR Observation.status


def corrupt(observation: dict, kind: str) -> dict:
    """Return a broken COPY of one FHIR Observation. The original is never changed."""
    if kind not in SCHEMA_ERROR_KINDS:
        raise ValueError(f"Unknown schema error kind: {kind}")

    broken = copy.deepcopy(observation)

    if kind == "number_as_string":
        quantity = broken.get("valueQuantity")
        if isinstance(quantity, dict) and quantity.get("value") is not None:
            quantity["value"] = str(quantity["value"])

    elif kind == "missing_patient":
        broken["subject"] = {"reference": ""}

    elif kind == "invalid_status":
        broken["status"] = INVALID_STATUS

    return broken


def inject_schema_errors(
    observations: Iterable[dict],
    rate: float = 0.3,
    kinds: tuple[str, ...] = SCHEMA_ERROR_KINDS,
    seed: int | None = None,
) -> Iterator[dict]:
    """
    Yield observations, corrupting a share of them.

    rate:  share of observations to corrupt, 0.0 to 1.0
    kinds: which error kinds to use (picked at random per corrupted row)
    seed:  fixed seed gives the same corruption every run (useful for demos and tests)
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError("rate must be between 0.0 and 1.0")

    rng = random.Random(seed)

    for observation in observations:
        if rng.random() < rate:
            yield corrupt(observation, rng.choice(kinds))
        else:
            yield observation