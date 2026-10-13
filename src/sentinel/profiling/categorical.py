from collections import Counter
from typing import Any


def profile_categorical(
    records: list[dict[str, Any]],
    field_name: str,
) -> dict[str, Any]:
    """
    Profile the distribution of a categorical field in one completed window.

    Null values are counted but excluded from the category proportions.
    """

    total_count = len(records)

    values = [
        record.get(field_name)
        for record in records
    ]

    non_null_values = [
        str(value)
        for value in values
        if value is not None and value != ""
    ]

    null_count = total_count - len(non_null_values)

    category_counts = Counter(non_null_values)
    non_null_count = sum(category_counts.values())

    if non_null_count == 0:
        category_proportions = {}
    else:
        category_proportions = {
            category: count / non_null_count
            for category, count in sorted(category_counts.items())
        }

    return {
        "field_name": field_name,
        "total_count": total_count,
        "non_null_count": non_null_count,
        "null_count": null_count,
        "category_counts": dict(sorted(category_counts.items())),
        "category_proportions": category_proportions,
    }