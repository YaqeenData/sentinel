import random
from copy import deepcopy
from typing import Any


def inject_categorical_drift(
    records: list[dict[str, Any]],
    field_name: str,
    source_category: Any,
    target_category: Any,
    fraction: float = 0.5,
    seed: int = 42,
    observation_code: str | None = None,
    display_field: str | None = None,
    target_display: str | None = None,
) -> list[dict[str, Any]]:
    """
    Inject categorical distribution drift by changing a fraction of one
    source category into a target category.

    If observation_code is provided, only that Observation type is changed.
    Optionally update its paired display field as well.

    The original records are not modified.
    """

    if not 0 <= fraction <= 1:
        raise ValueError("fraction must be between 0 and 1.")

    if source_category == target_category:
        raise ValueError(
            "source_category and target_category must be different."
        )

    injected_records = deepcopy(records)

    eligible_indexes = [
        index
        for index, record in enumerate(injected_records)
        if record.get(field_name) == source_category
        and (
            observation_code is None
            or record.get("code") == observation_code
        )
    ]

    if not eligible_indexes:
        return injected_records

    number_to_change = int(
        len(eligible_indexes) * fraction
    )

    if number_to_change == 0:
        return injected_records

    rng = random.Random(seed)

    indexes_to_change = rng.sample(
        eligible_indexes,
        k=number_to_change,
    )

    for index in indexes_to_change:
        injected_records[index][field_name] = target_category

        if (
            display_field is not None
            and target_display is not None
        ):
            injected_records[index][display_field] = target_display

    return injected_records