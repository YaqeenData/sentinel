"""
Profile a numeric field in one completed window.

Answers one question: what do the numbers in this window look like?
It does not decide whether anything is wrong; the detectors do that.
"""

import math
from statistics import mean, median, stdev
from typing import Any


def _is_valid_number(value: Any) -> bool:
    """Return True only for real numbers (not bool, not string, not NaN)."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return not math.isnan(value)


def profile_numeric(
    records: list[dict[str, Any]],
    field_name: str,
) -> dict[str, Any]:
    """
    Profile the distribution of a numeric field in one completed window.

    Nulls and non-numeric values are counted but excluded from the statistics.
    """

    total_count = len(records)

    values = [
        record.get(field_name)
        for record in records
    ]

    null_count = sum(
        1 for value in values
        if value is None or value == ""
    )

    numeric_values = sorted(
        float(value)
        for value in values
        if _is_valid_number(value)
    )

    valid_count = len(numeric_values)
    invalid_count = total_count - null_count - valid_count

    if valid_count == 0:
        stats = {}
    else:
        stats = {
            "mean": mean(numeric_values),
            "median": median(numeric_values),
            "std": stdev(numeric_values) if valid_count > 1 else 0.0,
            "min": numeric_values[0],
            "max": numeric_values[-1],
        }

    return {
        "field_name": field_name,
        "total_count": total_count,
        "valid_count": valid_count,
        "null_count": null_count,
        "invalid_count": invalid_count,
        "values": numeric_values,
        "stats": stats,
    }