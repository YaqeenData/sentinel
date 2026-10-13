from collections import OrderedDict, deque
from pathlib import Path
from statistics import median

import yaml

from sentinel.baseline.builder import (
    BASELINES_PATH,
    load_baselines,
)
from sentinel.detection.categorical_drift import (
    detect_categorical_drift,
)
from sentinel.detection.categorical_monitor import (
    monitor_categorical_drift,
)
from sentinel.detection.contract import (
    check as check_contract,
)
from sentinel.detection.encounter_contract import (
    ALLOWED_CLASS_CODES,
    check as check_encounter_contract,
)
from sentinel.detection.missingness import (
    detect_missingness_spike,
)
from sentinel.detection.numeric_drift import (
    MIN_SAMPLES as NUMERIC_MIN_PATIENTS,
    MONITORED_CODES,
    check as check_numeric,
    is_number,
)
from sentinel.detection.patient_contract import (
    check as check_patient_contract,
)
from sentinel.detection.volume import (
    detect_volume_drift,
)
from sentinel.profiling.categorical import (
    profile_categorical,
)
from sentinel.storage.postgres import (
    get_open_incident_id,
    get_open_incidents_by_types,
    insert_incident,
    resolve_incident,
    upsert_quality_metric,
)
from sentinel.streaming.consumer import (
    RESOURCE_TYPE_FIELD,
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

RESOURCE_TYPE = "Observation"
PATIENT_RESOURCE_TYPE = "Patient"
ENCOUNTER_RESOURCE_TYPE = "Encounter"
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

MISSINGNESS_FIELD = "numeric_value"
MISSINGNESS_METRIC = "null_rate"
MISSINGNESS_INCIDENT_TYPE = "null_spike"
MISSINGNESS_HISTORY = 10   # healthy windows kept as the baseline
MISSINGNESS_WARMUP = 5     # healthy windows needed before judging
MISSINGNESS_MIN_ROWS = 20  # numeric rows needed in one window

VOLUME_METRIC = "record_count"
VOLUME_INCIDENT_TYPE = "volume_drop"
VOLUME_HISTORY = 10   # healthy windows kept as the baseline
VOLUME_WARMUP = 5     # healthy windows needed before judging

NUMERIC_FIELD = "numeric_value"
NUMERIC_METRIC = "median"
NUMERIC_INCIDENT_TYPE = "numeric_drift"
NUMERIC_SKIP_TYPES = ("no_baseline", "insufficient_data")
# One value per patient (their median), so a window full of
# a few patients cannot look like a whole-population shift.
NUMERIC_REFERENCE_PATIENTS = 100  # reference size per code
NUMERIC_REFERENCE_MAX_WINDOWS = 20  # freeze anyway after this, if >= min patients
NUMERIC_CURRENT_PATIENTS = 50     # most recent patients compared per code


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


def load_encounter_config() -> dict | None:
    """encounter_class_drift block of monitoring.yaml, or None."""

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file) or {}

    return config.get("encounter_class_drift")


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

    # Observation results carry example_observation_ids,
    # Patient results example_patient_ids,
    # Encounter results example_encounter_ids.
    examples = [
        str(value)
        for value in (
            evidence.get("example_observation_ids")
            or evidence.get("example_patient_ids")
            or evidence.get("example_encounter_ids")
            or []
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
            f" Example {result['resource_type']} IDs: "
            + ", ".join(examples)
            + "."
        )

    return message


# ============================================================
# Contract persistence
# ============================================================


def persist_contract_window(
    window,
    *,
    rows: list[dict] | None = None,
    resource_type: str = RESOURCE_TYPE,
    check=check_contract,
    label: str = "CONTRACT",
) -> None:
    """
    Validate one completed window against the deterministic
    contract of one resource type.

    By default this is the Observation contract on all rows of
    the window. The Patient contract passes its own rows,
    resource_type and check function, and reuses everything else.

    Every completed window writes:
        - contract_violation_count
        - contract_rows_checked

    Contract failures additionally create incidents.
    Recovered failures resolve existing open incidents.
    """

    if rows is None:
        rows = window.rows

    window_meta = {
        "resource_type": resource_type,
        "window_start": window.window_start,
        "window_end": window.window_end,
    }

    results = check(
        rows,
        window_meta,
    )

    anomalies = [
        result
        for result in results
        if result["is_anomaly"]
    ]

    rows_checked = len(
        rows
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
        resource_type=resource_type,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=CONTRACT_VIOLATION_METRIC,
        field_name=None,
        metric_value=float(
            violation_count
        ),
    )

    upsert_quality_metric(
        resource_type=resource_type,
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
            resource_type=resource_type,
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
                f"  {label} INCIDENT RESOLVED: "
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
            resource_type=resource_type,
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
            f"  {label} INCIDENT OPENED: "
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
        f"[{label} "
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
    Run contract validation on every completed window,
    then pass that SAME window to downstream detectors.
    """

    for window in windows:

        persist_contract_window(
            window
        )

        yield window


# ============================================================
# Patient contract + split Patients from Observations
# ============================================================


def patient_checked_windows(
    windows,
):
    """
    First step of the pipeline.

    The consumer now sends Patient rows and Observation rows in
    the same windows. For every window this:
      1. runs the Patient contract on the Patient rows, and
      2. yields a copy of the window with ONLY the Observation rows,
         so every Observation detector after it stays unchanged.

    A window with no Patients is skipped for the Patient contract:
    there is nothing to judge, so open Patient incidents stay open
    until Patients arrive again.
    """

    for window in windows:

        patient_rows = [
            row
            for row in window.rows
            if row.get(RESOURCE_TYPE_FIELD) == PATIENT_RESOURCE_TYPE
        ]

        observation_rows = [
            row
            for row in window.rows
            if row.get(RESOURCE_TYPE_FIELD, RESOURCE_TYPE) == RESOURCE_TYPE
        ]

        if patient_rows:
            persist_contract_window(
                window,
                rows=patient_rows,
                resource_type=PATIENT_RESOURCE_TYPE,
                check=check_patient_contract,
                label="PATIENT CONTRACT",
            )
        else:
            print(
                f"[PATIENT CONTRACT "
                f"{window.window_start} → "
                f"{window.window_end}] "
                "SKIP | no patients in window"
            )

        yield Window(
            window_start=window.window_start,
            window_end=window.window_end,
            rows=observation_rows,
        )


# ============================================================
# Encounter class drift (JSD on the last N distinct encounters)
# ============================================================


def encounter_class_settings(
    config: dict | None,
    baselines: dict | None,
) -> dict | None:
    """
    Everything the Encounter class check needs, in one dict.

    The reference proportions come from Silver
    (baselines.json → encounter_class). Without them the
    check is turned off: there is nothing to compare with.
    """

    if not config:
        return None

    silver = (baselines or {}).get("encounter_class") or {}
    proportions = silver.get("proportions")

    if not proportions:
        return None

    return {
        "field_name": str(config.get("field_name", "class_code")),
        "threshold": float(config["detection"]["threshold"]),
        "min_samples": int(config["detection"]["min_samples"]),
        "incident_type": config["incident"]["type"],
        "metric_name": config["incident"]["metric_name"],
        "severity": config["incident"]["severity"],
        "baseline_proportions": {
            str(category): float(share)
            for category, share in proportions.items()
        },
    }


def build_encounter_incident_message(
    *,
    field_name: str,
    js_distance: float,
    threshold: float,
    sample_size: int,
    observed: dict[str, float],
    baseline: dict[str, float],
) -> str:

    def as_percent(proportions: dict[str, float]) -> str:
        ordered = sorted(
            proportions.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        return ", ".join(
            f"{category} {share:.1%}"
            for category, share in ordered
        )

    return (
        "Categorical distribution drift detected for "
        f"{ENCOUNTER_RESOURCE_TYPE}.{field_name}. "
        f"Jensen-Shannon distance {js_distance:.4f} "
        f"exceeded threshold {threshold:.2f} "
        f"on the last {sample_size} encounters. "
        f"Observed: {as_percent(observed)}. "
        f"Silver baseline: {as_percent(baseline)}."
    )


def persist_encounter_window(
    window,
    new_rows: list[dict],
    buffer: OrderedDict,
    settings: dict,
) -> None:
    """
    Add this window's Encounters to the buffer of the last
    N distinct encounters, then compare the class mix of the
    buffer with the Silver proportions (Jensen-Shannon distance).

    N = min_samples (1000): about 1.2 minutes of stream.
    A smaller sample gives false alarms (N=100 → 10% of healthy
    samples crossed 0.20); 1000 gave none.
    """

    label = (
        f"[ENCOUNTER CLASS {window.window_start} → "
        f"{window.window_end}]"
    )

    field_name = settings["field_name"]
    min_samples = settings["min_samples"]

    if not new_rows:
        print(f"{label} SKIP | no encounters in window")
        return

    # --------------------------------------------------------
    # 1. Keep the last N distinct encounters
    # --------------------------------------------------------

    for row in new_rows:
        encounter_id = row.get("encounter_id")

        if not encounter_id:
            continue

        if encounter_id in buffer:
            buffer.move_to_end(encounter_id)

        buffer[encounter_id] = row

        while len(buffer) > min_samples:
            buffer.popitem(last=False)

    sample_size = len(buffer)

    if sample_size < min_samples:
        print(
            f"{label} WAIT | encounters={sample_size}/{min_samples} "
            f"| new={len(new_rows)}"
        )
        return

    # --------------------------------------------------------
    # 2. Profile + JSD against Silver
    # --------------------------------------------------------

    profile = profile_categorical(
        records=list(buffer.values()),
        field_name=field_name,
    )

    observed = profile["category_proportions"]

    detection = detect_categorical_drift(
        baseline_proportions=settings["baseline_proportions"],
        current_proportions=observed,
        current_count=sample_size,
        threshold=settings["threshold"],
        min_samples=min_samples,
    )

    js_distance = detection.get("js_distance")

    if js_distance is None:
        print(f"{label} SKIP | no JSD value produced")
        return

    metric_id = upsert_quality_metric(
        resource_type=ENCOUNTER_RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=settings["metric_name"],
        field_name=field_name,
        metric_value=float(js_distance),
    )

    open_id = get_open_incident_id(
        resource_type=ENCOUNTER_RESOURCE_TYPE,
        incident_type=settings["incident_type"],
        field_name=field_name,
    )

    # --------------------------------------------------------
    # 3. Open or resolve the incident
    # --------------------------------------------------------

    if detection["drift_detected"]:
        status = "DRIFT"

        if open_id is None:
            incident_id = insert_incident(
                resource_type=ENCOUNTER_RESOURCE_TYPE,
                detected_at=window.window_end,
                incident_type=settings["incident_type"],
                severity=settings["severity"],
                metric_name=settings["metric_name"],
                field_name=field_name,
                observed_value=float(js_distance),
                baseline_value=None,
                message=build_encounter_incident_message(
                    field_name=field_name,
                    js_distance=float(js_distance),
                    threshold=settings["threshold"],
                    sample_size=sample_size,
                    observed=observed,
                    baseline=settings["baseline_proportions"],
                ),
                status="open",
                quality_metric_id=metric_id,
            )
            print(f"  ENCOUNTER CLASS INCIDENT OPENED: {incident_id}")
        else:
            print(f"  Encounter class incident already open: {open_id}")

    else:
        status = "HEALTHY"

        if open_id is not None:
            resolve_incident(open_id)
            print(f"  ENCOUNTER CLASS INCIDENT RESOLVED: {open_id}")

    amb = observed.get("AMB", 0.0)
    emer = observed.get("EMER", 0.0)

    print(
        f"{label} {status} "
        f"| JSD={js_distance:.4f} "
        f"| threshold={settings['threshold']:.2f} "
        f"| AMB={amb:.1%} EMER={emer:.1%} "
        f"| encounters={sample_size} new={len(new_rows)}"
    )


def encounter_checked_windows(
    windows,
    settings: dict | None,
):
    """
    First step of the pipeline.

    For every window this:
      1. runs the Encounter contract on the Encounter rows,
      2. runs the Encounter class check on the rows whose class_code
         is a valid FHIR class, and
      3. yields a copy of the window WITHOUT the Encounter rows,
         so every detector after it stays unchanged.

    A missing or unknown class_code is a broken record, not drift:
    the contract reports it, and the class mix never counts it.

    settings None (no Silver encounter_class baseline, or no
    encounter_class_drift block in monitoring.yaml) → the class check is
    off; the contract still runs and Encounter rows are still removed.
    """

    buffer: OrderedDict = OrderedDict()

    for window in windows:

        encounter_rows = [
            row
            for row in window.rows
            if row.get(RESOURCE_TYPE_FIELD) == ENCOUNTER_RESOURCE_TYPE
        ]

        other_rows = [
            row
            for row in window.rows
            if row.get(RESOURCE_TYPE_FIELD) != ENCOUNTER_RESOURCE_TYPE
        ]

        if encounter_rows:
            persist_contract_window(
                window,
                rows=encounter_rows,
                resource_type=ENCOUNTER_RESOURCE_TYPE,
                check=check_encounter_contract,
                label="ENCOUNTER CONTRACT",
            )
        else:
            print(
                f"[ENCOUNTER CONTRACT "
                f"{window.window_start} → "
                f"{window.window_end}] "
                "SKIP | no encounters in window"
            )

        if settings is not None:
            field_name = settings["field_name"]
            valid_rows = [
                row
                for row in encounter_rows
                if row.get(field_name) in ALLOWED_CLASS_CODES
            ]
            persist_encounter_window(
                window,
                valid_rows,
                buffer,
                settings,
            )

        yield Window(
            window_start=window.window_start,
            window_end=window.window_end,
            rows=other_rows,
        )


# ============================================================
# Missingness (null spike on numeric_value)
# ============================================================


def load_numeric_codes() -> set[str]:
    """LOINC codes of numeric measurements, from monitoring.yaml."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    observations = (
        (config.get("numeric_drift") or {}).get("observations") or []
    )

    return {str(item["code"]) for item in observations}


def numeric_null_rate(
    rows: list[dict],
    codes: set[str],
) -> tuple[float | None, int]:
    """
    Share of numeric rows whose value is missing.

    Only numeric measurements count: categorical rows
    (e.g. smoking status) never carry numeric_value.
    """

    numeric_rows = [
        row for row in rows
        if row.get("code") in codes
    ]

    if not numeric_rows:
        return None, 0

    missing = sum(
        1 for row in numeric_rows
        if row.get(MISSINGNESS_FIELD) is None
    )

    return missing / len(numeric_rows), len(numeric_rows)


def persist_missingness_window(
    window,
    codes: set[str],
    history: deque,
    learn: bool = True,
) -> None:
    """
    Compare this window's null rate with the baseline null rates.

    With a Silver baseline (learn=False) the history is fixed:
    live windows never change it.

    Without one (learn=True) healthy live windows feed the history;
    spiked windows do not, so an ongoing problem never becomes
    the new normal.
    """

    label = (
        f"[MISSINGNESS {window.window_start} → "
        f"{window.window_end}]"
    )

    rate, checked = numeric_null_rate(window.rows, codes)

    if rate is None or checked < MISSINGNESS_MIN_ROWS:
        print(f"{label} SKIP | numeric rows={checked}")
        return

    metric_id = upsert_quality_metric(
        resource_type=RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=MISSINGNESS_METRIC,
        field_name=MISSINGNESS_FIELD,
        metric_value=rate,
    )

    if len(history) < MISSINGNESS_WARMUP:
        history.append(rate)
        print(
            f"{label} WARMUP {len(history)}/{MISSINGNESS_WARMUP} "
            f"| null_rate={rate:.3f} | rows={checked}"
        )
        return

    result = detect_missingness_spike(rate, list(history))

    open_id = get_open_incident_id(
        resource_type=RESOURCE_TYPE,
        incident_type=MISSINGNESS_INCIDENT_TYPE,
        field_name=MISSINGNESS_FIELD,
    )

    if result["is_anomaly"]:
        status = "SPIKE"

        if open_id is None:
            incident_id = insert_incident(
                resource_type=RESOURCE_TYPE,
                detected_at=window.window_end,
                incident_type=MISSINGNESS_INCIDENT_TYPE,
                severity=result["severity"],
                metric_name=MISSINGNESS_METRIC,
                field_name=MISSINGNESS_FIELD,
                observed_value=rate,
                baseline_value=result["baseline_null_rate"],
                message=(
                    f"Null spike on {RESOURCE_TYPE}."
                    f"{MISSINGNESS_FIELD}: "
                    f"{rate:.1%} missing vs baseline "
                    f"{result['baseline_null_rate']:.1%} "
                    f"(threshold +{result['threshold']:.1%}) "
                    f"in {checked} numeric rows."
                ),
                status="open",
                quality_metric_id=metric_id,
            )
            print(f"  NULL SPIKE INCIDENT OPENED: {incident_id}")
        else:
            print(f"  Null spike incident already open: {open_id}")

    else:
        status = "HEALTHY"

        if learn:
            history.append(rate)

        if open_id is not None:
            resolve_incident(open_id)
            print(f"  NULL SPIKE INCIDENT RESOLVED: {open_id}")

    print(
        f"{label} {status} "
        f"| null_rate={rate:.3f} "
        f"| baseline={result['baseline_null_rate']:.3f} "
        f"| threshold=+{result['threshold']:.3f} "
        f"| rows={checked}"
    )


def missingness_checked_windows(
    windows,
    codes: set[str],
    baseline_null_rates: list[float] | None = None,
):
    """
    Run the null-spike check, then pass the SAME window on.

    baseline_null_rates: null rates of historical Silver windows.
    When given, they are the fixed baseline and no warm-up is needed.
    When None, the baseline is learned from the first healthy windows.
    """

    if baseline_null_rates:
        history: deque = deque(baseline_null_rates)
        learn = False
    else:
        history = deque(maxlen=MISSINGNESS_HISTORY)
        learn = True

    for window in windows:
        persist_missingness_window(window, codes, history, learn)
        yield window


# ============================================================
# Volume (record count per window)
# ============================================================


def persist_volume_window(
    window,
    history: deque,
) -> None:
    """
    Compare this window's record count with recent healthy windows.

    Drops open a volume_drop incident. Spikes are logged only,
    because the schema has no volume_spike type yet.
    """

    label = (
        f"[VOLUME {window.window_start} → "
        f"{window.window_end}]"
    )

    count = len(window.rows)

    metric_id = upsert_quality_metric(
        resource_type=RESOURCE_TYPE,
        window_start=window.window_start,
        window_end=window.window_end,
        metric_name=VOLUME_METRIC,
        field_name=None,
        metric_value=float(count),
    )

    if len(history) < VOLUME_WARMUP:
        history.append(count)
        print(
            f"{label} WARMUP {len(history)}/{VOLUME_WARMUP} "
            f"| rows={count}"
        )
        return

    result = detect_volume_drift(count, list(history))

    # Looked up by type: field_name is NULL for volume.
    open_ids = [
        incident["id"]
        for incident in get_open_incidents_by_types(
            resource_type=RESOURCE_TYPE,
            incident_types=(VOLUME_INCIDENT_TYPE,),
        )
    ]

    if result["is_anomaly"] and result["direction"] == "drop":
        status = "DROP"

        if not open_ids:
            incident_id = insert_incident(
                resource_type=RESOURCE_TYPE,
                detected_at=window.window_end,
                incident_type=VOLUME_INCIDENT_TYPE,
                severity=result["severity"],
                metric_name=VOLUME_METRIC,
                field_name=None,
                observed_value=float(count),
                baseline_value=float(result["expected_count"]),
                message=(
                    f"Volume drop on {RESOURCE_TYPE}: "
                    f"{count} records vs expected "
                    f"{result['expected_count']:.0f} "
                    f"({result['change_percent']:+.1f}%)."
                ),
                status="open",
                quality_metric_id=metric_id,
            )
            print(f"  VOLUME INCIDENT OPENED: {incident_id}")
        else:
            print(f"  Volume incident already open: {open_ids[0]}")

    else:
        if result["is_anomaly"]:
            # Spike: logged, not stored as an incident yet.
            status = "SPIKE"
        else:
            status = "HEALTHY"
            history.append(count)

        for incident_id in open_ids:
            resolve_incident(incident_id)
            print(f"  VOLUME INCIDENT RESOLVED: {incident_id}")

    change = result["change_percent"]
    change_text = f"{change:+.1f}%" if change is not None else "n/a"

    print(
        f"{label} {status} "
        f"| rows={count} "
        f"| expected={result['expected_count']:.0f} "
        f"| change={change_text} "
        f"| threshold=±{result['threshold']:.0f}"
    )


def volume_checked_windows(
    windows,
):
    """Run the volume check, then pass the SAME window on."""

    history: deque = deque(maxlen=VOLUME_HISTORY)

    for window in windows:
        persist_volume_window(window, history)
        yield window


# ============================================================
# Numeric drift (KS test on one value per patient)
# ============================================================


def numeric_field(code: str) -> str:
    """numeric_value:8867-4, the field_name the dashboard expects."""

    return f"{NUMERIC_FIELD}:{code}"


def numeric_readings(rows: list[dict]):
    """Yield (code, patient_id, value) for valid monitored readings."""

    for row in rows:
        code = row.get("code")
        patient_id = row.get("patient_id")
        value = row.get(NUMERIC_FIELD)

        if (
            code in MONITORED_CODES
            and patient_id is not None
            and is_number(value)
        ):
            yield code, patient_id, float(value)


def add_reference_readings(
    rows: list[dict],
    reference: dict[str, dict[str, list[float]]],
) -> None:
    """Fill the reference until it holds enough patients per code."""

    for code, patient_id, value in numeric_readings(rows):
        patients = reference[code]

        if (
            patient_id not in patients
            and len(patients) >= NUMERIC_REFERENCE_PATIENTS
        ):
            continue

        patients.setdefault(patient_id, []).append(value)


def add_current_readings(
    rows: list[dict],
    current: dict[str, OrderedDict],
) -> None:
    """Keep the most recent patients per code (oldest dropped first)."""

    for code, patient_id, value in numeric_readings(rows):
        patients = current[code]

        if patient_id in patients:
            patients.move_to_end(patient_id)

        patients.setdefault(patient_id, []).append(value)

        while len(patients) > NUMERIC_CURRENT_PATIENTS:
            patients.popitem(last=False)


def patient_medians(patients: dict[str, list[float]]) -> list[float]:
    return [median(values) for values in patients.values()]


def reference_is_ready(state: dict) -> bool:
    sizes = [len(p) for p in state["reference"].values()]

    if all(size >= NUMERIC_REFERENCE_PATIENTS for size in sizes):
        return True

    return (
        state["reference_windows"] >= NUMERIC_REFERENCE_MAX_WINDOWS
        and all(size >= NUMERIC_MIN_PATIENTS for size in sizes)
    )


def build_numeric_message(
    result: dict,
) -> str:
    """Same wording the dashboard parses: 'KS D=0.353 (p=...)'."""

    evidence = result["evidence"]
    name = evidence.get("name") or evidence["code"]

    return (
        f"{name} ({evidence['code']}): "
        f"KS D={evidence['ks_statistic']:.3f} "
        f"(p={evidence['p_value']:.1e}), "
        f"median {result['baseline_value']:.2f} → "
        f"{result['current_value']:.2f} "
        f"(shift {evidence['median_shift']:+.2f}) "
        f"across {evidence['current_n']} patients."
    )


def persist_numeric_window(
    window,
    state: dict,
) -> None:
    """
    Phase 1: build a reference of patient medians per code, then freeze it.
    Phase 2: compare the latest patients' medians with that reference
             using the KS check in detection/numeric_drift.py.

    Every judged code writes the median of patient medians to
    quality_metrics, so healthy windows show on the chart too.
    """

    label = (
        f"[NUMERIC {window.window_start} → "
        f"{window.window_end}]"
    )

    # --------------------------------------------------------
    # 1. Reference phase
    # --------------------------------------------------------

    if state["frozen"] is None:
        add_reference_readings(window.rows, state["reference"])
        state["reference_windows"] += 1

        sizes = " ".join(
            f"{code}={len(patients)}"
            for code, patients in state["reference"].items()
        )

        if reference_is_ready(state):
            state["frozen"] = {
                code: patient_medians(patients)
                for code, patients in state["reference"].items()
            }
            print(f"{label} REFERENCE READY | patients {sizes}")
        else:
            print(
                f"{label} REFERENCE "
                f"{state['reference_windows']}/{NUMERIC_REFERENCE_MAX_WINDOWS} "
                f"| patients {sizes} (target {NUMERIC_REFERENCE_PATIENTS})"
            )
        return

    # --------------------------------------------------------
    # 2. Compare the latest patients with the reference
    # --------------------------------------------------------

    add_current_readings(window.rows, state["current"])

    rows_for_check = [
        {"code": code, NUMERIC_FIELD: value}
        for code, patients in state["current"].items()
        for value in patient_medians(patients)
    ]

    window_meta = {
        "resource_type": RESOURCE_TYPE,
        "window_start": window.window_start,
        "window_end": window.window_end,
    }

    results = check_numeric(
        rows_for_check,
        window_meta,
        state["frozen"],
    )

    parts = []

    for result in results:

        evidence = result["evidence"]
        code = evidence["code"]
        name = evidence.get("name") or code
        field = numeric_field(code)

        if result["incident_type"] in NUMERIC_SKIP_TYPES:
            parts.append(
                f"{name}: SKIP (patients={evidence['current_n']}"
                f"/{NUMERIC_MIN_PATIENTS})"
            )
            continue

        current_median = float(result["current_value"])
        reference_median = float(result["baseline_value"])

        metric_id = upsert_quality_metric(
            resource_type=RESOURCE_TYPE,
            window_start=window.window_start,
            window_end=window.window_end,
            metric_name=NUMERIC_METRIC,
            field_name=field,
            metric_value=current_median,
        )

        open_id = get_open_incident_id(
            resource_type=RESOURCE_TYPE,
            incident_type=NUMERIC_INCIDENT_TYPE,
            field_name=field,
        )

        if result["is_anomaly"]:
            status = f"DRIFT {result['severity'].upper()}"

            if open_id is None:
                incident_id = insert_incident(
                    resource_type=RESOURCE_TYPE,
                    detected_at=window.window_end,
                    # Detector says "distribution_drift";
                    # the schema stores it as numeric_drift.
                    incident_type=NUMERIC_INCIDENT_TYPE,
                    severity=result["severity"],
                    metric_name=NUMERIC_METRIC,
                    field_name=field,
                    observed_value=current_median,
                    baseline_value=reference_median,
                    message=build_numeric_message(result),
                    status="open",
                    quality_metric_id=metric_id,
                )
                print(f"  NUMERIC INCIDENT OPENED: {incident_id} ({name})")
            else:
                print(f"  Numeric incident already open: {open_id} ({name})")

        else:
            status = "OK"

            if open_id is not None:
                resolve_incident(open_id)
                print(f"  NUMERIC INCIDENT RESOLVED: {open_id} ({name})")

        parts.append(
            f"{name}: {status} "
            f"D={evidence['ks_statistic']:.3f} "
            f"median {reference_median:.1f}→{current_median:.1f} "
            f"(patients={evidence['current_n']})"
        )

    print(f"{label} " + " | ".join(parts))


def numeric_checked_windows(
    windows,
    reference: dict[str, list[float]] | None = None,
):
    """
    Run the numeric drift check, then pass the SAME window on.

    reference: {code: patient medians} from Silver.
    When given, it is frozen from the start and comparison begins
    with the first window. When None, the reference is learned
    from the first patients of the stream.
    """

    frozen = None

    if reference:
        frozen = {
            code: list(values)
            for code, values in reference.items()
            if code in MONITORED_CODES and values
        }

    state = {
        "reference": {code: {} for code in MONITORED_CODES},
        "reference_windows": 0,
        "frozen": frozen,
        "current": {code: OrderedDict() for code in MONITORED_CODES},
    }

    for window in windows:
        persist_numeric_window(window, state)
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

    numeric_codes = load_numeric_codes()

    encounter_config = load_encounter_config()

    # --------------------------------------------------------
    # Silver baseline (config/baselines.json)
    # --------------------------------------------------------
    # Built by: PYTHONPATH=src python -m sentinel.baseline.builder
    # Without the file, numeric drift and missingness fall back
    # to learning their baseline from the first live windows.

    baselines = load_baselines()

    numeric_reference = None
    missingness_baseline = None

    if baselines:
        numeric_reference = {
            code: item["patient_medians"]
            for code, item in baselines["numeric"].items()
        }
        missingness_baseline = baselines["missingness"]["null_rates"]

    encounter_settings = encounter_class_settings(
        encounter_config,
        baselines,
    )

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

    print(
        "Patient contract: enabled "
        "(patient_id, gender, birth_date, marital_status_code)"
    )

    if baselines:
        print(
            f"Baseline:        Silver "
            f"({baselines['source']}, built {baselines['built_at']})"
        )
    else:
        print(
            f"Baseline:        live warm-up "
            f"({BASELINES_PATH.name} not found)"
        )

    print(
        f"Missingness:     enabled "
        f"({MISSINGNESS_FIELD} on "
        f"{len(numeric_codes)} numeric codes, "
        + (
            f"{len(missingness_baseline)} Silver windows)"
            if missingness_baseline
            else f"warm-up {MISSINGNESS_WARMUP} windows)"
        )
    )

    print(
        "Encounter contract: enabled "
        "(required fields, status, class, start/end time, unique id)"
    )

    if encounter_settings:
        print(
            f"Encounter class: enabled "
            f"(JSD on {encounter_settings['field_name']}, "
            f"last {encounter_settings['min_samples']} encounters, "
            f"threshold {encounter_settings['threshold']}, "
            f"Silver baseline)"
        )
    else:
        print(
            "Encounter class: off "
            "(no encounter_class_drift in monitoring.yaml "
            "or no encounter_class in baselines.json)"
        )

    print(
        "Volume:          enabled "
        "(drops open incidents, warm-up "
        f"{VOLUME_WARMUP} windows)"
    )

    if numeric_reference:
        sizes = ", ".join(
            f"{code}={len(values)}"
            for code, values in numeric_reference.items()
        )
        reference_text = f"Silver reference patients {sizes}"
    else:
        reference_text = (
            f"reference {NUMERIC_REFERENCE_PATIENTS} live patients"
        )

    print(
        f"Numeric drift:   enabled "
        f"(KS on {len(MONITORED_CODES)} codes, one value per patient, "
        f"{reference_text}, "
        f"latest {NUMERIC_CURRENT_PATIENTS} patients compared)"
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

    # Encounter class drift on Encounter rows, then the
    # Encounter rows are removed from the window.
    windows = encounter_checked_windows(
        windows,
        encounter_settings,
    )

    # Patient contract on Patient rows, then only
    # Observation rows continue to the detectors below.
    windows = patient_checked_windows(
        windows
    )

    # Observation contract validation happens next.
    # The exact same Window is then yielded to
    # the next detectors.
    windows = contract_checked_windows(
        windows
    )

    # Null spike on numeric_value, numeric rows only.
    windows = missingness_checked_windows(
        windows,
        numeric_codes,
        missingness_baseline,
    )

    # Record count per window.
    windows = volume_checked_windows(
        windows
    )

    # KS test per numeric measurement, one value per patient.
    windows = numeric_checked_windows(
        windows,
        numeric_reference,
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