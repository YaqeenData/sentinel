from datetime import datetime, timezone

from sentinel.streaming.profile import build_window_profile
from sentinel.streaming.windows import Window


def test_build_window_profile():
    start = datetime(2026, 10, 10, 13, 42, tzinfo=timezone.utc)
    end = datetime(2026, 10, 10, 13, 43, tzinfo=timezone.utc)

    window = Window(
        window_start=start,
        window_end=end,
        rows=[
            {"value_type": "numeric", "numeric_value": 10.0},
            {"value_type": "numeric", "numeric_value": None},
            {"value_type": "categorical", "numeric_value": None},
        ],
    )

    profile = build_window_profile(window)

    assert profile["record_count"] == 3
    assert profile["numeric_record_count"] == 2
    assert profile["null_rate"] == 0.5
    assert profile["window_start"] == start
    assert profile["window_end"] == end
