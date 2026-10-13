from copy import deepcopy
from math import ceil


def inject_null_spike(
    rows: list[dict],
    field_name: str = "numeric_value",
    null_rate: float = 0.30,
) -> list[dict]:
    """Inject missing values into a copied dataset."""

    if not 0.0 <= null_rate <= 1.0:
        raise ValueError("null_rate must be between 0 and 1.")

    if not field_name:
        raise ValueError("field_name cannot be empty.")

    copied_rows = deepcopy(rows)

    if not copied_rows or null_rate == 0:
        return copied_rows

    target_count = ceil(len(copied_rows) * null_rate)

    # Make the selected field missing in the first target_count rows.
    for row in copied_rows[:target_count]:
        row[field_name] = None

    return copied_rows
