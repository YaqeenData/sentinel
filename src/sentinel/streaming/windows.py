"""
Group a stream of rows into fixed, non-overlapping (tumbling) time windows.

Uses processing time (when Sentinel receives the row), not the clinical time
inside the FHIR resource, because the producer replays historical data.

Note: a window closes when the next row arrives after its end.
If the stream goes quiet, the last window waits for the next message.
"""

import time
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _window(start: float, end: float, resource_type: str) -> dict:
    return {"resource_type": resource_type, "window_start": _iso(start), "window_end": _iso(end)}


def tumbling_windows(
    rows: Iterable[dict],
    seconds: int = 60,
    resource_type: str = "Observation",
) -> Iterator[tuple[dict, list[dict]]]:
    """Yield (window, rows) every `seconds` of processing time."""
    batch: list[dict] = []
    start = time.time()

    for row in rows:
        now = time.time()
        if now - start >= seconds:
            if batch:
                yield _window(start, now, resource_type), batch
            batch, start = [], now
        batch.append(row)

    if batch:
        yield _window(start, time.time(), resource_type), batch
