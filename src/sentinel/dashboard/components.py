"""
Reusable Sentinel UI components.

HTML is only ever emitted through ``html()``, which escapes nothing itself
but collapses markup onto one line so Markdown can never render it as
literal text or a code block. Every dynamic value is escaped with ``esc()``.
"""

from __future__ import annotations

import html as _html
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from sentinel.dashboard.model import (
    SEVERITY_ORDER,
    DetectorStatus,
    HealthState,
    IncidentContext,
    format_timestamp,
    format_value,
    humanize,
    relative_time,
    severity_tone,
    status_tone,
    threshold_state,
    THRESHOLD_STATE_TONE,
    to_display_tz,
    tz_label,
)
from sentinel.dashboard.theme import COLORS, logo_data_uri, tone_color


# ---------------------------------------------------------------------------
# HTML primitives
# ---------------------------------------------------------------------------


def esc(value: Any) -> str:
    return _html.escape("" if value is None else str(value))


def html(markup: str) -> None:
    """Render trusted markup built in this module, safely as one line."""

    compact = " ".join(line.strip() for line in markup.splitlines() if line.strip())
    st.markdown(compact, unsafe_allow_html=True)


def chip(label: str, tone: str, dot: bool = False) -> str:
    dot_html = f'<span class="sn-dot sn-dot-{tone}"></span>' if dot else ""
    return f'<span class="sn-chip sn-{tone}">{dot_html}{esc(label)}</span>'


def severity_chip(severity: str | None) -> str:
    return chip((severity or "—").upper(), severity_tone(severity))


def status_chip(status: str | None) -> str:
    return chip((status or "open").upper(), status_tone(status), dot=True)


def empty_state(title: str, detail: str = "") -> None:
    detail_html = f"<div>{esc(detail)}</div>" if detail else ""
    html(f'<div class="sn-empty"><div class="sn-big">{esc(title)}</div>{detail_html}</div>')


def note(text: str, tone: str = "muted") -> None:
    html(f'<div class="sn-note" style="border-left-color:{tone_color(tone)}">{esc(text)}</div>')


def section_title(title: str, subtitle: str = "") -> None:
    sub = f'<div class="sn-section-sub">{esc(subtitle)}</div>' if subtitle else ""
    html(f'<div class="sn-section-title">{esc(title)}</div>{sub}')


# ---------------------------------------------------------------------------
# Top bar, hero and footer
# ---------------------------------------------------------------------------


def render_top_bar(
    pages: list[str],
    nav_key: str,
    theme_key: str,
    fetched_at: datetime | None,
    data_as_of: datetime | None,
) -> bool:
    """
    Brand, navigation and refresh status. The navigation widget writes the
    selected page to ``st.session_state[nav_key]``. Returns True when the
    Refresh button was pressed.
    """

    brand, nav, theme, status, button = st.columns(
        [2.3, 4.7, 1.5, 2.1, 0.9],
        vertical_alignment="center",
    )
    with brand:
        logo = logo_data_uri()
        mark = (
            f'<img class="sn-logo" src="{logo}" alt="Sentinel logo">'
            if logo
            else '<div class="sn-mark"><span></span></div>'
        )
        html(
            f"""
            <div class="sn-brand">
              {mark}
              <div>
                <div class="sn-wordmark">SENTINEL</div>
                <div class="sn-brand-sub">Real-Time Healthcare Data Reliability</div>
              </div>
            </div>
            """
        )
    with nav:
        st.segmented_control(
            "Navigation",
            options=pages,
            key=nav_key,
            label_visibility="collapsed",
        )
    with theme:
        current_theme = st.session_state.get(
            theme_key,
            "dark",
        )

        next_theme = (
            "light"
            if current_theme == "dark"
            else "dark"
        )

        icon = (
            "☀️"
            if current_theme == "dark"
            else "🌙"
        )

        if st.button(
            icon,
            key="theme_toggle",
            help=f"Switch to {next_theme} mode",
            width="stretch",
        ):
            st.session_state[theme_key] = next_theme
            st.rerun()
    with status:
        refreshed = (
            to_display_tz(fetched_at).strftime("%H:%M:%S") + " " + tz_label(to_display_tz(fetched_at))
            if fetched_at
            else "—"
        )
        as_of = relative_time(data_as_of) if data_as_of else "no data yet"
        html(
            f"""
            <div class="sn-refresh">
              Refreshed <b>{esc(refreshed)}</b><br>
              Latest data <b>{esc(as_of)}</b>
            </div>
            """
        )
    with button:
        pressed = st.button("↻ Refresh", key="refresh", width="stretch")
    html('<div class="sn-topbar-rule"></div>')
    return pressed


def render_hero() -> None:
    html(
        """
        <div class="sn-hero">
          <div class="sn-hero-q">The pipeline is green — <em>but is the data healthy?</em></div>
          <div class="sn-hero-sub">Live data-reliability monitoring for FHIR resources streamed through Kafka.</div>
        </div>
        """
    )


def render_page_title(title: str, subtitle: str) -> None:
    html(f'<div class="sn-page-title">{esc(title)}</div><div class="sn-page-sub">{esc(subtitle)}</div>')


def render_footer(data_as_of: datetime | None) -> None:
    html(
        f"""
        <div class="sn-footer">
          <span>Sentinel monitors data reliability, not patient health.</span>
          <span>Data as of {esc(format_timestamp(data_as_of))}</span>
        </div>
        """
    )


def render_db_error(error: Exception) -> None:
    html(
        f"""
        <div class="sn-card sn-accent sn-accent-rose" style="max-width:760px">
          <div class="sn-eyebrow sn-text-rose">PostgreSQL unavailable</div>
          <div class="sn-inc-title">Sentinel could not read its incident store</div>
          <div class="sn-inc-sub">Check that the Sentinel PostgreSQL service is running and that
          POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD are set in your environment or .env.</div>
          <div class="sn-message">{esc(type(error).__name__)}: {esc(error)}</div>
        </div>
        """
    )


# ---------------------------------------------------------------------------
# Overview cards
# ---------------------------------------------------------------------------


def overall_health_card(
    health: HealthState,
    open_count: int,
    monitored: int,
    total_resources: int,
    last_detection: datetime | None,
    score: float | None = None,
) -> None:
    """
    Overall data health. Shows a state (Healthy / Attention / Critical).
    ``score`` is reserved for a future, real scoring formula; when None no
    number is shown.
    """

    center = (
        f'<div class="sn-compare-val sn-text-{health.tone}">{score:.0f}%</div>'
        if score is not None
        else f'<div class="sn-ring-label sn-text-{health.tone}">{esc(health.label)}</div>'
    )
    html(
        f"""
        <div class="sn-card sn-card-tall">
          <div class="sn-card-head">
            <span class="sn-eyebrow">Overall Data Health</span>
            <span class="sn-tech">from open incidents</span>
          </div>
          <div class="sn-health">
            <div class="sn-ring sn-ring-{health.tone}">
              {center}
              <div class="sn-ring-sub">current state</div>
            </div>
            <div class="sn-health-detail">{esc(health.detail)}</div>
          </div>
          <div class="sn-stats">
            <div class="sn-stat"><span>Open incidents</span><b>{open_count}</b></div>
            <div class="sn-stat"><span>Resources monitored</span><b>{monitored} / {total_resources}</b></div>
            <div class="sn-stat"><span>Latest detection</span><b>{esc(relative_time(last_detection))}</b></div>
          </div>
        </div>
        """
    )


def resources_card(rows: list[dict]) -> None:
    """
    rows: name, detail, label, tone, active (bool).
    """

    items = []
    for row in rows:
        off = "" if row["active"] else " sn-off"
        items.append(
            f"""
            <div class="sn-res{off}">
              <div>
                <div class="sn-res-name">{esc(row['name'])}</div>
                <div class="sn-res-sub">{esc(row['detail'])}</div>
              </div>
              {chip(row['label'], row['tone'], dot=row['active'])}
            </div>
            """
        )
    html(
        f"""
        <div class="sn-card sn-card-tall">
          <div class="sn-card-head"><span class="sn-eyebrow">FHIR Resources</span>
          <span class="sn-tech">{sum(r['active'] for r in rows)} monitored</span></div>
          {''.join(items)}
          <div class="sn-tech" style="margin-top:auto">A resource is monitored only when a detector is configured for it.</div>
        </div>
        """
    )


def active_incident_card(
    incident: dict | None,
    context: IncidentContext | None,
    is_open: bool,
) -> None:
    if incident is None or context is None:
        html(
            f"""
            <div class="sn-card sn-card-tall">
              <div class="sn-card-head"><span class="sn-eyebrow">Active Incident</span>
              {chip('None', 'green', dot=True)}</div>
              <div class="sn-empty-ok">
                <div class="sn-big sn-text-green">No data-health incidents detected</div>
                <div>Sentinel has not written any incident to PostgreSQL yet.</div>
              </div>
            </div>
            """
        )
        return

    eyebrow = "Active Incident" if is_open else "Most Recent Incident"
    accent = context.tone if is_open else "muted"
    reference_html = ""
    if context.reference is not None:
        reference_html = f"""
          <div class="sn-compare-op">{esc(context.comparator)}</div>
          <div>
            <div class="sn-compare-val" style="color:{COLORS['muted']}">{format_value(context.reference)}</div>
            <div class="sn-compare-lab">{esc(context.reference_label)}</div>
          </div>
        """
    window = ""
    if incident.get("window_start") and incident.get("window_end"):
        start = to_display_tz(incident["window_start"]).strftime("%H:%M:%S")
        end = to_display_tz(incident["window_end"]).strftime("%H:%M:%S")
        window = f'<div class="sn-stat"><span>Processing window</span><b>{esc(start)} – {esc(end)}</b></div>'
    resolved_note = "" if is_open else '<div class="sn-tech">No open incidents — showing the latest one for context.</div>'

    html(
        f"""
        <div class="sn-card sn-card-tall sn-accent sn-accent-{accent}">
          <div class="sn-card-head"><span class="sn-eyebrow">{eyebrow}</span>
          <span class="sn-tech">#{esc(incident['id'])}</span></div>
          <div class="sn-inc-type sn-text-{context.tone}">{esc(humanize(incident['incident_type']))}</div>
          <div class="sn-inc-title">{esc(context.title)}</div>
          <div class="sn-inc-sub">{esc(context.subtitle)} · {esc(context.metric_label)}</div>
          <div class="sn-compare">
            <div>
              <div class="sn-compare-val sn-text-{context.tone}">{format_value(context.observed)}</div>
              <div class="sn-compare-lab">observed</div>
            </div>
            {reference_html}
          </div>
          {resolved_note}
          <div class="sn-stats">
            <div class="sn-stat"><span>Detected</span><b>{esc(format_timestamp(incident['detected_at']))}</b></div>
            {window}
            <div class="sn-stat" style="align-items:center"><span>Severity · Status</span>
            <span class="sn-chips">{severity_chip(incident['severity'])}{status_chip(incident['status'])}</span></div>
            <div class="sn-tech" style="margin-top:8px">{esc(incident['incident_type'])} · {esc(incident.get('metric_name') or '—')} · {esc(incident.get('field_name') or '—')}</div>
          </div>
        </div>
        """
    )


def pipeline_strip(open_count: int, health_tone: str, active_detectors: int) -> None:
    detectors = f"{active_detectors} detector{'s' if active_detectors != 1 else ''} active"
    incidents = f"{open_count} open" if open_count else "None open"
    steps = [
        ("STREAM", "Kafka", "Fresh Synthea FHIR events", "blue", "K"),
        ("OBSERVE", "Data Health", f"Windows · profiling · {detectors}", "cyan", "◎"),
        ("RESPOND", "Incidents", f"PostgreSQL · {incidents}", health_tone if open_count else "green", "!"),
    ]
    parts = []
    for index, (key, name, detail, tone, glyph) in enumerate(steps):
        color = tone_color(tone)
        if index:
            parts.append('<div class="sn-strip-arrow">→</div>')
        parts.append(
            f"""
            <div class="sn-strip-step">
              <div class="sn-strip-icon" style="border-color:{color};color:{color}">{esc(glyph)}</div>
              <div>
                <div class="sn-strip-k" style="color:{color}">{key}</div>
                <div class="sn-strip-n">{esc(name)}</div>
                <div class="sn-strip-d">{esc(detail)}</div>
              </div>
            </div>
            """
        )
    html(f'<div class="sn-strip">{"".join(parts)}</div>')


# ---------------------------------------------------------------------------
# KPI tiles, gauge, key/value panel
# ---------------------------------------------------------------------------


def kpi_tiles(tiles: list[tuple[str, str, str, str]]) -> None:
    """tiles: (label, value, detail, tone)."""

    columns = st.columns(len(tiles))
    for column, (label, value, detail, tone) in zip(columns, tiles):
        with column:
            color = tone_color(tone) if tone != "text" else COLORS["text"]
            html(
                f"""
                <div class="sn-kpi">
                  <div class="sn-eyebrow">{esc(label)}</div>
                  <div class="sn-kpi-v" style="color:{color}">{esc(value)}</div>
                  <div class="sn-kpi-d">{esc(detail)}</div>
                </div>
                """
            )


def threshold_gauge(value: float | None, threshold: float, label: str) -> None:
    """Horizontal bar: observed value against the configured threshold."""

    if value is None:
        empty_state("No observed value yet", "Sentinel has not persisted a value for this metric.")
        return

    state = threshold_state(value, threshold)
    tone = THRESHOLD_STATE_TONE[state]
    scale = max(threshold * 1.5, value * 1.15)
    scale = round(scale + 0.05 - (scale % 0.05), 2)

    def pct(x: float) -> float:
        return max(0.0, min(100.0, x / scale * 100))

    delta = value - threshold
    if state == "exceeded":
        verdict = f"Above threshold by {delta:+.4f} ({value / threshold:.0%} of threshold)."
    elif state == "near":
        verdict = f"Approaching threshold: {value / threshold:.0%} of threshold."
    else:
        verdict = f"Within threshold: {value / threshold:.0%} of threshold."

    html(
        f"""
        <div class="sn-gauge">
          <div class="sn-gauge-nums">
            <div><div class="sn-eyebrow">{esc(label)}</div>
            <div class="sn-compare-val sn-text-{tone}">{value:.4f}</div></div>
            <div style="text-align:right"><div class="sn-eyebrow">Threshold</div>
            <div class="sn-compare-val sn-text-amber" style="font-size:1.4rem">{threshold:.4f}</div></div>
          </div>
          <div class="sn-gauge-track">
            <div class="sn-gauge-fill sn-dot-{tone}" style="width:{pct(value):.1f}%"></div>
            <div class="sn-gauge-mark" style="left:{pct(threshold):.1f}%"></div>
          </div>
          <div class="sn-gauge-scale">
            <span style="left:0%;transform:none">0</span>
            <span style="left:{pct(threshold):.1f}%;color:{COLORS['amber']}">{threshold:.2f}</span>
            <span style="left:100%;transform:translateX(-100%)">{scale:.2f}</span>
          </div>
          <div class="sn-gauge-note">{esc(verdict)}</div>
        </div>
        """
    )


def kv_panel(title: str, rows: list[tuple[str, str]], mono_values: bool = False) -> None:
    value_class = "sn-kv-v sn-mono" if mono_values else "sn-kv-v"
    items = "".join(
        f'<div class="sn-kv-row"><span class="sn-kv-k">{esc(k)}</span><span class="{value_class}">{esc(v)}</span></div>'
        for k, v in rows
    )
    head = f'<div class="sn-eyebrow" style="margin-bottom:6px">{esc(title)}</div>' if title else ""
    html(f'{head}<div class="sn-kv">{items}</div>')


def distribution_table(rows: list[dict], has_detected: bool) -> None:
    """rows: label, code, baseline, detected (optional)."""

    head = "<th>Category</th><th>Code</th><th>Baseline</th>"
    if has_detected:
        head += "<th>Detected</th><th>Δ pp</th>"
    body = []
    for row in rows:
        cells = (
            f"<td>{esc(row['label'])}</td><td class='sn-muted'>{esc(row['code'])}</td>"
            f"<td>{row['baseline']:.1%}</td>"
        )
        if has_detected:
            delta = (row["detected"] - row["baseline"]) * 100
            tone = "rose" if abs(delta) >= 10 else ("amber" if abs(delta) >= 3 else "muted")
            cells += f"<td>{row['detected']:.1%}</td><td class='sn-text-{tone}'>{delta:+.1f}</td>"
        body.append(f"<tr>{cells}</tr>")
    html(f'<table class="sn-dist"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>')


# ---------------------------------------------------------------------------
# Detector coverage
# ---------------------------------------------------------------------------


def detector_coverage(statuses: list[DetectorStatus]) -> None:
    columns = st.columns(len(statuses))
    for column, status in zip(columns, statuses):
        detector = status.detector
        if status.configured:
            badge = chip("Active", "cyan", dot=True)
        elif status.incident_count:
            badge = chip("Reporting", "blue", dot=True)
        else:
            badge = chip("Not implemented yet", "muted")
        incidents = (
            f"{status.incident_count} incident{'s' if status.incident_count != 1 else ''} recorded"
            if status.active
            else "No data yet"
        )
        off = "" if status.active else " sn-off"
        with column:
            html(
                f"""
                <div class="sn-det{off}">
                  {badge}
                  <div class="sn-det-name">{esc(detector.name)}</div>
                  <div class="sn-det-line">Signal · {esc(detector.signal)}</div>
                  <div class="sn-det-line">Method · {esc(detector.method)}</div>
                  <div class="sn-det-line" style="margin-top:6px;color:{COLORS['text']}">{esc(incidents)}</div>
                </div>
                """
            )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


def severity_breakdown(counts: dict[str, int]) -> None:
    total = sum(counts.values())
    if not total:
        empty_state("No incidents recorded")
        return
    segments = "".join(
        f'<div style="width:{counts.get(s, 0) / total * 100:.2f}%;background:{tone_color(severity_tone(s))};'
        f'opacity:{1 if s in ("medium", "critical") else 0.75}"></div>'
        for s in SEVERITY_ORDER
        if counts.get(s)
    )
    legend = "".join(
        f'<span><span class="sn-dot" style="background:{tone_color(severity_tone(s))}"></span> '
        f"{s.title()}<b>{counts.get(s, 0)}</b></span>"
        for s in SEVERITY_ORDER
    )
    html(f'<div class="sn-sevbar">{segments}</div><div class="sn-legend">{legend}</div>')


def incidents_frame(incidents: list[dict]) -> pd.DataFrame:
    """Readable incident table (no internal foreign keys)."""

    if not incidents:
        return pd.DataFrame()
    tz = tz_label(to_display_tz(incidents[0]["detected_at"]))
    return pd.DataFrame(
        {
            "ID": [i["id"] for i in incidents],
            f"Detected At ({tz})": [
                to_display_tz(i["detected_at"]).strftime("%Y-%m-%d %H:%M:%S") for i in incidents
            ],
            "Incident Type": [humanize(i["incident_type"]) for i in incidents],
            "Resource": [i.get("resource_type") or "—" for i in incidents],
            "Metric": [humanize(i.get("metric_name")) for i in incidents],
            "Observed Value": [i.get("observed_value") for i in incidents],
            "Severity": [(i["severity"] or "").upper() for i in incidents],
            "Status": [(i.get("status") or "open").title() for i in incidents],
        }
    )


def _text_color(color: str) -> str:
    return f"color: {color}; font-weight: 600"


def incident_table(incidents: list[dict], key: str, height: int | str = "auto") -> list[int]:
    """
    Styled incident table with single-row selection. Returns the selected
    row positions.
    """

    frame = incidents_frame(incidents)
    if frame.empty:
        return []
    styler = (
        frame.style
        .format(
            {
                "Observed Value": "{:.4f}",
            },
            na_rep="—",
        )
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
        .map(
            lambda v: _text_color(
                tone_color(
                    severity_tone(
                        str(v).lower()
                    )
                )
            ),
            subset=["Severity"],
        )
        .map(
            lambda v: _text_color(
                tone_color(
                    status_tone(
                        str(v).lower()
                    )
                )
            ),
            subset=["Status"],
        )
    )
    event = st.dataframe(
        styler,
        hide_index=True,
        width="stretch",
        height=height,
        key=key,
        on_select="rerun",
        selection_mode="single-row",
        column_config={"ID": st.column_config.NumberColumn("ID", format="%d", width="small")},
    )
    try:
        return list(event.selection.rows)
    except AttributeError:
        return []


def incident_detail(incident: dict, context: IncidentContext, extra_rows: list[tuple[str, str]]) -> None:
    fields = [
        ("Incident ID", f"#{incident['id']}"),
        ("Incident type", humanize(incident["incident_type"])),
        ("FHIR resource", incident.get("resource_type") or "—"),
        ("Monitored", context.title),
        ("Metric", context.metric_label),
        ("Field", incident.get("field_name") or "—"),
        ("Observed value", format_value(context.observed)),
        (f"{context.reference_label.title()}", format_value(context.reference)),
        ("Detected", format_timestamp(incident["detected_at"])),
        *extra_rows,
    ]
    grid = "".join(
        f'<div><div class="sn-detail-k">{esc(k)}</div><div class="sn-detail-v">{esc(v)}</div></div>'
        for k, v in fields
    )
    message = incident.get("message") or "No message recorded."
    html(
        f"""
        <div class="sn-card sn-accent sn-accent-{context.tone}">
          <div class="sn-card-head" style="margin-bottom:4px">
            <div><div class="sn-inc-type sn-text-{context.tone}">{esc(humanize(incident['incident_type']))}</div>
            <div class="sn-inc-title">{esc(context.title)}</div></div>
            <div class="sn-chips">{severity_chip(incident['severity'])}{status_chip(incident.get('status'))}</div>
          </div>
          <div class="sn-detail-grid">{grid}</div>
          <div class="sn-detail-k" style="margin-top:16px">Message / context</div>
          <div class="sn-message" style="margin-top:6px">{esc(message)}</div>
          <div class="sn-tech" style="margin-top:10px">{esc(incident['incident_type'])} · {esc(incident.get('metric_name') or '—')} · {esc(incident.get('field_name') or '—')}</div>
        </div>
        """
    )


def ordered_options(values: set[str], order: tuple[str, ...]) -> list[str]:
    known = [v for v in order if v in values]
    return known + sorted(v for v in values if v not in order)

def incident_static_table(
    incidents: list[dict],
) -> None:
    """
    Render incidents using Sentinel's own theme-aware HTML table.
    """

    if not incidents:
        return

    tz = tz_label(
        to_display_tz(
            incidents[0]["detected_at"]
        )
    )

    rows = []

    for incident in incidents:
        detected = to_display_tz(
            incident["detected_at"]
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        observed = (
            f"{incident['observed_value']:.4f}"
            if incident.get("observed_value")
            is not None
            else "—"
        )

        severity = (
            incident.get("severity")
            or "unknown"
        )

        status = (
            incident.get("status")
            or "open"
        )

        rows.append(
            f"""
            <tr>
                <td>{esc(incident["id"])}</td>
                <td>{esc(detected)}</td>
                <td>{esc(humanize(incident["incident_type"]))}</td>
                <td>{esc(incident.get("resource_type") or "—")}</td>
                <td>{esc(humanize(incident.get("metric_name")))}</td>
                <td class="sn-mono">{esc(observed)}</td>
                <td>
                    <span class="sn-text-{severity_tone(severity)}">
                        {esc(severity.upper())}
                    </span>
                </td>
                <td>
                    <span class="sn-text-{status_tone(status)}">
                        {esc(status.title())}
                    </span>
                </td>
            </tr>
            """
        )

    html(
        f"""
        <div class="sn-table-wrap">
            <table class="sn-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Detected At ({esc(tz)})</th>
                        <th>Incident Type</th>
                        <th>Resource</th>
                        <th>Metric</th>
                        <th>Observed Value</th>
                        <th>Severity</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
    )