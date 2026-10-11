from copy import deepcopy


def inject_volume_failure(
    rows: list[dict],
    mode: str = "drop",
    factor: float = 0.25,
) -> list[dict]:
    """Create a modified copy of rows to simulate a volume failure."""

    if mode not in {"drop", "spike"}:
        raise ValueError("mode must be 'drop' or 'spike'.")

    if factor <= 0:
        raise ValueError("factor must be greater than 0.")

    if mode == "drop" and factor >= 1:
        raise ValueError("For a drop, factor must be less than 1.")

    if not rows:
        return []

    copied_rows = deepcopy(rows)

    if mode == "drop":
        keep_count = int(len(copied_rows) * factor)
        return copied_rows[:keep_count]

    extra_count = max(1, int(len(copied_rows) * factor))
    extra_rows = deepcopy(copied_rows[:extra_count])

    return copied_rows + extra_rows
