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
from sentinel.streaming.windows import (
    tumbling_windows,
)

from sentinel.detection.missingness import (
    detect_missingness_spike,
)

from sentinel.injection.control import (
    is_injection_enabled,
)
from sentinel.injection.nulls import (
    inject_null_spike,
)

from sentinel.detection.numeric_drift import (
    check_code as check_numeric_drift_code,
)
from sentinel.injection.numeric_drift import (
    inject_record as inject_numeric_record,
    load_baseline as load_numeric_baseline,
    shift_for as numeric_shift_for,
)


from sentinel.detection.volume import (
    detect_volume_drift,
)

from sentinel.injection.volume import (
    inject_volume_failure,
)

VOLUME_INJECTION_MODE = "drop"
VOLUME_INJECTION_FACTOR = 0.25

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


MISSINGNESS_CODE = "8480-6"
MISSINGNESS_DISPLAY = "Systolic Blood Pressure"
MISSINGNESS_FIELD = "numeric_value"

MISSINGNESS_METRIC = "null_rate"
MISSINGNESS_INCIDENT_TYPE = "null_spike"

MISSINGNESS_INJECTION_RATE = 0.30

# Derived from 92 healthy historical windows.
# Every historical null rate was 0.0.
MISSINGNESS_BASELINE_NULL_RATES = [0.0]

NUMERIC_DRIFT_CODE = "8867-4"
NUMERIC_DRIFT_DISPLAY = "Heart rate"
NUMERIC_DRIFT_FIELD = "numeric_value"
NUMERIC_DRIFT_METRIC = "numeric_drift"
NUMERIC_DRIFT_INCIDENT_TYPE = "numeric_drift"


VOLUME_METRIC = "volume"
VOLUME_DROP_INCIDENT_TYPE = "volume_drop"
VOLUME_SPIKE_INCIDENT_TYPE = "volume_spike"

VOLUME_BASELINE_COUNTS = [
    10078,
    11214,
    11676,
    10580,
    10575,
    10910,
    10418,
    10563,
    10462,
    10679,
    11064,
    11494,
    10492,
    11320,
    9894,
    10305,
    10987,
]

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


def persist_volume_window(
    window,
) -> None:
    observed_count = len(window.rows)

    detection = detect_volume_drift(
        observed_count=observed_count,
        baseline_counts=VOLUME_BASELINE_COUNTS,
    )

    metric_id = upsert_quality_metric(
        resource_type=RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=VOLUME_METRIC,
        field_name=None,
        metric_value=float(observed_count),
    )

    open_drop_id = get_open_incident_id(
        resource_type=RESOURCE_TYPE,
        incident_type=VOLUME_DROP_INCIDENT_TYPE,
        field_name=None,
    )

    open_spike_id = get_open_incident_id(
        resource_type=RESOURCE_TYPE,
        incident_type=VOLUME_SPIKE_INCIDENT_TYPE,
        field_name=None,
    )

    if detection["is_anomaly"]:

        incident_type = (
            VOLUME_DROP_INCIDENT_TYPE
            if detection["direction"] == "drop"
            else VOLUME_SPIKE_INCIDENT_TYPE
        )

        existing_id = (
            open_drop_id
            if detection["direction"] == "drop"
            else open_spike_id
        )

        opposite_id = (
            open_spike_id
            if detection["direction"] == "drop"
            else open_drop_id
        )

        if opposite_id is not None:
            resolve_incident(opposite_id)

        if existing_id is None:
            incident_id = insert_incident(
                resource_type=RESOURCE_TYPE,
                detected_at=window.window_end,
                incident_type=incident_type,
                severity=detection["severity"],
                metric_name=VOLUME_METRIC,
                field_name=None,
                observed_value=float(observed_count),
                baseline_value=float(
                    detection["expected_count"]
                ),
                message=(
                    f"Volume {detection['direction']} detected. "
                    f"Observed {observed_count} rows; "
                    f"expected approximately "
                    f"{detection['expected_count']:.0f}. "
                    f"Change: "
                    f"{detection['change_percent']:.1f}%."
                ),
                status="open",
                quality_metric_id=metric_id,
            )

            print(
                f"  VOLUME INCIDENT OPENED: "
                f"{incident_id}"
            )

    else:
        if open_drop_id is not None:
            resolve_incident(open_drop_id)
            print(
                f"  VOLUME INCIDENT RESOLVED: "
                f"{open_drop_id}"
            )

        if open_spike_id is not None:
            resolve_incident(open_spike_id)
            print(
                f"  VOLUME INCIDENT RESOLVED: "
                f"{open_spike_id}"
            )

    status = (
        "FAIL"
        if detection["is_anomaly"]
        else "PASS"
    )

    print(
        f"[VOLUME "
        f"{window.window_start} → "
        f"{window.window_end}] "
        f"{status} | "
        f"rows={observed_count} | "
        f"expected={detection['expected_count']:.0f} | "
        f"change={detection['change_percent']:.1f}%"
    )
    
def volume_checked_windows(
    windows,
):
    for window in windows:

        persist_volume_window(
            window
        )

        yield window
        
def persist_missingness_window(
    window,
) -> None:
    """
    Monitor numeric_value missingness for
    Systolic Blood Pressure observations.
    """

    rows = [
        row
        for row in window.rows
        if (
            row.get("code") == MISSINGNESS_CODE
            and row.get("value_type") == "numeric"
        )
    ]

    # Nothing to evaluate in this window.
    if not rows:
        print(
            f"[MISSINGNESS "
            f"{window.window_start} → "
            f"{window.window_end}] "
            "SKIP | no matching observations"
        )
        return

    null_count = sum(
        row.get(MISSINGNESS_FIELD) is None
        for row in rows
    )

    observed_null_rate = (
        null_count / len(rows)
    )

    detection = detect_missingness_spike(
        observed_null_rate=observed_null_rate,
        baseline_null_rates=(
            MISSINGNESS_BASELINE_NULL_RATES
        ),
    )

    # --------------------------------------------------------
    # Persist metric
    # --------------------------------------------------------

    metric_id = upsert_quality_metric(
        resource_type=RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=MISSINGNESS_METRIC,
        field_name=MISSINGNESS_FIELD,
        metric_value=observed_null_rate,
    )

    # --------------------------------------------------------
    # Find existing incident
    # --------------------------------------------------------

    open_incident_id = get_open_incident_id(
        resource_type=RESOURCE_TYPE,
        incident_type=MISSINGNESS_INCIDENT_TYPE,
        field_name=MISSINGNESS_FIELD,
    )

    # --------------------------------------------------------
    # Open incident
    # --------------------------------------------------------

    if (
        detection["is_anomaly"]
        and open_incident_id is None
    ):

        incident_id = insert_incident(
            resource_type=RESOURCE_TYPE,
            detected_at=window.window_end,
            incident_type=(
                MISSINGNESS_INCIDENT_TYPE
            ),
            severity=detection["severity"],
            metric_name=MISSINGNESS_METRIC,
            field_name=MISSINGNESS_FIELD,
            observed_value=observed_null_rate,
            baseline_value=detection[
                "baseline_null_rate"
            ],
            message=(
                f"Missingness spike detected for "
                f"{MISSINGNESS_DISPLAY} "
                f"({MISSINGNESS_CODE}). "
                f"numeric_value null rate increased "
                f"from "
                f"{detection['baseline_null_rate']:.1%} "
                f"to {observed_null_rate:.1%}. "
                f"Threshold: "
                f"{detection['threshold']:.1%}."
            ),
            status="open",
            quality_metric_id=metric_id,
        )

        print(
            "  MISSINGNESS INCIDENT OPENED: "
            f"{incident_id}"
        )

    # --------------------------------------------------------
    # Resolve incident
    # --------------------------------------------------------

    elif (
        not detection["is_anomaly"]
        and open_incident_id is not None
    ):

        resolve_incident(
            open_incident_id
        )

        print(
            "  MISSINGNESS INCIDENT RESOLVED: "
            f"{open_incident_id}"
        )

    # --------------------------------------------------------
    # Console status
    # --------------------------------------------------------

    status = (
        "FAIL"
        if detection["is_anomaly"]
        else "PASS"
    )

    print(
        f"[MISSINGNESS "
        f"{window.window_start} → "
        f"{window.window_end}] "
        f"{status} | "
        f"{MISSINGNESS_DISPLAY} | "
        f"rows={len(rows)} | "
        f"nulls={null_count} | "
        f"rate={observed_null_rate:.1%} | "
        f"threshold="
        f"{detection['threshold']:.1%}"
    )


def persist_numeric_drift_window(
    window,
    baseline: dict,
) -> None:
    """
    Monitor Heart Rate numeric distribution drift.
    """

    window_meta = {
        "resource_type": RESOURCE_TYPE,
        "window_start": window.window_start,
        "window_end": window.window_end,
    }

    result = check_numeric_drift_code(
        NUMERIC_DRIFT_CODE,
        window.rows,
        window_meta,
        baseline.get(NUMERIC_DRIFT_CODE),
    )

    evidence = result["evidence"]

    # Not enough live values yet.
    if result["incident_type"] == "insufficient_data":
        print(
            f"[NUMERIC DRIFT "
            f"{window.window_start} → "
            f"{window.window_end}] "
            f"SKIP | {NUMERIC_DRIFT_DISPLAY} | "
            f"samples={evidence['current_n']}"
        )
        return

    if result["incident_type"] == "no_baseline":
        print(
            "[NUMERIC DRIFT] SKIP | no baseline"
        )
        return

    ks_statistic = float(
        evidence["ks_statistic"]
    )

    metric_id = upsert_quality_metric(
        resource_type=RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=NUMERIC_DRIFT_METRIC,
        field_name=NUMERIC_DRIFT_FIELD,
        metric_value=ks_statistic,
    )

    open_incident_id = get_open_incident_id(
        resource_type=RESOURCE_TYPE,
        incident_type=NUMERIC_DRIFT_INCIDENT_TYPE,
        field_name=NUMERIC_DRIFT_FIELD,
    )

    if (
        result["is_anomaly"]
        and open_incident_id is None
    ):
        incident_id = insert_incident(
            resource_type=RESOURCE_TYPE,
            detected_at=window.window_end,
            incident_type=NUMERIC_DRIFT_INCIDENT_TYPE,
            severity=result["severity"],
            metric_name=NUMERIC_DRIFT_METRIC,
            field_name=NUMERIC_DRIFT_FIELD,
            observed_value=ks_statistic,
            baseline_value=0.15,
            message=(
                f"Numeric distribution drift detected for "
                f"{NUMERIC_DRIFT_DISPLAY} "
                f"({NUMERIC_DRIFT_CODE}). "
                f"KS statistic={ks_statistic:.4f}, "
                f"p-value={evidence['p_value']:.4g}, "
                f"median shift="
                f"{evidence['median_shift']:.2f}."
            ),
            status="open",
            quality_metric_id=metric_id,
        )

        print(
            "  NUMERIC DRIFT INCIDENT OPENED: "
            f"{incident_id}"
        )

    elif (
        not result["is_anomaly"]
        and open_incident_id is not None
    ):
        resolve_incident(
            open_incident_id
        )

        print(
            "  NUMERIC DRIFT INCIDENT RESOLVED: "
            f"{open_incident_id}"
        )

    status = (
        "FAIL"
        if result["is_anomaly"]
        else "PASS"
    )

    print(
        f"[NUMERIC DRIFT "
        f"{window.window_start} → "
        f"{window.window_end}] "
        f"{status} | "
        f"{NUMERIC_DRIFT_DISPLAY} | "
        f"samples={evidence['current_n']} | "
        f"KS={ks_statistic:.4f} | "
        f"median_shift="
        f"{evidence['median_shift']:.2f}"
    )
    
def numeric_drift_checked_windows(
    windows,
    baseline,
):
    for window in windows:

        persist_numeric_drift_window(
            window,
            baseline,
        )

        yield window
        
# ============================================================
# Window pipeline wrapper
# ============================================================


def injected_windows(
    windows,
    numeric_baseline,
):
    """
    Apply controlled failure injections to completed
    normalized windows before any detector sees them.
    """

    last_missingness_state = None
    last_numeric_state = None
    last_volume_state = None

    numeric_shift = numeric_shift_for(
        numeric_baseline[NUMERIC_DRIFT_CODE]
    )

    for window in windows:
        
        # ====================================================
        # Volume injection
        # ====================================================

        volume_enabled = is_injection_enabled(
            "volume"
        )

        if volume_enabled != last_volume_state:
            print(
                "\nControlled volume injection: "
                + (
                    "ON"
                    if volume_enabled
                    else "OFF"
                )
            )

            if volume_enabled:
                print(
                    f"Keeping only "
                    f"{VOLUME_INJECTION_FACTOR:.0%} "
                    f"of rows to simulate "
                    f"a volume drop"
                )

            last_volume_state = volume_enabled

        if volume_enabled:
            window.rows = inject_volume_failure(
                window.rows,
                mode=VOLUME_INJECTION_MODE,
                factor=VOLUME_INJECTION_FACTOR,
            )

        # ====================================================
        # Missingness injection
        # ====================================================

        missingness_enabled = is_injection_enabled(
            "missingness"
        )

        if missingness_enabled != last_missingness_state:
            print(
                "\nControlled missingness injection: "
                + (
                    "ON"
                    if missingness_enabled
                    else "OFF"
                )
            )

            if missingness_enabled:
                print(
                    f"Injecting "
                    f"{MISSINGNESS_INJECTION_RATE:.0%} "
                    f"nulls into "
                    f"{MISSINGNESS_DISPLAY} "
                    f"({MISSINGNESS_CODE})"
                )

            last_missingness_state = (
                missingness_enabled
            )

        if missingness_enabled:

            matching_indexes = [
                index
                for index, row
                in enumerate(window.rows)
                if (
                    row.get("code")
                    == MISSINGNESS_CODE
                    and row.get("value_type")
                    == "numeric"
                )
            ]

            matching_rows = [
                window.rows[index]
                for index in matching_indexes
            ]

            injected_rows = inject_null_spike(
                matching_rows,
                field_name=MISSINGNESS_FIELD,
                null_rate=MISSINGNESS_INJECTION_RATE,
            )

            for index, injected_row in zip(
                matching_indexes,
                injected_rows,
            ):
                window.rows[index] = injected_row

        # ====================================================
        # Numeric drift injection
        # ====================================================

        numeric_enabled = is_injection_enabled(
            "numeric"
        )

        if numeric_enabled != last_numeric_state:
            print(
                "\nControlled numeric drift injection: "
                + (
                    "ON"
                    if numeric_enabled
                    else "OFF"
                )
            )

            if numeric_enabled:
                print(
                    f"Shifting "
                    f"{NUMERIC_DRIFT_DISPLAY} "
                    f"({NUMERIC_DRIFT_CODE}) "
                    f"by +{numeric_shift}"
                )

            last_numeric_state = numeric_enabled

        if numeric_enabled:

            window.rows = [
                inject_numeric_record(
                    row,
                    NUMERIC_DRIFT_CODE,
                    numeric_shift,
                )
                for row in window.rows
            ]

        yield window

def contract_checked_windows(
    windows,
):
    """
    Run contract validation on every completed window,
    then pass that SAME window to downstream detectors.
    """

    for window in windows:

        persist_contract_window(
            window
        )

        yield window
        
def missingness_checked_windows(
    windows,
):
    """
    Run missingness detection on every completed window,
    then pass the same window downstream.
    """

    for window in windows:

        persist_missingness_window(
            window
        )

        yield window


# ============================================================
# Main monitor
# ============================================================


def main() -> None:
    
    numeric_baseline = load_numeric_baseline()

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

    windows = injected_windows(
        windows,
        numeric_baseline,
    )
    
    windows = volume_checked_windows(
        windows
    )

    windows = contract_checked_windows(
        windows
    )

    windows = missingness_checked_windows(
    windows
    )

    windows = numeric_drift_checked_windows(
        windows,
        numeric_baseline,
    )

    results = monitor_categorical_drift(
        windows=windows,
        observation_code=observation_code,
        baseline_proportions=baseline_proportions,
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