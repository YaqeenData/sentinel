from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Window:
    """
    One completed tumbling window and the rows that arrived in it.
    """

    window_start: datetime
    window_end: datetime
    rows: list[dict] = field(default_factory=list)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def floor_to_window(
    timestamp: datetime,
    window_seconds: int,
) -> datetime:
    """
    Round a timestamp down to the start of its window.

    Example with 60-second windows:
    14:00:23 -> 14:00:00
    """

    epoch_seconds = int(timestamp.timestamp())
    window_start_seconds = epoch_seconds - (epoch_seconds % window_seconds)

    return datetime.fromtimestamp(
        window_start_seconds,
        tz=timezone.utc,
    )


def tumbling_windows(
    rows: Iterable[dict],
    window_seconds: int = 60,
    clock: Callable[[], datetime] = utc_now,
) -> Iterator[Window]:
    """
    Group incoming rows into tumbling windows by arrival time.

    A window is yielded when the first row of a later window arrives.
    """

    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than 0.")

    current: Window | None = None

    for row in rows:
        start = floor_to_window(clock(), window_seconds)

        if current is None:
            current = Window(
                window_start=start,
                window_end=start + timedelta(seconds=window_seconds),
            )

        elif start >= current.window_end:
            yield current

            current = Window(
                window_start=start,
                window_end=start + timedelta(seconds=window_seconds),
            )

        current.rows.append(row)