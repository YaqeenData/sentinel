from datetime import datetime, timezone
from unittest.mock import patch

from sentinel.streaming.window_manager import WindowManager


def test_window_manager_profiles_completed_window():
    manager = WindowManager()

    first_time = datetime(
        2026, 10, 10, 13, 42, 10,
        tzinfo=timezone.utc,
    )
    next_time = datetime(
        2026, 10, 10, 13, 43, 5,
        tzinfo=timezone.utc,
    )

    with patch(
        "sentinel.streaming.window_manager.save_quality_window"
    ) as mock_save:
        assert manager.add_row(
            {"value_type": "numeric", "numeric_value": 10.0},
            first_time,
        ) == []

        assert manager.add_row(
            {"value_type": "numeric", "numeric_value": None},
            first_time,
        ) == []

        completed = manager.add_row(
            {"value_type": "numeric", "numeric_value": 20.0},
            next_time,
        )

    assert len(completed) == 1

    profile = completed[0]

    assert profile["window_start"] == datetime(
        2026, 10, 10, 13, 42,
        tzinfo=timezone.utc,
    )
    assert profile["window_end"] == datetime(
        2026, 10, 10, 13, 43,
        tzinfo=timezone.utc,
    )
    assert profile["record_count"] == 2
    assert profile["null_rate"] == 0.5

    mock_save.assert_called_once()


def test_completed_window_is_saved_to_storage():
    manager = WindowManager(window_seconds=60)

    first_time = datetime(
        2026, 10, 10, 13, 42, 10,
        tzinfo=timezone.utc,
    )
    next_time = datetime(
        2026, 10, 10, 13, 43, 5,
        tzinfo=timezone.utc,
    )

    with patch(
        "sentinel.streaming.window_manager.save_quality_window"
    ) as mock_save:
        manager.add_row(
            {"numeric_value": 10.0},
            first_time,
        )
        manager.add_row(
            {"numeric_value": None},
            next_time,
        )

    mock_save.assert_called_once()

    saved_data = mock_save.call_args.kwargs

    assert saved_data["resource_type"] == "Observation"

    metrics = saved_data["metrics"]

    assert metrics[0]["metric_name"] == "record_count"
    assert metrics[0]["metric_value"] == 1

    assert metrics[1]["metric_name"] == "null_rate"
    assert metrics[1]["metric_value"] == 0.0
