"""
The four Sentinel pages: Overview, Data Quality, Schema & Contracts, Incidents.

Each page receives a ``ViewData`` built from one PostgreSQL snapshot plus
monitoring.yaml, and arranges components and charts. No SQL here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from sentinel.dashboard import charts
from sentinel.dashboard import components1 as ui
from sentinel.dashboard.model1 import (
    CONTRACT_INCIDENT_TYPES,
    OVERVIEW_RESOURCES,
    SEVERITY_ORDER,
    STATUS_ORDER,
    THRESHOLD_STATE_TONE,
    DetectorStatus,
    HealthState,
    assess_health,
    category_display,
    category_short_label,
    detector_statuses,
    format_timestamp,
    format_value,
    humanize,
    incident_context,
    monitored_resources,
    recover_detected_distribution,
    relative_time,
    resource_state,
    sentence_case,
    severity_tone,
    threshold_state,
    to_display_tz,
)
from sentinel.dashboard.theme import PLOTLY_CONFIG
from sentinel.dashboard.theme import COLORS

@dataclass
class ViewData:
    snapshot: dict[str, Any]
    settings: dict[str, Any] | None  # categorical-drift settings from monitoring.yaml
    statuses: list[DetectorStatus]
    coverage: dict[str, list[str]]
    health: HealthState
    open_by_resource: dict[str, dict[str, int]]
    open_count: int
    counts_by_type: dict[str, int]
    counts_by_status: dict[str, int]
    counts_by_severity: dict[str, int]

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
        statuses=statuses,
        coverage=monitored_resources(statuses),
        health=assess_health(open_by_severity),
        open_by_resource=open_by_resource,
        open_count=sum(open_by_severity.values()),
        counts_by_type=counts_by_type,
        counts_by_status={r["status"]: int(r["incident_count"]) for r in snapshot["counts_by_status"]},
        counts_by_severity={r["severity"]: int(r["incident_count"]) for r in snapshot["counts_by_severity"]},
    )


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
            detail = f"{name} monitoring not implemented yet"
        rows.append({"name": name, "detail": detail, "label": label, "tone": tone, "active": active})
    rows.sort(key=lambda r: not r["active"])
    return rows


def render_overview(data: ViewData) -> None:
    ui.render_hero()

    latest_open = data.snapshot["latest_open_incident"]
    incident = latest_open or data.snapshot["latest_incident"]
    context = incident_context(incident, data.settings) if incident else None
    resources = _resource_rows(data)

    left, center, right = st.columns([1, 1.08, 1.22], gap="medium")
    with left:
        ui.overall_health_card(
            data.health,
            data.open_count,
            monitored=sum(r["active"] for r in resources),
            total_resources=len(resources),
            last_detection=(data.snapshot["latest_incident"] or {}).get("detected_at"),
        )
    with center:
        ui.resources_card(resources)
    with right:
        ui.active_incident_card(incident, context, is_open=latest_open is not None)

    ui.pipeline_strip(
        data.open_count,
        data.health.tone,
        active_detectors=sum(s.configured for s in data.statuses),
    )


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------


def _incident_label(incident: dict) -> str:
    return (
        f"#{incident['id']} · {format_timestamp(incident['detected_at'], with_seconds=False)}"
        f" · JSD {format_value(incident.get('observed_value'))}"
    )


def _jsd_chart(data: ViewData, history: list[dict]) -> None:
    settings = data.settings
    threshold = settings["threshold"]
    windows = data.snapshot["categorical_window_series"]

    if windows:
        ui.section_title("JSD per processing window", "Persisted window metrics, with detected incidents ringed.")
        _plot(
            charts.metric_vs_threshold(
                [w["window_end"] for w in windows],
                [w["metric_value"] for w in windows],
                threshold,
                hover=[
                    f"Window ending {format_timestamp(w['window_end'])}<br>JSD {w['metric_value']:.4f}"
                    for w in windows
                ],
                connect=True,
                metric_label="JSD",
                incident_times=[i["detected_at"] for i in history],
                incident_values=[i["observed_value"] for i in history],
            )
        )
        return

    ui.section_title("Detected JSD values", "One point per categorical-drift incident written to PostgreSQL.")
    points = [i for i in history if i.get("observed_value") is not None]
    if not points:
        ui.empty_state("No categorical drift detected yet", "JSD values appear here once Sentinel writes an incident.")
        return
    _plot(
        charts.metric_vs_threshold(
            [i["detected_at"] for i in points],
            [i["observed_value"] for i in points],
            threshold,
            hover=[
                f"Incident #{i['id']} · {format_timestamp(i['detected_at'])}<br>"
                f"JSD {i['observed_value']:.4f} · {i['severity']} · {i.get('status') or 'open'}"
                for i in points
            ],
            connect=False,
            metric_label="JSD",
        )
    )
    ui.note(
        "Incident-level values only. Per-window JSD for healthy windows is not persisted to "
        "quality_metrics yet, so values below the threshold do not appear on this chart."
    )


def _distribution_panel(data: ViewData, history: list[dict]) -> None:
    settings = data.settings
    baseline = settings["baseline"]
    codes = sorted(baseline, key=lambda code: -baseline[code])
    labels = [category_short_label(c, settings) for c in codes]
    hover_names = [f"{category_display(c, settings)} · {c}" for c in codes]

    ui.section_title(
        "Baseline vs detected distribution",
        f"{sentence_case(settings['baseline_level'])} · baseline from monitoring.yaml",
    )

    detected = None
    selected = None
    if history:
        newest_first = list(reversed(history))
        selected = st.selectbox(
            "Incident",
            newest_first,
            format_func=_incident_label,
            key="dq_incident",
        )
        result = recover_detected_distribution(selected.get("message"), selected.get("observed_value"), settings)
        if result.distribution:
            detected = result.distribution.proportions
        else:
            ui.note(
                "Detected category distribution is not yet stored in structured form. "
                + result.reason
                + " Only the configured baseline is shown.",
                tone="amber",
            )

    _plot(
        charts.distribution_comparison(
            labels,
            hover_names,
            [baseline[c] for c in codes],
            [detected[c] for c in codes] if detected else None,
        )
    )
    ui.distribution_table(
        [
            {"label": label, "code": code, "baseline": baseline[code], "detected": (detected or {}).get(code)}
            for label, code in zip(labels, codes)
        ],
        has_detected=detected is not None,
    )
    if detected is not None and selected is not None:
        st.caption(
            f"Recovered from incident #{selected['id']} context; verified by recomputing "
            f"JSD = {result.distribution.recomputed_jsd:.4f} against the stored "
            f"{result.distribution.stored_jsd:.4f}."
        )
    elif not history:
        st.caption("No categorical-drift incident yet — showing the configured baseline only.")


def _config_panel(settings: dict) -> None:
    ui.kv_panel(
        "Monitoring configuration",
        [
            ("Observation", settings["observation_display"]),
            ("FHIR code", settings["observation_code"]),
            ("Field", settings["field_name"]),
            ("Method", sentence_case(settings["method"])),
            ("Threshold", f"{settings['threshold']:.2f}"),
            ("Minimum unique patients", str(settings["min_samples"])),
            ("Baseline level", sentence_case(settings["baseline_level"])),
        ],
    )
    st.caption("Source: config/monitoring.yaml")


def _other_detector_trends(data: ViewData) -> None:
    """Generic trends for non-categorical detectors once they write incidents."""

    skip = set(CONTRACT_INCIDENT_TYPES) | {data.settings["incident_type"] if data.settings else ""}
    for incident_type in sorted(t for t in data.counts_by_type if t not in skip):
        rows = [
            i for i in reversed(data.incidents)
            if i["incident_type"] == incident_type and i.get("observed_value") is not None
        ]
        if not rows:
            continue
        metric = humanize(rows[-1].get("metric_name"))
        with st.container(key=f"panel-trend-{incident_type}"):
            ui.section_title(f"{humanize(incident_type)} · {metric}", "Observed value at each detected incident.")
            _plot(
                charts.metric_vs_threshold(
                    [i["detected_at"] for i in rows],
                    [i["observed_value"] for i in rows],
                    None,
                    hover=[
                        f"#{i['id']} · {i.get('field_name') or '—'}<br>{metric} {i['observed_value']:.4f}"
                        for i in rows
                    ],
                    connect=False,
                    metric_label=metric,
                    height=260,
                )
            )


def render_data_quality(data: ViewData) -> None:
    settings = data.settings
    if settings is None:
        ui.render_page_title("Data Quality", "Statistical detectors over processing windows.")
        ui.empty_state(
            "Categorical drift is not configured",
            "Add a categorical_drift section to config/monitoring.yaml to enable this view.",
        )
    else:
        ui.render_page_title(
            "Categorical Distribution Drift",
            f"{settings['observation_display']} · FHIR Observation {settings['observation_code']} · "
            f"field {settings['field_name']}",
        )
        history = data.snapshot["categorical_history"]
        latest = history[-1] if history else None
        latest_value = latest.get("observed_value") if latest else None
        state = threshold_state(latest_value, settings["threshold"])
        open_count = sum(1 for i in history if (i.get("status") or "open") == "open")

        ui.kpi_tiles(
            [
                (
                    "Latest detected JSD",
                    format_value(latest_value),
                    f"Incident #{latest['id']}" if latest else "No detection yet",
                    THRESHOLD_STATE_TONE[state] if latest else "text",
                ),
                ("Threshold", f"{settings['threshold']:.4f}", "monitoring.yaml", "amber"),
                ("Detections", str(len(history)), f"{open_count} open", "text"),
                (
                    "Latest detection",
                    relative_time(latest["detected_at"]) if latest else "—",
                    format_timestamp(latest["detected_at"]) if latest else "No detection yet",
                    "text",
                ),
            ]
        )
        st.write("")

        chart_col, gauge_col = st.columns([1.7, 1], gap="medium")
        with chart_col, st.container(key="panel-jsd"):
            _jsd_chart(data, history)
        with gauge_col, st.container(key="panel-gauge"):
            ui.section_title("Observed vs threshold", "Latest detected Jensen–Shannon distance.")
            if latest is None:
                ui.empty_state("No data-health incidents detected", "Nothing has crossed the threshold.")
            else:
                ui.threshold_gauge(latest_value, settings["threshold"], "Observed JSD")
                st.caption(
                    "JSD compares the window's category proportions with the healthy baseline: "
                    "0 = identical, 1 = completely different."
                )

        st.write("")
        dist_col, config_col = st.columns([1.7, 1], gap="medium")
        with dist_col, st.container(key="panel-dist"):
            _distribution_panel(data, history)
        with config_col, st.container(key="panel-config"):
            _config_panel(settings)

    st.write("")
    ui.section_title("Detector coverage", "Detectors appear as active once configured or writing incidents.")
    ui.detector_coverage(data.statuses)
    st.write("")
    _other_detector_trends(data)


# ---------------------------------------------------------------------------
# Schema & Contracts
# ---------------------------------------------------------------------------


def render_schema(data: ViewData) -> None:
    ui.render_page_title(
        "Schema & Contracts",
        (
            "Structural checks on incoming FHIR records: "
            "required fields, allowed values, value types and schema changes."
        ),
    )

    # ---------------------------------------------------------
    # Data
    # ---------------------------------------------------------

    events = data.snapshot["schema_history"]

    contract_incidents = [
        incident
        for incident in data.incidents
        if incident["incident_type"] in CONTRACT_INCIDENT_TYPES
    ]

    open_contract = sum(
        1
        for incident in contract_incidents
        if (incident.get("status") or "open") == "open"
    )

    contract_series = data.snapshot[
        "contract_violation_series"
    ]

    contract_rows_series = data.snapshot[
        "contract_rows_checked_series"
    ]

    # ---------------------------------------------------------
    # Latest contract window
    # ---------------------------------------------------------

    latest_contract = (
        contract_series[-1]
        if contract_series
        else None
    )

    latest_rows = (
        contract_rows_series[-1]
        if contract_rows_series
        else None
    )

    latest_violation_count = (
        int(latest_contract["metric_value"])
        if latest_contract
        else None
    )

    latest_rows_checked = (
        int(latest_rows["metric_value"])
        if latest_rows
        else None
    )

    # ---------------------------------------------------------
    # Contract state
    # ---------------------------------------------------------

    if latest_violation_count is None:
        contract_label = "NOT RUN"
        contract_tone = "muted"

    elif latest_violation_count == 0:
        contract_label = "PASS"
        contract_tone = "green"

    else:
        contract_label = "FAIL"
        contract_tone = "rose"

    # ---------------------------------------------------------
    # KPIs
    # ---------------------------------------------------------

    ui.kpi_tiles(
        [
            (
                "Contract status",
                contract_label,
                "Latest completed processing window",
                contract_tone,
            ),
            (
                "Rows checked",
                (
                    f"{latest_rows_checked:,}"
                    if latest_rows_checked is not None
                    else "—"
                ),
                "Latest window",
                "text",
            ),
            (
                "Violations",
                (
                    str(latest_violation_count)
                    if latest_violation_count is not None
                    else "—"
                ),
                (
                    f"{open_contract} open incident"
                    if open_contract == 1
                    else f"{open_contract} open incidents"
                ),
                (
                    "rose"
                    if latest_violation_count
                    else "text"
                ),
            ),
            (
                "Schema events",
                str(len(events)),
                "schema_history",
                "text",
            ),
        ]
    )

    st.write("")

    # ---------------------------------------------------------
    # No contract execution yet
    # ---------------------------------------------------------

    if (
        latest_violation_count is None
        and not events
        and not contract_incidents
    ):
        ui.empty_state(
            "No schema or contract monitoring results yet.",
            (
                "Sentinel has not persisted a completed contract-validation "
                "window or schema event yet."
            ),
        )
        return

    # ---------------------------------------------------------
    # Schema history
    # ---------------------------------------------------------

    if events:
        with st.container(
            key="panel-schema-timeline"
        ):
            ui.section_title(
                "Schema timeline",
                (
                    "Field additions, removals "
                    "and type changes."
                ),
            )

            _plot(
                charts.schema_timeline(events)
            )

        st.write("")

        with st.container(
            key="panel-schema-table"
        ):
            ui.section_title(
                "Latest schema events"
            )

            frame = pd.DataFrame(
                {
                    "Observed At": [
                        to_display_tz(
                            event["observed_at"]
                        ).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        for event in events
                    ],
                    "Resource": [
                        event["resource_type"]
                        for event in events
                    ],
                    "Field": [
                        event["field_name"]
                        for event in events
                    ],
                    "Change": [
                        humanize(
                            event["change_type"]
                        )
                        for event in events
                    ],
                    "Previous Type": [
                        event.get(
                            "previous_type"
                        )
                        or "—"
                        for event in events
                    ],
                    "Observed Type": [
                        event.get(
                            "observed_type"
                        )
                        or "—"
                        for event in events
                    ],
                }
            )

            styled_frame = (
                frame.style
                .set_properties(
                    **{
                        "background-color": COLORS["card"],
                        "color": COLORS["text"],
                        "border-color": COLORS["secondary"],
                    }
                )
                .set_table_styles(
                    [
                        {
                            "selector": "th",
                            "props": [
                                (
                                    "background-color",
                                    COLORS["card"],
                                ),
                                (
                                    "color",
                                    COLORS["muted"],
                                ),
                                (
                                    "border-color",
                                    COLORS["secondary"],
                                ),
                                (
                                    "font-weight",
                                    "600",
                                ),
                            ],
                        },
                    ]
                )
            )

            st.dataframe(
                styled_frame,
                hide_index=True,
                width="stretch",
                height=min(
                    420,
                    40 + 35 * len(frame),
                ),
            )

    else:
        ui.empty_state(
            "No schema changes recorded",
            "No schema changes have been detected.",
        )

    # ---------------------------------------------------------
    # Contract incidents
    # ---------------------------------------------------------

    st.write("")

    with st.container(
        key="panel-contract-incidents"
    ):
        ui.section_title(
            "Contract incidents",
            (
                "Missing required fields, invalid values "
                "and value/type mismatches."
            ),
        )

        if contract_incidents:
            ui.incident_table(
                contract_incidents,
                key="contract_table",
                height=min(
                    380,
                    40 + 35 * len(contract_incidents),
                ),
            )

        else:
            ui.empty_state(
                "No contract violations detected",
                (
                    "The latest monitored windows satisfy "
                    "the Observation data contract."
                    if latest_violation_count == 0
                    else
                    "No contract incident has been written yet."
                ),
            )
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
                "Acknowledged",
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
    if settings and incident["incident_type"] == settings["incident_type"]:
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
                "Acknowledged",
                str(data.counts_by_status.get("acknowledged", 0)),
                "under investigation",
                "blue",
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
    # Severity + activity
    # ---------------------------------------------------------

    sev_col, chart_col = st.columns(
        [1, 1.9],
        gap="medium",
    )

    with sev_col, st.container(
        key="panel-severity",
    ):
        ui.section_title(
            "Severity breakdown",
            "All incidents, all-time.",
        )

        ui.severity_breakdown(
            data.counts_by_severity
        )

        st.write("")

        ui.section_title(
            "Status breakdown"
        )

        status_rows = [
            (
                status.title(),
                str(
                    data.counts_by_status.get(
                        status,
                        0,
                    )
                ),
            )
            for status in STATUS_ORDER
        ]

        ui.kv_panel(
            "",
            status_rows,
            mono_values=True,
        )

    with chart_col, st.container(
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
            filtered
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
        incident_context(
            incident,
            data.settings,
        ),
        _detail_extra_rows(
            incident,
            data.settings,
        ),
    )