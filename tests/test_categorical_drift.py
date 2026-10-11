import pytest

from sentinel.detection.categorical_drift import (
    detect_categorical_drift,
)
from sentinel.detection.categorical_monitor import (
    monitor_categorical_drift,
)
from sentinel.injection.categorical_drift import (
    inject_categorical_drift,
)
from sentinel.profiling.categorical import (
    profile_categorical,
)
from sentinel.streaming.windows import Window

from datetime import datetime, timedelta, timezone


def test_profile_categorical():
    records = [
        {"categorical_code": "A"},
        {"categorical_code": "A"},
        {"categorical_code": "B"},
        {"categorical_code": None},
    ]

    profile = profile_categorical(
        records,
        "categorical_code",
    )

    assert profile["total_count"] == 4
    assert profile["non_null_count"] == 3
    assert profile["null_count"] == 1

    assert profile["category_counts"] == {
        "A": 2,
        "B": 1,
    }

    assert profile["category_proportions"] == pytest.approx(
        {
            "A": 2 / 3,
            "B": 1 / 3,
        }
    )


def test_categorical_injection_is_controlled():
    records = [
        {
            "code": "72166-2",
            "categorical_code": "A",
            "categorical_display": "Category A",
        },
        {
            "code": "72166-2",
            "categorical_code": "B",
            "categorical_display": "Category B",
        },
        {
            "code": "OTHER",
            "categorical_code": "A",
            "categorical_display": "Category A",
        },
    ]

    original = [
        record.copy()
        for record in records
    ]

    drifted = inject_categorical_drift(
        records=records,
        field_name="categorical_code",
        source_category="A",
        target_category="B",
        fraction=1.0,
        seed=42,
        observation_code="72166-2",
        display_field="categorical_display",
        target_display="Category B",
    )

    # Original input must remain untouched.
    assert records == original

    # Matching source category is changed.
    assert drifted[0]["categorical_code"] == "B"
    assert drifted[0]["categorical_display"] == "Category B"

    # Existing target category stays unchanged.
    assert drifted[1]["categorical_code"] == "B"

    # Unrelated Observation must not be modified.
    assert drifted[2]["categorical_code"] == "A"


def test_insufficient_samples_do_not_trigger_detection():
    baseline = {
        "A": 0.75,
        "B": 0.25,
    }

    current = {
        "A": 0.50,
        "B": 0.50,
    }

    result = detect_categorical_drift(
        baseline_proportions=baseline,
        current_proportions=current,
        current_count=5,
        threshold=0.20,
        min_samples=30,
    )

    assert result["sufficient_data"] is False
    assert result["drift_detected"] is False
    assert result["js_distance"] is None
    assert result["reason"] == "insufficient_samples"


def test_healthy_distribution_does_not_trigger_drift():
    baseline = {
        "A": 0.75,
        "B": 0.25,
    }

    current = {
        "A": 0.70,
        "B": 0.30,
    }

    result = detect_categorical_drift(
        baseline_proportions=baseline,
        current_proportions=current,
        current_count=100,
        threshold=0.20,
        min_samples=30,
    )

    assert result["sufficient_data"] is True
    assert result["drift_detected"] is False
    assert result["js_distance"] < 0.20


def test_shifted_distribution_triggers_drift():
    baseline = {
        "A": 0.75,
        "B": 0.25,
    }

    current = {
        "A": 0.20,
        "B": 0.80,
    }

    result = detect_categorical_drift(
        baseline_proportions=baseline,
        current_proportions=current,
        current_count=100,
        threshold=0.20,
        min_samples=30,
    )

    assert result["sufficient_data"] is True
    assert result["drift_detected"] is True
    assert result["js_distance"] > 0.20


def test_monitor_keeps_latest_status_per_patient():
    start = datetime.now(timezone.utc)

    windows = [
        Window(
            window_start=start,
            window_end=start + timedelta(seconds=60),
            rows=[
                {
                    "patient_id": "patient-1",
                    "code": "72166-2",
                    "categorical_code": "A",
                },
                {
                    "patient_id": "patient-2",
                    "code": "72166-2",
                    "categorical_code": "A",
                },
            ],
        ),
        Window(
            window_start=start + timedelta(seconds=60),
            window_end=start + timedelta(seconds=120),
            rows=[
                {
                    "patient_id": "patient-1",
                    "code": "72166-2",
                    "categorical_code": "B",
                },
                {
                    "patient_id": "patient-3",
                    "code": "72166-2",
                    "categorical_code": "B",
                },
            ],
        ),
    ]

    baseline = {
        "A": 0.75,
        "B": 0.25,
    }

    results = list(
        monitor_categorical_drift(
            windows=windows,
            observation_code="72166-2",
            baseline_proportions=baseline,
            threshold=0.20,
            min_samples=3,
        )
    )

    final_result = results[-1]

    assert final_result["unique_patient_count"] == 3

    assert final_result["profile"]["category_counts"] == {
        "A": 1,
        "B": 2,
    }

    # patient-1's newer B value replaces their older A value.
    assert final_result["profile"]["total_count"] == 3

    assert final_result["detection"]["sufficient_data"] is True