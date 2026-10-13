"""
Window health metrics for the live Observation stream.

For every completed window Sentinel stores two whole-window numbers in
quality_metrics, so the dashboard can show the latest state of the stream:

    record_count   rows received in the window
    null_rate      share of numeric rows whose numeric_value is missing

These describe the health of the data, not the health of patients.
"""

from collections.abc import Callable

from sentinel.streaming.profile import build_window_profile
from sentinel.streaming.windows import Window


RECORD_COUNT_METRIC = "record_count"
NULL_RATE_METRIC = "null_rate"


def window_health_metrics(window: Window) -> list[dict]:
    """The two health metrics of one completed window, ready to store."""

    profile = build_window_profile(window)

    return [
        {
            "metric_name": RECORD_COUNT_METRIC,
            "field_name": None,
            "metric_value": float(profile["record_count"]),
        },
        {
            "metric_name": NULL_RATE_METRIC,
            "field_name": profile["field_name"],
            "metric_value": float(profile["null_rate"]),
        },
    ]


def persist_window_health(
    window: Window,
    resource_type: str = "Observation",
    save: Callable[..., int] | None = None,
) -> list[dict]:
    """
    Store record_count and null_rate for one completed window.

    ``save`` defaults to ``upsert_quality_metric``; tests pass a fake.
    The write is an upsert, so re-processing a window does not duplicate it.
    """

    if save is None:
        from sentinel.storage.postgres import upsert_quality_metric

        save = upsert_quality_metric

    metrics = window_health_metrics(window)

    for metric in metrics:
        save(
            resource_type=resource_type,
            window_start=window.window_start,
            window_end=window.window_end,
            **metric,
        )

    return metrics
