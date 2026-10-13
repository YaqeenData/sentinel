from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


EVENT_TIME_FIELD = "_event_time"


@dataclass
class Window:
    """
    One completed tumbling window and the rows that belong to it.
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


def row_time(
    row: dict,
    clock: Callable[[], datetime],
) -> datetime:
    """
    Return the time a row belongs to.

    Uses the event time attached by the consumer (when the
    message was sent to Kafka). Falls back to the clock
    (arrival time) when the row has no event time.
    """

    event_time = row.get(EVENT_TIME_FIELD)

    if isinstance(event_time, datetime):
        return event_time

    return clock()


def tumbling_windows(
    rows: Iterable[dict],
    window_seconds: int = 60,
    clock: Callable[[], datetime] = utc_now,
) -> Iterator[Window]:
    """
    Group incoming rows into tumbling windows by event time.

    Event time is the Kafka send time attached by the consumer.
    If a row has none, its arrival time (clock) is used instead.

    A window is yielded when the first row of a later window arrives.
    A late row whose window has already closed is added to the
    current window, so no row is lost.
    """

    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than 0.")

    current: Window | None = None

    for row in rows:
        start = floor_to_window(row_time(row, clock), window_seconds)

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