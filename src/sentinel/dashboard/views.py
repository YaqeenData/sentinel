"""
The three Sentinel pages: Overview, Data Quality, Incidents.

Contract checks live in Data Quality, per FHIR resource, next to the other
detectors of that resource (Patient only has a contract; Observation has
contract, missingness, volume, numeric and categorical drift).

Each page receives a ``ViewData`` built from one PostgreSQL snapshot plus
monitoring.yaml, and arranges components and charts. No SQL here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st

from sentinel.dashboard import charts
from sentinel.dashboard import components as ui
from sentinel.dashboard.model import (
    CONTRACT_INCIDENT_TYPES,
    DETECTORS,
    OVERVIEW_RESOURCES,
    SEVERITY_ORDER,
    STATUS_ORDER,
    THRESHOLD_STATE_TONE,
    Detector,
    DetectorStatus,
    HealthState,
    assess_health,
    category_display,
    category_short_label,
    detector_statuses,
    encounter_class_label,
    encounter_class_settings,
    format_timestamp,
    format_value,
    humanize,
    incident_context,
    load_silver_baselines,
    monitored_resources,
    numeric_settings,
    recover_detected_distribution,
    recover_encounter_distribution,
    relative_time,
    resource_state,
    sentence_case,
    severity_tone,
    threshold_state,
    to_display_tz,
)
from sentinel.dashboard.theme import PLOTLY_CONFIG
from sentinel.dashboard.theme import COLORS, rgba

@dataclass
class ViewData:
    snapshot: dict[str, Any]
    settings: dict[str, Any] | None  # categorical-drift settings from monitoring.yaml
    numeric: dict[str, Any] | None  # numeric-drift settings from monitoring.yaml
    statuses: list[DetectorStatus]
    coverage: dict[str, list[str]]
    health: HealthState
    open_by_resource: dict[str, dict[str, int]]
    open_count: int
    counts_by_type: dict[str, int]
    counts_by_status: dict[str, int]
    counts_by_severity: dict[str, int]
    # Encounter class drift settings (monitoring.yaml + Silver baselines.json)
    encounter: dict[str, Any] | None = None

    @property
    def incidents(self) -> list[dict]:
        return self.snapshot["incidents"]

    @property
    def data_as_of(self) -> datetime | None:
        return self.snapshot["data_as_of"]


def build_view_data(snapshot: dict[str, Any], config: dict, settings: dict | None) -> ViewData:
    open_by_resource: dict[str, dict[str, int]] = {}
    open_by_severity: dict[str, int] = {}
    for row in snapshot["open_counts"]:
        count = int(row["incident_count"])
        open_by_resource.setdefault(row["resource_type"], {})[row["severity"]] = count
        open_by_severity[row["severity"]] = open_by_severity.get(row["severity"], 0) + count

    counts_by_type = {r["incident_type"]: int(r["incident_count"]) for r in snapshot["counts_by_type"]}
    statuses = detector_statuses(config, counts_by_type)
    return ViewData(
        snapshot=snapshot,
        settings=settings,
        numeric=numeric_settings(config),
        statuses=statuses,
        coverage=monitored_resources(statuses),
        health=assess_health(open_by_severity),
        open_by_resource=open_by_resource,
        open_count=sum(open_by_severity.values()),
        counts_by_type=counts_by_type,
        counts_by_status={r["status"]: int(r["incident_count"]) for r in snapshot["counts_by_status"]},
        counts_by_severity={r["severity"]: int(r["incident_count"]) for r in snapshot["counts_by_severity"]},
        encounter=_encounter_settings_or_none(config),
    )


def _encounter_settings_or_none(config: dict) -> dict[str, Any] | None:
    """Encounter class settings, or None if monitoring.yaml/baselines.json lack them."""

    try:
        return encounter_class_settings(config, load_silver_baselines())
    except (ValueError, FileNotFoundError):
        return None


def _plot(figure) -> None:
    st.plotly_chart(
        figure,
        width="stretch",
        config=PLOTLY_CONFIG,
        theme=None,
    )


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

# Session-state key holding the FHIR resource the Overview is scoped to.
# None means "all resources".
RESOURCE_KEY = "selected_resource"


_CONTRACT_ROWS_PATTERN = re.compile(r"(\d+) rule failures in (\d+) rows")

# Encounter class drift writes e.g.
# "... exceeded threshold 0.20 on the last 1000 encounters.
#  Observed: AMB 69.1%, EMER 30.3%, ... Silver baseline: AMB 92.7%, EMER 4.4%, ..."
_THRESHOLD_PATTERN = re.compile(r"threshold\s+([0-9]*\.?[0-9]+)")
_CLASS_SHARES_PATTERN = re.compile(r"Observed:\s*(.*?)\.\s*Silver baseline:\s*(.*?)\.?\s*$")
_CLASS_SHARE_PATTERN = re.compile(r"([A-Z]+)\s+([0-9]*\.?[0-9]+)%")


def _class_shares(text: str) -> dict[str, float]:
    """'AMB 69.1%, EMER 30.3%' -> {'AMB': 69.1, 'EMER': 30.3}."""

    return {code: float(value) for code, value in _CLASS_SHARE_PATTERN.findall(text)}


def _encounter_class_context(context, incident: dict):
    """
    Encounter class drift: compare the JSD with the threshold written in the
    message, and say which classes moved the most against the Silver baseline.
    """

    message = incident.get("message") or ""
    observed = incident.get("observed_value")

    threshold_match = _THRESHOLD_PATTERN.search(message)
    threshold = float(threshold_match.group(1)) if threshold_match else None

    comparator = ""
    if observed is not None and threshold is not None:
        comparator = ">" if observed > threshold else "<" if observed < threshold else "="

    note = None
    shares_match = _CLASS_SHARES_PATTERN.search(message)
    if shares_match:
        now = _class_shares(shares_match.group(1))
        silver = _class_shares(shares_match.group(2))
        moved = sorted(
            set(now) | set(silver),
            key=lambda code: abs(now.get(code, 0.0) - silver.get(code, 0.0)),
            reverse=True,
        )[:2]
        if moved:
            note = " · ".join(
                f"{code} {now.get(code, 0.0):.1f}% (Silver {silver.get(code, 0.0):.1f}%)"
                for code in moved
            )

    return context._replace(
        title="Encounter class",
        subtitle="FHIR Encounter · class_code",
        reference=threshold,
        reference_label="threshold",
        comparator=comparator,
        note=note,
    )


def _incident_context(incident: dict, settings: dict | None, numeric: dict | None = None):
    """
    incident_context, with readable names for:
      - numeric measurements: Heart rate (8867-4)
      - contract violations: "Patient · Birth date", shown as a count of
        bad rows against zero expected, not as decimals.
    """

    context = incident_context(incident, settings)
    field = incident.get("field_name") or ""

    if field.startswith("numeric_value:"):
        return context._replace(title=_measurement_label(field, numeric))

    if (
        incident.get("resource_type") == "Encounter"
        and incident.get("incident_type") == "categorical_drift"
    ):
        return _encounter_class_context(context, incident)

    if (
        incident.get("incident_type") in CONTRACT_INCIDENT_TYPES
        and incident.get("metric_name") == "contract_violation_count"
    ):
        resource = incident.get("resource_type") or "Record"
        bad_rows = int(incident.get("observed_value") or 0)

        note = None
        match = _CONTRACT_ROWS_PATTERN.search(incident.get("message") or "")
        if match:
            failed, total = int(match.group(1)), int(match.group(2))
            note = f"{failed} of {total} {resource} rows in the window broke this rule"

        return context._replace(
            title=f"{resource} · {sentence_case(field)}",
            observed_label="bad rows",
            observed_text=f"{bad_rows:,}",
            reference_label="expected",
            reference_text="0",
            note=note,
        )

    return context


def _with_same_window_note(context, incident: dict, incidents: list[dict]):
    """
    The card shows one incident, but one window can open several
    (one per field and problem). Add a line saying how many others
    were detected for the same resource at the same time.
    """

    same_window = [
        other
        for other in incidents
        if other["id"] != incident["id"]
        and other.get("detected_at") == incident.get("detected_at")
        and other.get("resource_type") == incident.get("resource_type")
    ]
    if not same_window:
        return context

    count = len(same_window)
    line = f"+{count} more incident{'s' if count != 1 else ''} in the same window"

    if incident.get("metric_name") == "contract_violation_count":
        contract_rows = [incident] + [
            other for other in same_window
            if other.get("metric_name") == "contract_violation_count"
        ]
        total = sum(int(other.get("observed_value") or 0) for other in contract_rows)
        line += f" · {total} bad rows in total"

    note = f"{context.note}\n{line}" if context.note else line
    return context._replace(note=note)


def _field_label(field_name: str | None) -> str:
    """Readable field for incident tables: Heart rate (8867-4), Birth date, ..."""

    if not field_name:
        return "—"
    if field_name.startswith("numeric_value:"):
        return _measurement_label(field_name)
    return sentence_case(field_name)


def _select_resource(name: str) -> None:
    """Card click: select a resource, or clear it when clicked again."""

    current = st.session_state.get(RESOURCE_KEY)
    st.session_state[RESOURCE_KEY] = None if current == name else name


def _resource_rows(data: ViewData) -> list[dict]:
    names = list(OVERVIEW_RESOURCES)
    for extra in list(data.snapshot["resource_types"]) + list(data.coverage):
        if extra not in names:
            names.append(extra)

    rows = []
    for name in names:
        label, tone = resource_state(name, data.coverage, data.open_by_resource)
        active = tone != "muted"
        if name in data.coverage:
            detail = " · ".join(data.coverage[name])
        elif active:
            detail = "Incidents reported"
        else:
            detail = "No detector configured"
        rows.append({"name": name, "detail": detail, "label": label, "tone": tone, "active": active})
    # Fixed order from OVERVIEW_RESOURCES (Patient, Observation, Encounter).
    return rows


def render_overview(data: ViewData) -> None:
    ui.render_hero()

    resources = _resource_rows(data)
    by_name = {row["name"]: row for row in resources}

    selected = st.session_state.get(RESOURCE_KEY)
    if selected not in by_name:
        selected = None

    if selected is None:
        health = data.health
        open_count = data.open_count
        latest_open = data.snapshot["latest_open_incident"]
        latest_any = data.snapshot["latest_incident"]
        health_title = "Overall Data Health"
        empty_detail = "Sentinel has not written any incident to PostgreSQL yet."
    else:
        # Incidents are ordered newest first by queries.get_recent_incidents.
        scoped = [i for i in data.incidents if i.get("resource_type") == selected]
        open_scoped = [i for i in scoped if (i.get("status") or "open") == "open"]
        latest_open = open_scoped[0] if open_scoped else None
        latest_any = scoped[0] if scoped else None
        open_count = sum(data.open_by_resource.get(selected, {}).values())
        health_title = f"{selected} Data Health"
        empty_detail = f"No incident has been recorded for {selected} yet."

        if by_name[selected]["active"]:
            health = assess_health(data.open_by_resource.get(selected, {}))
        else:
            # No detector covers this resource: "no incidents" does not mean healthy.
            health = HealthState(
                "Not monitored",
                "muted",
                f"{selected} monitoring not implemented yet",
            )

    incident = latest_open or latest_any
    context = _incident_context(incident, data.settings, data.numeric) if incident else None
    if incident is not None and context is not None:
        context = _with_same_window_note(context, incident, data.incidents)

    left, center, right = st.columns([1, 1.08, 1.22], gap="medium")
    with left:
        ui.overall_health_card(
            health,
            open_count,
            last_detection=(latest_any or {}).get("detected_at"),
            title=health_title,
        )
    with center:
        ui.resources_card(resources, selected=selected, on_select=_select_resource)
    with right:
        ui.active_incident_card(
            incident,
            context,
            is_open=latest_open is not None,
            empty_detail=empty_detail,
        )


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------


def _incident_label(incident: dict) -> str:
    return (
        f"#{incident['id']} · {format_timestamp(incident['detected_at'], with_seconds=False)}"
        f" · JSD {_jsd_text(incident.get('observed_value'))}"
    )


# ---------------------------------------------------------------------------
# Categorical drift pages (Observation smoking + Encounter class)
#
# Both pages share one layout:
#   current JSD + latest incident · JSD per window (time range) ·
#   baseline vs the distribution at one incident · settings · incidents.
# ---------------------------------------------------------------------------

# Time ranges for the JSD chart, measured back from the latest window.
_JSD_RANGES = {"1h": timedelta(hours=1), "6h": timedelta(hours=6), "24h": timedelta(hours=24), "All": None}
_JSD_DEFAULT_RANGE = "1h"

# Two windows further apart than this are not joined on the chart.
_JSD_GAP = timedelta(minutes=3)


def _jsd_text(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _duration_text(delta: timedelta) -> str:
    minutes = max(1, int(round(delta.total_seconds() / 60)))
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    if hours < 48:
        return f"{hours} h {rest} min" if rest else f"{hours} h"
    return f"{hours // 24} d {hours % 24} h"


def _incident_duration(incident: dict, windows: list[dict], threshold: float) -> str:
    """
    How long an incident lasted. The incidents table keeps no resolve time,
    so a resolved incident ends at the first later window back under the
    threshold, which is the window that resolved it.
    """

    start = incident["detected_at"]
    if (incident.get("status") or "open") == "open":
        return f"Open for {_duration_text(datetime.now(timezone.utc) - start)}"
    ends = [
        w["window_end"]
        for w in windows
        if w["window_end"] > start and w["metric_value"] is not None and w["metric_value"] < threshold
    ]
    return f"Resolved after {_duration_text(min(ends) - start)}" if ends else "Resolved"


def _jsd_range_windows(windows: list[dict], key: str) -> list[dict]:
    """Time-range buttons over the JSD chart; returns the windows inside the range."""

    state_key = f"jsd_range_{key}"
    if st.session_state.get(state_key) not in _JSD_RANGES:
        st.session_state[state_key] = _JSD_DEFAULT_RANGE
    _remember(state_key)
    choice = (
        st.segmented_control(
            "Time range",
            list(_JSD_RANGES),
            key=state_key,
            on_change=_keep_selection,
            args=(state_key,),
            label_visibility="collapsed",
        )
        or _JSD_DEFAULT_RANGE
    )
    span = _JSD_RANGES[choice]
    if span is None or not windows:
        return windows
    newest = max(w["window_end"] for w in windows)
    return [w for w in windows if w["window_end"] >= newest - span]


def _categorical_tiles(spec: dict) -> None:
    windows, history, threshold = spec["windows"], spec["history"], spec["threshold"]

    current = windows[-1] if windows else None
    current_value = current["metric_value"] if current else None
    current_state = threshold_state(current_value, threshold)
    if current is None:
        current_detail = "No window judged yet"
    else:
        verdict = {"exceeded": "Above threshold", "near": "Close to threshold"}.get(current_state, "Healthy")
        current_detail = (
            f"{verdict} · threshold {threshold:.2f} · window ending "
            f"{format_timestamp(current['window_end'], with_seconds=False)}"
        )

    latest = history[-1] if history else None
    if latest is None:
        incident_value, incident_detail, incident_tone = "None", "Nothing has crossed the threshold", "text"
    else:
        is_open = (latest.get("status") or "open") == "open"
        incident_value = f"#{latest['id']} · {_jsd_text(latest.get('observed_value'))}"
        incident_detail = (
            f"{_incident_duration(latest, spec['all_windows'], threshold)} · "
            f"{len(history)} incident{'s' if len(history) != 1 else ''} recorded"
        )
        incident_tone = severity_tone(latest.get("severity")) if is_open else "muted"

    ui.kpi_tiles(
        [
            (
                "Current JSD",
                _jsd_text(current_value),
                current_detail,
                THRESHOLD_STATE_TONE[current_state] if current else "text",
            ),
            ("Latest incident", incident_value, incident_detail, incident_tone),
        ]
    )


def _categorical_jsd_chart(spec: dict) -> None:
    threshold, history = spec["threshold"], spec["history"]

    ui.section_title("JSD per processing window", spec["chart_subtitle"])
    windows = _jsd_range_windows(spec["all_windows"], spec["key"])

    if not windows:
        points = [i for i in history if i.get("observed_value") is not None]
        if not points:
            ui.empty_state(
                "No JSD written yet",
                "The monitor writes one value per window once it has enough data.",
            )
            return
        _plot(
            charts.metric_vs_threshold(
                [i["detected_at"] for i in points],
                [i["observed_value"] for i in points],
                threshold,
                hover=[f"Incident #{i['id']}<br>JSD {i['observed_value']:.3f}" for i in points],
                connect=False,
                metric_label="JSD",
            )
        )
        return

    first = windows[0]["window_end"]
    shown = [i for i in history if i["detected_at"] >= first and i.get("observed_value") is not None]
    _plot(
        charts.metric_vs_threshold(
            [w["window_end"] for w in windows],
            [w["metric_value"] for w in windows],
            threshold,
            hover=[
                f"{format_timestamp(w['window_end'], with_seconds=False)}<br>JSD {w['metric_value']:.3f}"
                for w in windows
            ],
            connect=True,
            metric_label="JSD",
            incident_times=[i["detected_at"] for i in shown],
            incident_values=[i["observed_value"] for i in shown],
            gap=_JSD_GAP,
        )
    )


def _categorical_distribution(spec: dict) -> None:
    history, baseline, codes = spec["history"], spec["baseline"], spec["codes"]

    detected = None
    selected = None
    if history:
        newest_first = list(reversed(history))
        selected = st.selectbox(
            "Incident",
            newest_first,
            format_func=_incident_label,
            key=f"dist_incident_{spec['key']}",
            label_visibility="collapsed",
        )
        result = spec["recover"](selected)
        if result.distribution:
            detected = result.distribution.proportions

    if selected is not None and detected is not None:
        subtitle = (
            f"{spec['baseline_name']} vs the mix when #{selected['id']} was detected "
            f"({format_timestamp(selected['detected_at'], with_seconds=False)})"
        )
    elif selected is not None:
        subtitle = f"The mix at #{selected['id']} is not available · {spec['baseline_name']} only"
    else:
        subtitle = f"{spec['baseline_name']} · no incident yet"
    ui.section_title(spec["distribution_title"], subtitle)

    _plot(
        charts.distribution_comparison(
            [spec["label"](c) for c in codes],
            [spec["hover_name"](c) for c in codes],
            [baseline[c] for c in codes],
            [detected.get(c, 0.0) for c in codes] if detected else None,
        )
    )


def _render_categorical_page(spec: dict) -> None:
    """One layout for every categorical-drift detector (see the comment above)."""

    _categorical_tiles(spec)
    st.write("")
    with st.container(key=f"panel-{spec['key']}-jsd"):
        _categorical_jsd_chart(spec)

    st.write("")
    dist_col, config_col = st.columns([1.7, 1], gap="medium")
    with dist_col, st.container(key=f"panel-{spec['key']}-dist"):
        _categorical_distribution(spec)
    with config_col, st.container(key=f"panel-{spec['key']}-config"):
        ui.kv_panel("Settings", spec["config_rows"])


# Data Quality is navigated in two levels: FHIR resource, then one of its
# detectors. The resource choice is shared with the Overview (RESOURCE_KEY);
# the widget itself keeps its own key so Streamlit never drops the shared
# value when the Data Quality page is not on screen.
DQ_RESOURCE_KEY = "dq_resource"

# Detectors shown with the contract view (status, rows checked, violations
# per window). Each one checks the contract of its own resource.
CONTRACT_DETECTOR_KEYS = ("contract", "patient_contract", "encounter_contract")

# Some detectors share incident types (the two contracts, the two categorical
# drifts), so the resource decides which one an incident belongs to
# (see _detector_for).
_RESOURCE_SPECIFIC_DETECTORS = {
    # (shared detector key, resource) -> detector key used for that resource
    ("contract", "Patient"): "patient_contract",
    ("contract", "Encounter"): "encounter_contract",
    ("categorical_drift", "Encounter"): "encounter_class_drift",
}
_RESOURCE_SPECIFIC_KEYS = set(_RESOURCE_SPECIFIC_DETECTORS.values())
_DETECTOR_BY_KEY = {d.key: d for d in DETECTORS}
_DETECTOR_BY_INCIDENT_TYPE = {
    t: d for d in DETECTORS if d.key not in _RESOURCE_SPECIFIC_KEYS for t in d.incident_types
}


def _detector_for(incident: dict) -> Detector | None:
    """The detector that wrote an incident, using its resource for shared types."""

    detector = _DETECTOR_BY_INCIDENT_TYPE.get(incident.get("incident_type"))
    if detector is None:
        return None
    specific = _RESOURCE_SPECIFIC_DETECTORS.get((detector.key, incident.get("resource_type")))
    return _DETECTOR_BY_KEY.get(specific, detector) if specific else detector

# Fallback display names for numeric fields stored as "numeric_value:<LOINC code>".
# monitoring.yaml (numeric_drift.observations) is checked first.
_MEASUREMENT_LABELS = {
    "8867-4": "Heart rate",
    "8480-6": "Systolic blood pressure",
    "2339-0": "Glucose",
    "2345-7": "Glucose",
}

# The numeric-drift detector writes e.g. "Heart rate: KS D=0.353 (p=1.3e-14), ..."
_KS_PATTERN = re.compile(r"KS\s*D\s*=\s*([0-9]*\.?[0-9]+)")


def _resource_detectors(data: ViewData) -> dict[str, list[Detector]]:
    """
    resource_type -> detectors that cover it, in registry order.

    A detector covers a resource when monitoring.yaml configures it for that
    resource, or when it has already written incidents for that resource.
    """

    keys: dict[str, set[str]] = {}
    for status in data.statuses:
        if status.configured and status.resource_type:
            keys.setdefault(status.resource_type, set()).add(status.detector.key)
    for incident in data.incidents:
        detector = _detector_for(incident)
        resource = incident.get("resource_type")
        if detector and resource:
            keys.setdefault(resource, set()).add(detector.key)
    return {
        resource: [d for d in DETECTORS if d.key in found]
        for resource, found in keys.items()
    }


def _measurement_label(field_name: str | None, numeric: dict | None = None) -> str:
    """
    numeric_value:8867-4 -> Heart rate (8867-4).

    Names come from monitoring.yaml first, then the fallback table.
    """

    if not field_name:
        return "—"
    code = field_name.split(":", 1)[1] if ":" in field_name else field_name
    configured = (numeric or {}).get("observations", {}).get(code, {})
    name = configured.get("display") or _MEASUREMENT_LABELS.get(code)
    return f"{name} ({code})" if name else field_name


def _ks_statistic(message: str | None) -> float | None:
    match = _KS_PATTERN.search(message or "")
    return float(match.group(1)) if match else None


def _open_count(rows: list[dict]) -> int:
    return sum(1 for i in rows if (i.get("status") or "open") == "open")


def _resource_incidents(data: ViewData, resource: str, detector: Detector) -> list[dict]:
    """Incidents of one detector on one resource, oldest first."""

    return [
        i
        for i in reversed(data.incidents)
        if i.get("resource_type") == resource and i["incident_type"] in detector.incident_types
    ]


def _default_detector(data: ViewData, resource: str, detectors: list[Detector]) -> Detector:
    """The detector that reported most recently on this resource, else the first."""

    for incident in data.incidents:  # newest first
        if incident.get("resource_type") != resource:
            continue
        detector = _detector_for(incident)
        if detector in detectors:
            return detector
    return detectors[0]


def _dq_nav_style() -> None:
    """Soft cyan for the selected resource / detector / measurement buttons."""

    c = COLORS
    ui.html(
        f"""
        <div class="sn-css-holder"></div>
        <style>
        [data-testid="stElementContainer"]:has(.sn-css-holder) {{ display:none !important; }}
        div[class*="st-key-dq_"] [data-testid="stButtonGroup"] button {{
            background:transparent !important;
            border-color:{c['secondary']} !important;
            color:{c['muted']} !important;
            box-shadow:none !important;
        }}
        div[class*="st-key-dq_"] [data-testid="stButtonGroup"] button p {{
            color:inherit !important;
        }}
        div[class*="st-key-dq_"] [data-testid="stButtonGroup"] button:hover {{
            border-color:{c['cyan']} !important;
            color:{c['text']} !important;
        }}
        div[class*="st-key-dq_"] [data-testid="stButtonGroup"] button[kind$="Active"],
        div[class*="st-key-dq_"] [data-testid="stButtonGroup"] button[data-testid$="Active"],
        div[class*="st-key-dq_"] [data-testid="stButtonGroup"] button[aria-checked="true"],
        div[class*="st-key-dq_"] [data-testid="stButtonGroup"] button[aria-pressed="true"] {{
            background:{rgba(c['cyan'], 0.18)} !important;
            border-color:{c['cyan']} !important;
            box-shadow:inset 0 0 0 1px {c['cyan']} !important;
            color:{c['cyan']} !important;
            font-weight:600 !important;
            position:relative;
            z-index:1;
        }}
        </style>
        """
    )


def _remember(key: str) -> None:
    """Store a segmented control's current value as its last valid choice."""

    st.session_state[f"_{key}_last"] = st.session_state.get(key)


def _keep_selection(key: str) -> None:
    """
    on_change for segmented controls: clicking the selected button again
    would clear it, so restore the previous choice instead.
    """

    if st.session_state.get(key) is None:
        st.session_state[key] = st.session_state.get(f"_{key}_last")
    else:
        _remember(key)


def _dq_resource_changed() -> None:
    _keep_selection(DQ_RESOURCE_KEY)
    st.session_state[RESOURCE_KEY] = st.session_state.get(DQ_RESOURCE_KEY)


# --- one view per detector --------------------------------------------------


def _contract_windows(data: ViewData, resource: str) -> tuple[list[dict], int | None, int | None]:
    """(violation series, latest violations, latest rows checked) for one resource."""

    def mine(series: list[dict]) -> list[dict]:
        return [row for row in series if row.get("resource_type") == resource]

    violations = mine(data.snapshot["contract_violation_series"])
    checked = mine(data.snapshot["contract_rows_checked_series"])
    latest_violations = int(violations[-1]["metric_value"]) if violations else None
    latest_checked = int(checked[-1]["metric_value"]) if checked else None
    return violations, latest_violations, latest_checked


def _contract_state(latest_violations: int | None) -> tuple[str, str]:
    if latest_violations is None:
        return "NOT RUN", "muted"
    if latest_violations == 0:
        return "PASS", "green"
    return "FAIL", "rose"


_SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITY_ORDER)}

# Dot shown on a measurement button, keyed by _open_rank (low=1 … critical=4).
_SEVERITY_DOT = {1: "🔵", 2: "🟠", 3: "🔴", 4: "🔴"}


def _open_rank(rows: list[dict]) -> int:
    """0 when nothing is open, else 1 + rank of the worst open severity."""

    ranks = [
        _SEVERITY_RANK.get((i.get("severity") or "").lower(), 0) + 1
        for i in rows
        if (i.get("status") or "open") == "open"
    ]
    return max(ranks, default=0)


def _detector_card(data: ViewData, resource: str, detector: Detector) -> dict:
    """Status card for one detector on one resource. ``rank`` > 0 means open incidents."""

    rows = _resource_incidents(data, resource, detector)
    open_rows = [i for i in rows if (i.get("status") or "open") == "open"]
    open_severities = [(i.get("severity") or "").lower() for i in open_rows]
    worst = max(open_severities, key=lambda s: _SEVERITY_RANK.get(s, -1)) if open_rows else None
    rank = _SEVERITY_RANK.get(worst, 0) + 1 if open_rows else 0

    if detector.key in CONTRACT_DETECTOR_KEYS:
        _, latest_violations, latest_checked = _contract_windows(data, resource)
        if open_rows:
            label, tone = f"{worst.upper()} · {len(open_rows)} open", severity_tone(worst)
        else:
            label, tone = _contract_state(latest_violations)
        detail = (
            f"{latest_checked:,} rows checked in the latest window"
            if latest_checked is not None
            else "No window checked yet"
        )
    else:
        if open_rows:
            label, tone = f"{worst.upper()} · {len(open_rows)} open", severity_tone(worst)
        elif rows:
            label, tone = "All resolved", "green"
        else:
            label, tone = "No detections", "green"

        if rows:
            detail = f"{len(rows)} incident{'s' if len(rows) != 1 else ''} recorded"
        elif detector.key == "categorical_drift" and data.settings and resource == "Observation":
            detail = f"JSD threshold {data.settings['threshold']:.2f}"
        elif detector.key == "encounter_class_drift" and data.encounter:
            detail = f"JSD threshold {data.encounter['threshold']:.2f}"
        else:
            detail = "Nothing has crossed its threshold"

    return {
        "key": detector.key,
        "name": detector.name,
        "label": label,
        "tone": tone,
        "detail": detail,
        "rank": rank,
    }


def _select_detector(state_key: str, detector_key: str) -> None:
    st.session_state[state_key] = detector_key


def _dq_contract(data: ViewData, resource: str, detector: Detector) -> None:
    violations, latest_violations, latest_checked = _contract_windows(data, resource)
    incidents = _resource_incidents(data, resource, detector)
    label, tone = _contract_state(latest_violations)
    open_count = _open_count(incidents)

    ui.kpi_tiles(
        [
            ("Contract status", label, "Latest processing window", tone),
            (
                "Rows checked",
                f"{latest_checked:,}" if latest_checked is not None else "—",
                "Latest window",
                "text",
            ),
            (
                "Violations",
                str(latest_violations) if latest_violations is not None else "—",
                "Latest window",
                "rose" if latest_violations else "text",
            ),
            ("Open incidents", str(open_count), f"{len(incidents)} recorded", "amber" if open_count else "text"),
        ]
    )
    st.write("")

    with st.container(key="panel-dq-contract"):
        if violations and any(row["metric_value"] for row in violations):
            ui.section_title("Violations per processing window")
            _plot(
                charts.metric_vs_threshold(
                    [row["window_end"] for row in violations],
                    [row["metric_value"] for row in violations],
                    None,
                    hover=[
                        f"Window ending {format_timestamp(row['window_end'])}<br>"
                        f"{int(row['metric_value'])} violations"
                        for row in violations
                    ],
                    connect=True,
                    metric_label="Violations",
                    height=260,
                )
            )
        elif violations:
            ui.section_title("Violations per processing window")
            ui.note(f"All {len(violations)} recorded windows passed the contract.", tone="green")


def _dq_numeric(data: ViewData, resource: str, detector: Detector) -> None:
    rows = _resource_incidents(data, resource, detector)
    if not rows:
        ui.empty_state("No numeric drift detected yet", "Values appear here once the detector writes an incident.")
        return

    def field_of(incident: dict) -> str:
        return incident.get("field_name") or "—"

    fields = list(dict.fromkeys(field_of(i) for i in rows))
    by_field = {f: [i for i in rows if field_of(i) == f] for f in fields}
    ranks = {f: _open_rank(by_field[f]) for f in fields}

    def button_label(f: str) -> str:
        dot = _SEVERITY_DOT.get(ranks[f])
        label = _measurement_label(f, data.numeric)
        return f"{dot} {label}" if dot else label

    # Open on the measurement with the worst open incident; if none is open,
    # on the measurement that reported most recently.
    default_field = max(fields, key=lambda f: (ranks[f], by_field[f][-1]["detected_at"]))

    field = default_field
    if len(fields) > 1:
        measure_key = f"dq_measure_{resource}"
        if st.session_state.get(measure_key) not in fields:
            st.session_state[measure_key] = default_field
        _remember(measure_key)
        chosen = st.segmented_control(
            "Measurement",
            fields,
            format_func=button_label,
            key=measure_key,
            on_change=_keep_selection,
            args=(measure_key,),
        )
        field = chosen or default_field

    field_label = _measurement_label(field, data.numeric)
    series = by_field[field]
    # Draw the most severe points last so they are never hidden under milder ones.
    chart_points = sorted(series, key=lambda i: _SEVERITY_RANK.get((i.get("severity") or "").lower(), -1))
    latest = series[-1]
    baseline = latest.get("baseline_value")
    ks = _ks_statistic(latest.get("message"))
    open_count = _open_count(series)

    ui.kpi_tiles(
        [
            (
                "Latest median",
                format_value(latest.get("observed_value"), 2),
                f"Incident #{latest['id']}",
                severity_tone(latest.get("severity")),
            ),
            ("Baseline median", format_value(baseline, 2), "Healthy reference", "text"),
            ("Latest KS D", f"{ks:.3f}" if ks is not None else "—", "0 = same shape, 1 = no overlap", "text"),
            ("Detections", str(len(series)), f"{open_count} open", "amber" if open_count else "text"),
        ]
    )
    st.write("")

    with st.container(key="panel-dq-numeric"):
        ui.section_title(
            f"{field_label} · median at detection",
            "One point per numeric-drift incident, colored by severity. Dashed line = baseline.",
        )
        _plot(
            charts.numeric_vs_baseline(
                [i["detected_at"] for i in chart_points],
                [i.get("observed_value") for i in chart_points],
                baseline,
                hover=[
                    f"#{i['id']} · {format_timestamp(i['detected_at'])}<br>"
                    f"Median {format_value(i.get('observed_value'), 2)} · "
                    f"{(i.get('severity') or '—').upper()} · {(i.get('status') or 'open').title()}"
                    for i in chart_points
                ],
                tones=[severity_tone(i.get("severity")) for i in chart_points],
                metric_label="Median",
            )
        )
        ui.note(
            "Incident-level values only. Medians of healthy windows are not persisted to "
            "quality_metrics yet, so the normal values before a shift do not appear here."
        )


def _dq_categorical_configured(data: ViewData) -> None:
    """Observation smoking status: JSD against the baseline in monitoring.yaml."""

    settings = data.settings
    baseline = settings["baseline"]
    windows = [
        w for w in data.snapshot["categorical_window_series"]
        if w.get("resource_type", "Observation") == "Observation"
    ]
    _render_categorical_page(
        {
            "key": "smoking",
            "threshold": settings["threshold"],
            "windows": windows,
            "all_windows": windows,
            "history": data.snapshot["categorical_history"],
            "chart_subtitle": (
                f"Latest status of each patient vs the baseline · {settings['min_samples']} patients minimum"
            ),
            "distribution_title": "Baseline vs detected distribution",
            "baseline_name": "Baseline",
            "baseline": baseline,
            "codes": sorted(baseline, key=lambda code: -baseline[code]),
            "label": lambda code: category_short_label(code, settings),
            "hover_name": lambda code: f"{category_display(code, settings)} · {code}",
            "recover": lambda incident: recover_detected_distribution(
                incident.get("message"), incident.get("observed_value"), settings
            ),
            "config_rows": [
                ("Observation", f"{settings['observation_display']} ({settings['observation_code']})"),
                ("Field", settings["field_name"]),
                ("Threshold", f"JSD {settings['threshold']:.2f}"),
                ("Minimum patients", str(settings["min_samples"])),
                ("Baseline", sentence_case(settings["baseline_level"])),
            ],
        }
    )


def _dq_encounter_class(data: ViewData) -> None:
    """Encounter class: JSD of the last N encounters against Silver."""

    settings = data.encounter
    baseline = settings["baseline"]
    windows = data.snapshot.get("encounter_window_series") or []
    encounters = settings.get("baseline_encounters")
    built_at = settings.get("baseline_built_at")
    _render_categorical_page(
        {
            "key": "encounter",
            "threshold": settings["threshold"],
            "windows": windows,
            "all_windows": windows,
            "history": data.snapshot.get("encounter_history") or [],
            "chart_subtitle": (
                f"Class mix of the last {settings['min_samples']:,} encounters vs Silver · "
                "detected incidents ringed"
            ),
            "distribution_title": "Silver vs detected class mix",
            "baseline_name": "Silver",
            "baseline": baseline,
            "codes": sorted(baseline, key=lambda code: -baseline[code]),
            "label": encounter_class_label,
            "hover_name": lambda code: f"{encounter_class_label(code)} · {code}",
            "recover": lambda incident: recover_encounter_distribution(
                incident.get("message"), incident.get("observed_value"), baseline
            ),
            "config_rows": [
                ("Field", settings["field_name"]),
                ("Threshold", f"JSD {settings['threshold']:.2f}"),
                ("Sample", f"Last {settings['min_samples']:,} encounters"),
                (
                    "Baseline",
                    "Silver"
                    + (f", {int(encounters):,} encounters" if encounters else "")
                    + (f" · {str(built_at)[:10]}" if built_at else ""),
                ),
            ],
        }
    )


def _dq_generic(data: ViewData, resource: str, detector: Detector) -> None:
    """Any detector without a dedicated view: its incidents over time."""

    rows = _resource_incidents(data, resource, detector)
    latest = rows[-1] if rows else None
    open_count = _open_count(rows)
    metric = humanize(latest.get("metric_name")) if latest else "Value"

    ui.kpi_tiles(
        [
            (
                f"Latest {metric}",
                format_value(latest.get("observed_value")) if latest else "—",
                f"Incident #{latest['id']}" if latest else "No detection yet",
                severity_tone(latest.get("severity")) if latest else "text",
            ),
            ("Detections", str(len(rows)), f"{open_count} open", "amber" if open_count else "text"),
            (
                "Latest detection",
                relative_time(latest["detected_at"]) if latest else "—",
                format_timestamp(latest["detected_at"]) if latest else "No detection yet",
                "text",
            ),
        ]
    )
    st.write("")

    valued = [i for i in rows if i.get("observed_value") is not None]
    with st.container(key=f"panel-dq-{detector.key}"):
        if valued:
            ui.section_title(f"{metric} at detection", "One point per incident written to PostgreSQL.")
            _plot(
                charts.metric_vs_threshold(
                    [i["detected_at"] for i in valued],
                    [i["observed_value"] for i in valued],
                    None,
                    hover=[
                        f"#{i['id']} · {format_timestamp(i['detected_at'])}<br>{metric} {i['observed_value']:.4f}"
                        for i in valued
                    ],
                    connect=False,
                    metric_label=metric,
                    height=260,
                )
            )


def render_data_quality(data: ViewData) -> None:
    ui.render_page_title("Data Quality", "Choose a FHIR resource, then one of its detectors.")
    _dq_nav_style()

    names = [row["name"] for row in _resource_rows(data)]
    by_resource = _resource_detectors(data)
    default_resource = next((name for name in names if by_resource.get(name)), names[0])

    # Follow the resource picked on the Overview; otherwise keep this page's
    # own choice, or open on the first monitored resource.
    shared = st.session_state.get(RESOURCE_KEY)
    if shared in names:
        st.session_state[DQ_RESOURCE_KEY] = shared
    elif st.session_state.get(DQ_RESOURCE_KEY) not in names:
        st.session_state[DQ_RESOURCE_KEY] = default_resource
    _remember(DQ_RESOURCE_KEY)

    resource = (
        st.segmented_control(
            "FHIR resource",
            names,
            key=DQ_RESOURCE_KEY,
            on_change=_dq_resource_changed,
        )
        or default_resource
    )

    detectors = by_resource.get(resource, [])
    if not detectors:
        st.write("")
        ui.empty_state(
            f"No detector configured for {resource} yet",
            "Once a detector is configured in monitoring.yaml or writes an incident for "
            f"{resource}, it appears here automatically.",
        )
        return

    cards = [_detector_card(data, resource, d) for d in detectors]
    state_key = f"dq_detector_{resource}"
    keys = [card["key"] for card in cards]
    if st.session_state.get(state_key) not in keys:
        # Open on the worst detector; if nothing is open, on the latest one to report.
        worst = max(cards, key=lambda card: card["rank"])
        st.session_state[state_key] = (
            worst["key"] if worst["rank"] > 0 else _default_detector(data, resource, detectors).key
        )
    selected_key = st.session_state[state_key]

    st.write("")
    ui.detector_cards(
        cards,
        selected=selected_key,
        on_select=partial(_select_detector, state_key),
        key_prefix=resource,
    )
    detector = next(d for d in detectors if d.key == selected_key)

    st.write("")
    ui.section_title(f"{resource} · {detector.name}", f"{detector.signal} · {detector.method}")

    if detector.key in CONTRACT_DETECTOR_KEYS:
        _dq_contract(data, resource, detector)
    elif detector.key == "numeric_drift":
        _dq_numeric(data, resource, detector)
    elif detector.key == "categorical_drift" and data.settings is not None and resource == "Observation":
        _dq_categorical_configured(data)
    elif detector.key == "encounter_class_drift" and data.encounter is not None:
        _dq_encounter_class(data)
    else:
        _dq_generic(data, resource, detector)



# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


def _adaptive_incident_chart(data: ViewData) -> None:
    types = data.counts_by_type
    if not types:
        ui.section_title("Incident activity")
        ui.empty_state("No data-health incidents detected.")
        return

    if len(types) > 1:
        ui.section_title("Incidents by type", "All-time counts.")
        ordered = sorted(types.items(), key=lambda item: -item[1])
        tones = []
        for incident_type, _ in ordered:
            severities = {i["severity"] for i in data.incidents if i["incident_type"] == incident_type}
            worst = max(severities, key=SEVERITY_ORDER.index) if severities else "low"
            tones.append(severity_tone(worst))
        _plot(charts.counts_by_category([humanize(t) for t, _ in ordered], [n for _, n in ordered], tones))
        return

    incident_type = next(iter(types))
    rows = [i for i in reversed(data.incidents) if i["incident_type"] == incident_type]
    valued = [i for i in rows if i.get("observed_value") is not None]
    if valued:
        metric = humanize(valued[-1].get("metric_name"))
        settings = data.settings
        threshold = (
            settings["threshold"]
            if settings and incident_type == settings["incident_type"]
            and valued[-1].get("metric_name") == settings["metric_name"]
            else None
        )
        ui.section_title(f"{metric} by incident time", f"{humanize(incident_type)} · observed value at detection.")
        _plot(
            charts.metric_vs_threshold(
                [i["detected_at"] for i in valued],
                [i["observed_value"] for i in valued],
                threshold,
                hover=[
                    f"#{i['id']} · {format_timestamp(i['detected_at'])}<br>{metric} {i['observed_value']:.4f}"
                    for i in valued
                ],
                connect=False,
                metric_label=metric,
                height=280,
            )
        )
    else:
        ui.section_title("Incident events over time", humanize(incident_type))
        _plot(
            charts.events_over_time(
                [i["detected_at"] for i in rows],
                [severity_tone(i["severity"]) for i in rows],
                [f"#{i['id']} · {format_timestamp(i['detected_at'])}" for i in rows],
            )
        )


def _filter_incidents(
    incidents: list[dict],
) -> list[dict]:

    incident_types = sorted(
        {
            humanize(
                incident["incident_type"]
            )
            for incident in incidents
        }
    )

    resources = sorted(
        {
            incident.get("resource_type")
            or "Unknown"
            for incident in incidents
        }
    )

    type_col, severity_col, status_col, resource_col = st.columns(
        4,
        gap="medium",
    )

    with type_col:
        selected_type = st.selectbox(
            "Incident Type",
            options=[
                "All types",
                *incident_types,
            ],
            key="incident_type_filter",
        )

    with severity_col:
        selected_severity = st.selectbox(
            "Severity",
            options=[
                "All severities",
                "Low",
                "Medium",
                "High",
                "Critical",
            ],
            key="incident_severity_filter",
        )

    with status_col:
        selected_status = st.selectbox(
            "Status",
            options=[
                "All statuses",
                "Open",
                "Resolved",
            ],
            key="incident_status_filter",
        )

    with resource_col:
        selected_resource = st.selectbox(
            "FHIR Resource",
            options=[
                "All resources",
                *resources,
            ],
            key="incident_resource_filter",
        )

    filtered = incidents

    if selected_type != "All types":
        filtered = [
            incident
            for incident in filtered
            if humanize(
                incident["incident_type"]
            )
            == selected_type
        ]

    if (
        selected_severity
        != "All severities"
    ):
        filtered = [
            incident
            for incident in filtered
            if (
                incident.get("severity")
                or ""
            ).lower()
            == selected_severity.lower()
        ]

    if selected_status != "All statuses":
        filtered = [
            incident
            for incident in filtered
            if (
                incident.get("status")
                or "open"
            ).lower()
            == selected_status.lower()
        ]

    if selected_resource != "All resources":
        filtered = [
            incident
            for incident in filtered
            if (
                incident.get(
                    "resource_type"
                )
                or "Unknown"
            )
            == selected_resource
        ]

    return filtered

def _detail_extra_rows(incident: dict, settings: dict | None) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if incident.get("window_start") and incident.get("window_end"):
        rows.append(
            (
                "Processing window",
                f"{to_display_tz(incident['window_start']).strftime('%H:%M:%S')} – "
                f"{to_display_tz(incident['window_end']).strftime('%H:%M:%S')}",
            )
        )
    if (
        settings
        and incident["incident_type"] == settings["incident_type"]
        # The smoking settings belong to Observation; Encounter class drift
        # shares the incident type but not the categories.
        and (incident.get("resource_type") or "Observation") == "Observation"
    ):
        rows.append(("FHIR code", settings["observation_code"]))
        result = recover_detected_distribution(incident.get("message"), incident.get("observed_value"), settings)
        if result.distribution:
            proportions = result.distribution.proportions
            rows.append(
                (
                    "Detected distribution",
                    " · ".join(
                        f"{category_short_label(c, settings)} {proportions[c]:.1%}"
                        for c in sorted(proportions, key=lambda c: -settings["baseline"][c])
                    ),
                )
            )
    return rows


def render_incidents(data: ViewData) -> None:
    ui.render_page_title(
        "Incidents",
        "Every data-health incident Sentinel has written to PostgreSQL.",
    )

    total = sum(data.counts_by_type.values())
    opened = data.counts_by_status.get("open", 0)

    ui.kpi_tiles(
        [
            (
                "Open",
                str(opened),
                "need attention" if opened else "nothing open",
                "amber" if opened else "green",
            ),
            (
                "Resolved",
                str(data.counts_by_status.get("resolved", 0)),
                "closed",
                "green",
            ),
            (
                "Total",
                str(total),
                f"{len(data.counts_by_type)} incident type(s)",
                "text",
            ),
        ]
    )

    st.write("")

    if not data.incidents:
        ui.empty_state(
            "No data-health incidents detected.",
            "Incidents appear here as soon as a detector writes one.",
        )
        return

    # ---------------------------------------------------------
    # Activity
    # ---------------------------------------------------------

    with st.container(
        key="panel-activity",
    ):
        _adaptive_incident_chart(
            data
        )

    st.write("")

    # ---------------------------------------------------------
    # Incident history
    # ---------------------------------------------------------

    with st.container(
        key="panel-incident-table",
    ):
        ui.section_title(
            "Recent incidents",
            "Filter incidents and choose one to inspect.",
        )

        filtered = _filter_incidents(
            data.incidents
        )

        if not filtered:
            ui.empty_state(
                "No incidents match these filters."
            )
            return

        incident_ids = [
            incident["id"]
            for incident in filtered
        ]

        def incident_option_label(
            incident_id: int,
        ) -> str:
            incident = next(
                item
                for item in filtered
                if item["id"] == incident_id
            )

            detected = to_display_tz(
                incident["detected_at"]
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            return (
                f"#{incident_id} · "
                f"{humanize(incident['incident_type'])} · "
                f"{detected}"
            )

        selected_id = st.selectbox(
            "Inspect incident",
            options=incident_ids,
            index=0,
            format_func=incident_option_label,
            key="incident_inspector",
        )

        ui.incident_static_table(
            filtered,
            field_label=_field_label,
        )

        if len(data.incidents) >= 500:
            st.caption(
                "Showing the 500 most recent incidents."
            )

    # ---------------------------------------------------------
    # Selected incident details
    # ---------------------------------------------------------

    st.write("")

    incident = next(
        incident
        for incident in filtered
        if incident["id"] == selected_id
    )

    ui.incident_detail(
        incident,
        _incident_context(
            incident,
            data.settings,
            data.numeric,
        ),
        _detail_extra_rows(
            incident,
            data.settings,
        ),
    )