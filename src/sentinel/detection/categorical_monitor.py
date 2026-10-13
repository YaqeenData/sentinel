from collections import OrderedDict
from collections.abc import Iterable, Iterator

from sentinel.detection.categorical_drift import (
    detect_categorical_drift,
)
from sentinel.profiling.categorical import (
    profile_categorical,
)
from sentinel.streaming.windows import Window


def monitor_categorical_drift(
    windows: Iterable[Window],
    observation_code: str,
    baseline_proportions: dict[str, float],
    field_name: str = "categorical_code",
    threshold: float = 0.20,
    min_samples: int = 100,
) -> Iterator[dict]:
    """
    Monitor categorical distribution drift across completed stream windows.

    For each patient, only the latest matching categorical observation
    is retained. Drift is evaluated across the most recent unique patients.
    """

    patient_buffer: OrderedDict[str, dict] = OrderedDict()

    for window in windows:

        matching_rows = [
            row
            for row in window.rows
            if row.get("code") == observation_code
            and row.get(field_name) is not None
            and row.get("patient_id") is not None
        ]

        for row in matching_rows:
            patient_id = row["patient_id"]

            if patient_id in patient_buffer:
                del patient_buffer[patient_id]

            patient_buffer[patient_id] = row

            while len(patient_buffer) > min_samples:
                patient_buffer.popitem(last=False)

        current_records = list(patient_buffer.values())

        profile = profile_categorical(
            records=current_records,
            field_name=field_name,
        )

        detection = detect_categorical_drift(
            baseline_proportions=baseline_proportions,
            current_proportions=profile["category_proportions"],
            current_count=len(patient_buffer),
            threshold=threshold,
            min_samples=min_samples,
        )

        yield {
            "window_start": window.window_start,
            "window_end": window.window_end,
            "window_rows": len(window.rows),
            "matching_rows": len(matching_rows),
            "unique_patient_count": len(patient_buffer),
            "profile": profile,
            "detection": detection,
        }