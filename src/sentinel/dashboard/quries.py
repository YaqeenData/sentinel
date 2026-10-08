"""
Data access for the Sentinel dashboard.

The dashboard never calculates metrics itself. It only reads what the
profiling step already stored, so there is one source of truth.

For now this returns SAMPLE data, because the PostgreSQL table for
quality-window metrics (YAQ-19) is not finished yet. When it is, only
get_latest_window() changes; the Streamlit page stays the same.
"""

from datetime import datetime, timedelta, timezone


def get_latest_window() -> dict | None:
    """
    Return the latest completed quality window, or None if there is none yet.

    Shape the page expects:
        {
            "window_start": datetime,
            "window_end":   datetime,
            "record_count": int,
            "null_rate":    float,   # 0.012 means 1.2%
            "is_sample":    bool,    # True while we show sample data
        }
    """
    return _sample_latest_window()


def _sample_latest_window() -> dict:
    """Fake window with realistic values, used until PostgreSQL is ready."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    return {
        "window_start": now - timedelta(minutes=1),
        "window_end": now,
        "record_count": 1240,
        "null_rate": 0.012,
        "is_sample": True,
    }