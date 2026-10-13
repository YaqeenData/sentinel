from sentinel.streaming.windows import Window


def build_window_profile(
    window: Window,
    field_name: str = "numeric_value",
) -> dict:
    """Build data-quality metrics for one completed window."""

    rows = window.rows
    record_count = len(rows)

    numeric_rows = [
        row for row in rows
        if row.get("value_type") == "numeric"
    ]

    numeric_record_count = len(numeric_rows)

    null_count = sum(
        row.get(field_name) is None
        for row in numeric_rows
    )

    null_rate = (
        null_count / numeric_record_count
        if numeric_record_count > 0
        else 0.0
    )

    return {
        "window_start": window.window_start,
        "window_end": window.window_end,
        "record_count": record_count,
        "numeric_record_count": numeric_record_count,
        "field_name": field_name,
        "null_count": null_count,
        "null_rate": null_rate,
    }
