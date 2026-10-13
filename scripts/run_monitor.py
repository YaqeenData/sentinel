from pathlib import Path

import yaml

from sentinel.detection.categorical_monitor import (
    monitor_categorical_drift,
)
from sentinel.detection.contract import (
    check as check_contract,
)
from sentinel.storage.postgres import (
    get_open_incident_id,
    get_open_incidents_by_types,
    insert_incident,
    resolve_incident,
    upsert_quality_metric,
)
from sentinel.streaming.consumer import (
    consume_observations,
)
from sentinel.streaming.health import (
    persist_window_health,
)
from sentinel.streaming.windows import (
    tumbling_windows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "monitoring.yaml"
)

RESOURCE_TYPE = "Observation"
WINDOW_SECONDS = 60

CONTRACT_VIOLATION_METRIC = (
    "contract_violation_count"
)
CONTRACT_ROWS_METRIC = (
    "contract_rows_checked"
)

CONTRACT_INCIDENT_TYPES = (
    "missing_required_field",
    "invalid_value",
    "type_mismatch",
)


# ============================================================
# Configuration
# ============================================================


def load_config() -> dict:
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    return config["categorical_drift"]


# ============================================================
# Categorical drift incident message
# ============================================================


def build_incident_message(
    *,
    observation_display: str,
    observation_code: str,
    js_distance: float,
    threshold: float,
    proportions: dict[str, float],
) -> str:

    return (
        "Categorical distribution drift detected for "
        f"{observation_display} "
        f"({observation_code}). "
        f"Jensen-Shannon distance "
        f"{js_distance:.4f} "
        f"exceeded threshold "
        f"{threshold:.2f}. "
        f"Observed proportions: "
        f"{proportions}."
    )


# ============================================================
# Contract incident message
# ============================================================


def build_contract_incident_message(
    result: dict,
) -> str:

    evidence = result["evidence"]

    examples = [
        str(value)
        for value in evidence.get(
            "example_observation_ids",
            [],
        )
        if value
    ]

    message = (
        "Contract violation on "
        f"{result['resource_type']}."
        f"{result['field_name']}: "
        f"{result['incident_type'].replace('_', ' ')}. "
        f"Expected {result['baseline_value']}; "
        f"observed {result['current_value']}. "
        f"{evidence['bad_rows']} rule failures "
        f"in {evidence['total_rows']} rows."
    )

    if examples:
        message += (
            " Example Observation IDs: "
            + ", ".join(examples)
            + "."
        )

    return message


# ============================================================
# Contract persistence
# ============================================================


def persist_contract_window(
    window,
) -> None:
    """
    Validate one completed Observation window against
    the deterministic contract.

    Every completed window writes:
        - contract_violation_count
        - contract_rows_checked

    Contract failures additionally create incidents.
    Recovered failures resolve existing open incidents.
    """

    window_meta = {
        "resource_type": RESOURCE_TYPE,
        "window_start": window.window_start,
        "window_end": window.window_end,
    }

    results = check_contract(
        window.rows,
        window_meta,
    )

    anomalies = [
        result
        for result in results
        if result["is_anomaly"]
    ]

    rows_checked = len(
        window.rows
    )

    violation_count = sum(
        int(
            result["evidence"]["bad_rows"]
        )
        for result in anomalies
    )

    # --------------------------------------------------------
    # 1. Persist contract metrics for EVERY completed window
    # --------------------------------------------------------

    violation_metric_id = upsert_quality_metric(
        resource_type=RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=CONTRACT_VIOLATION_METRIC,
        field_name=None,
        metric_value=float(
            violation_count
        ),
    )

    upsert_quality_metric(
        resource_type=RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=CONTRACT_ROWS_METRIC,
        field_name=None,
        metric_value=float(
            rows_checked
        ),
    )

    # --------------------------------------------------------
    # 2. Find currently-open contract incidents
    # --------------------------------------------------------

    open_incidents = (
        get_open_incidents_by_types(
            resource_type=RESOURCE_TYPE,
            incident_types=CONTRACT_INCIDENT_TYPES,
        )
    )

    open_by_key = {
        (
            incident["incident_type"],
            incident["field_name"],
        ): incident["id"]
        for incident in open_incidents
    }

    current_keys = {
        (
            result["incident_type"],
            result["field_name"],
        )
        for result in anomalies
    }

    # --------------------------------------------------------
    # 3. Resolve contract problems that disappeared
    # --------------------------------------------------------

    for (
        key,
        incident_id,
    ) in open_by_key.items():

        if key not in current_keys:
            resolve_incident(
                incident_id
            )

            print(
                "  CONTRACT INCIDENT RESOLVED: "
                f"{incident_id}"
            )

    # --------------------------------------------------------
    # 4. Open newly-detected contract incidents
    # --------------------------------------------------------

    for result in anomalies:

        key = (
            result["incident_type"],
            result["field_name"],
        )

        # Already being tracked.
        if key in open_by_key:
            continue

        bad_rows = int(
            result["evidence"]["bad_rows"]
        )

        incident_id = insert_incident(
            resource_type=RESOURCE_TYPE,
            detected_at=window.window_end,
            incident_type=result[
                "incident_type"
            ],
            severity=result["severity"],
            metric_name=(
                CONTRACT_VIOLATION_METRIC
            ),
            field_name=result[
                "field_name"
            ],
            observed_value=float(
                bad_rows
            ),

            # Contract expectation:
            # zero rule violations.
            baseline_value=0.0,

            message=(
                build_contract_incident_message(
                    result
                )
            ),
            status="open",
            quality_metric_id=(
                violation_metric_id
            ),
        )

        print(
            "  CONTRACT INCIDENT OPENED: "
            f"{incident_id}"
        )

    # --------------------------------------------------------
    # 5. Console status
    # --------------------------------------------------------

    status = (
        "PASS"
        if violation_count == 0
        else "FAIL"
    )

    print(
        f"[CONTRACT "
        f"{window.window_start} → "
        f"{window.window_end}] "
        f"{status} | "
        f"rows={rows_checked} | "
        f"violations={violation_count}"
    )


# ============================================================
# Window pipeline wrapper
# ============================================================


def contract_checked_windows(
    windows,
):
    """
    Store window health (record_count, null_rate) and run
    contract validation on every completed window, then pass
    that SAME window to downstream detectors.
    """

    for window in windows:

        # record_count + null_rate for the dashboard
        health = {
            metric["metric_name"]: metric["metric_value"]
            for metric in persist_window_health(window, RESOURCE_TYPE)
        }

        print(
            f"[HEALTH "
            f"{window.window_start} → "
            f"{window.window_end}] "
            f"records={int(health['record_count'])} | "
            f"null_rate={health['null_rate']:.2%}"
        )

        persist_contract_window(
            window
        )

        yield window


# ============================================================
# Main monitor
# ============================================================


def main() -> None:

    config = load_config()

    observation_code = (
        config["observation"]["code"]
    )

    observation_display = (
        config["observation"]["display"]
    )

    field_name = config[
        "field_name"
    ]

    threshold = float(
        config["detection"]["threshold"]
    )

    min_samples = int(
        config["detection"]["min_samples"]
    )

    baseline_proportions = {
        str(category): float(
            proportion
        )
        for category, proportion
        in config[
            "baseline"
        ]["proportions"].items()
    }

    incident_type = config[
        "incident"
    ]["type"]

    metric_name = config[
        "incident"
    ]["metric_name"]

    severity = config[
        "incident"
    ]["severity"]

    # --------------------------------------------------------
    # Startup information
    # --------------------------------------------------------

    print("=" * 70)
    print(
        "SENTINEL CONTINUOUS "
        "DATA-HEALTH MONITOR"
    )
    print("=" * 70)

    print(
        f"Resource:        "
        f"{RESOURCE_TYPE}"
    )

    print(
        f"Observation:     "
        f"{observation_display}"
    )

    print(
        f"FHIR code:       "
        f"{observation_code}"
    )

    print(
        f"Metric:          "
        f"{metric_name}"
    )

    print(
        f"Threshold:       "
        f"{threshold}"
    )

    print(
        f"Min patients:    "
        f"{min_samples}"
    )

    print(
        f"Window:          "
        f"{WINDOW_SECONDS} seconds"
    )

    print(
        "Contract:        enabled"
    )

    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Streaming pipeline
    # --------------------------------------------------------

    rows = consume_observations(
        limit=None
    )

    windows = tumbling_windows(
        rows,
        window_seconds=WINDOW_SECONDS,
    )

    # Contract validation happens first.
    # The exact same Window is then yielded to
    # categorical drift monitoring.
    windows = contract_checked_windows(
        windows
    )

    results = monitor_categorical_drift(
        windows=windows,
        observation_code=observation_code,
        baseline_proportions=(
            baseline_proportions
        ),
        field_name=field_name,
        threshold=threshold,
        min_samples=min_samples,
    )

    # --------------------------------------------------------
    # Monitor completed windows
    # --------------------------------------------------------

    try:

        for result in results:

            detection = result[
                "detection"
            ]

            print(
                f"[{result['window_start']} → "
                f"{result['window_end']}] "
                f"rows={result['window_rows']} "
                f"matching="
                f"{result['matching_rows']} "
                f"patients="
                f"{result['unique_patient_count']}"
            )

            # ------------------------------------------------
            # Not enough unique patients yet
            # ------------------------------------------------

            if not detection[
                "sufficient_data"
            ]:
                print(
                    "  Waiting for enough "
                    "unique patients "
                    f"("
                    f"{result['unique_patient_count']}"
                    f"/{min_samples})"
                )

                print()
                continue

            # ------------------------------------------------
            # JSD result
            # ------------------------------------------------

            js_distance = detection[
                "js_distance"
            ]

            if js_distance is None:
                print(
                    "  No JSD value produced."
                )
                print()
                continue

            # ------------------------------------------------
            # Persist EVERY valid categorical measurement
            # ------------------------------------------------

            quality_metric_id = (
                upsert_quality_metric(
                    resource_type=(
                        RESOURCE_TYPE
                    ),
                    window_start=result[
                        "window_start"
                    ],
                    window_end=result[
                        "window_end"
                    ],
                    metric_name=(
                        metric_name
                    ),
                    field_name=(
                        field_name
                    ),
                    metric_value=(
                        js_distance
                    ),
                )
            )

            print(
                f"  JSD="
                f"{js_distance:.4f} "
                f"| threshold="
                f"{threshold:.4f} "
                f"| metric_id="
                f"{quality_metric_id}"
            )

            # ------------------------------------------------
            # Existing categorical incident?
            # ------------------------------------------------

            open_incident_id = (
                get_open_incident_id(
                    resource_type=(
                        RESOURCE_TYPE
                    ),
                    incident_type=(
                        incident_type
                    ),
                    field_name=(
                        field_name
                    ),
                )
            )

            # ------------------------------------------------
            # Categorical drift detected
            # ------------------------------------------------

            if detection[
                "drift_detected"
            ]:

                print(
                    "  STATUS: DRIFT"
                )

                if open_incident_id is None:

                    proportions = result[
                        "profile"
                    ][
                        "category_proportions"
                    ]

                    message = (
                        build_incident_message(
                            observation_display=(
                                observation_display
                            ),
                            observation_code=(
                                observation_code
                            ),
                            js_distance=(
                                js_distance
                            ),
                            threshold=(
                                threshold
                            ),
                            proportions=(
                                proportions
                            ),
                        )
                    )

                    incident_id = (
                        insert_incident(
                            resource_type=(
                                RESOURCE_TYPE
                            ),
                            detected_at=result[
                                "window_end"
                            ],
                            incident_type=(
                                incident_type
                            ),
                            severity=(
                                severity
                            ),
                            metric_name=(
                                metric_name
                            ),
                            field_name=(
                                field_name
                            ),
                            observed_value=(
                                js_distance
                            ),
                            baseline_value=None,
                            message=message,
                            status="open",
                            quality_metric_id=(
                                quality_metric_id
                            ),
                        )
                    )

                    print(
                        "  INCIDENT OPENED: "
                        f"{incident_id}"
                    )

                else:
                    print(
                        "  Incident already "
                        "open: "
                        f"{open_incident_id}"
                    )

            # ------------------------------------------------
            # Categorical drift healthy / recovered
            # ------------------------------------------------

            else:

                print(
                    "  STATUS: HEALTHY"
                )

                if (
                    open_incident_id
                    is not None
                ):
                    resolve_incident(
                        open_incident_id
                    )

                    print(
                        "  INCIDENT RESOLVED: "
                        f"{open_incident_id}"
                    )

            print()

    except KeyboardInterrupt:

        print()
        print(
            "Sentinel monitor "
            "stopped by user."
        )


if __name__ == "__main__":
    main()