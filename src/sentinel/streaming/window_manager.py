from datetime import datetime, timedelta, timezone

from sentinel.streaming.profile import build_window_profile
from sentinel.streaming.windows import Window, floor_to_window
from sentinel.storage.posgres import save_quality_window


class WindowManager:
    """Build and save profiles for completed processing-time windows."""

    def __init__(self, window_seconds: int = 60):
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0.")

        self.window_seconds = window_seconds
        self._windows: dict[datetime, Window] = {}

    def add_row(
        self,
        row: dict,
        processing_timestamp: datetime | None = None,
    ) -> list[dict]:
        """Add a row and save profiles for completed windows."""

        now = processing_timestamp or datetime.now(timezone.utc)
        current_start = floor_to_window(now, self.window_seconds)
        completed_profiles: list[dict] = []

        for start in sorted(list(self._windows)):
            window = self._windows[start]

            if current_start >= window.window_end:
                profile = build_window_profile(window)

                metrics = [
                    {
                        "metric_name": "record_count",
                        "field_name": None,
                        "metric_value": profile["record_count"],
                    },
                    {
                        "metric_name": "null_rate",
                        "field_name": profile["field_name"],
                        "metric_value": profile["null_rate"],
                    },
                ]

                save_quality_window(
                    resource_type="Observation",
                    window_start=profile["window_start"],
                    window_end=profile["window_end"],
                    metrics=metrics,
                )

                completed_profiles.append(profile)
                del self._windows[start]

        if current_start not in self._windows:
            self._windows[current_start] = Window(
                window_start=current_start,
                window_end=current_start
                + timedelta(seconds=self.window_seconds),
            )

        self._windows[current_start].rows.append(row)

        return completed_profiles
