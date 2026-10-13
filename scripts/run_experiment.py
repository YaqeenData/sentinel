from collections.abc import Iterable, Iterator
from pathlib import Path

import yaml

from sentinel.detection.categorical_monitor import (
    monitor_categorical_drift,
)
from sentinel.injection.categorical_drift import (
    inject_categorical_drift,
)
from sentinel.storage.postgres import (
    insert_incident,
)
from sentinel.streaming.consumer import (
    consume_observations,
)
from sentinel.streaming.windows import (
    Window,
    tumbling_windows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "monitoring.yaml"
)


def load_categorical_drift_config() -> dict:
    """
    Load categorical-drift monitoring configuration.
    """

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    if not config:
        raise ValueError(
            "monitoring.yaml is empty."
        )

    if "categorical_drift" not in config:
        raise ValueError(
            "categorical_drift configuration "
            "was not found."
        )

    return config["categorical_drift"]


CONFIG = load_categorical_drift_config()

OBSERVATION_CODE = CONFIG[
    "observation"
]["code"]

FIELD_NAME = CONFIG[
    "field_name"
]

THRESHOLD = float(
    CONFIG[
        "detection"
    ]["threshold"]
)

MIN_SAMPLES = int(
    CONFIG[
        "detection"
    ]["min_samples"]
)

BASELINE = {
    str(category): float(proportion)
    for category, proportion
    in CONFIG[
        "baseline"
    ]["proportions"].items()
}

SOURCE_CATEGORY = CONFIG[
    "injection"
]["source_category"]["code"]

TARGET_CATEGORY = CONFIG[
    "injection"
]["target_category"]["code"]

TARGET_DISPLAY = CONFIG[
    "injection"
]["target_category"]["display"]

INJECTION_FRACTION = float(
    CONFIG[
        "injection"
    ]["fraction"]
)

INJECTION_SEED = int(
    CONFIG[
        "injection"
    ]["seed"]
)

INCIDENT_TYPE = CONFIG[
    "incident"
]["type"]

METRIC_NAME = CONFIG[
    "incident"
]["metric_name"]

SEVERITY = CONFIG[
    "incident"
]["severity"]


class ExperimentWindows:
    """
    Pass healthy windows through normally.

    When injection is enabled, categorical drift is injected
    into the configured Observation category.
    """

    def __init__(
        self,
        windows: Iterable[Window],
    ) -> None:
        self.windows = iter(windows)
        self.injection_enabled = False

    def __iter__(self) -> Iterator[Window]:

        for window in self.windows:

            if not self.injection_enabled:
                yield window
                continue

            injected_rows = inject_categorical_drift(
                records=window.rows,
                field_name=FIELD_NAME,
                source_category=SOURCE_CATEGORY,
                target_category=TARGET_CATEGORY,
                observation_code=OBSERVATION_CODE,
                fraction=INJECTION_FRACTION,
                seed=INJECTION_SEED,
                display_field="categorical_display",
                target_display=TARGET_DISPLAY,
            )

            yield Window(
                window_start=window.window_start,
                window_end=window.window_end,
                rows=injected_rows,
            )


def main() -> None:

    rows = consume_observations()

    windows = tumbling_windows(
        rows,
        window_seconds=60,
    )

    experiment_windows = ExperimentWindows(
        windows
    )

    results = monitor_categorical_drift(
        windows=experiment_windows,
        observation_code=OBSERVATION_CODE,
        baseline_proportions=BASELINE,
        field_name=FIELD_NAME,
        threshold=THRESHOLD,
        min_samples=MIN_SAMPLES,
    )

    healthy_confirmed = False

    print(
        "\nSentinel Categorical Drift Experiment"
    )
    print("=" * 60)

    print(
        f"Observation: "
        f"{CONFIG['observation']['display']} "
        f"({OBSERVATION_CODE})"
    )

    print(
        f"Threshold: {THRESHOLD}"
    )

    print(
        f"Minimum unique patients: "
        f"{MIN_SAMPLES}"
    )

    print("\nPhase 1: Healthy live stream")

    print(
        f"Waiting for "
        f"{MIN_SAMPLES} unique patients..."
    )

    for result in results:

        detection = result["detection"]

        print("\n" + "=" * 60)

        print(
            f"Window: {result['window_start']} "
            f"→ {result['window_end']}"
        )

        print(
            f"Smoking-status rows: "
            f"{result['matching_rows']}"
        )

        print(
            f"Unique patients: "
            f"{result['unique_patient_count']}"
            f"/{detection['min_samples']}"
        )

        if not detection["sufficient_data"]:
            print(
                "Status: waiting for enough "
                "unique patients"
            )
            continue

        print(
            "Current proportions:"
        )

        print(
            result[
                "profile"
            ]["category_proportions"]
        )

        print(
            f"JSD: "
            f"{detection['js_distance']:.4f}"
        )

        print(
            f"Drift detected: "
            f"{detection['drift_detected']}"
        )

        if (
            not healthy_confirmed
            and not detection["drift_detected"]
        ):
            healthy_confirmed = True

            experiment_windows.injection_enabled = True

            print(
                "\nHEALTHY STATE CONFIRMED"
            )

            print(
                "Phase 2: categorical drift "
                "injection ENABLED"
            )

            print(
                f"Changing "
                f"{INJECTION_FRACTION:.0%} "
                f"of incoming "
                f"'{CONFIG['injection']['source_category']['display']}' "
                f"statuses to "
                f"'{TARGET_DISPLAY}'."
            )

            continue

        if (
            healthy_confirmed
            and detection["drift_detected"]
        ):
            print(
                "\nDRIFT DETECTED"
            )

            incident_id = insert_incident(
                resource_type="Observation",
                detected_at=result["window_end"],
                incident_type=INCIDENT_TYPE,
                metric_name=METRIC_NAME,
                field_name=FIELD_NAME,
                observed_value=detection[
                    "js_distance"
                ],
                baseline_value=None,
                severity=SEVERITY,
                message=(
                    "Categorical distribution drift "
                    f"detected for "
                    f"{CONFIG['observation']['display']} "
                    f"({OBSERVATION_CODE}). "
                    f"Jensen-Shannon distance "
                    f"{detection['js_distance']:.4f} "
                    f"exceeded threshold "
                    f"{THRESHOLD:.2f}. "
                    f"Observed proportions: "
                    f"{result['profile']['category_proportions']}."
                ),
            )

            print(
                "Sentinel successfully detected "
                "the injected categorical "
                "distribution change."
            )

            print(
                f"Incident stored in PostgreSQL "
                f"with ID: {incident_id}"
            )

            break


if __name__ == "__main__":
    main()