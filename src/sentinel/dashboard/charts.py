"""
Plotly figures for the Sentinel dashboard.

Each function receives real rows (already loaded from PostgreSQL or
monitoring.yaml) and returns a figure. No data is generated here.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import plotly.graph_objects as go

from sentinel.dashboard.model1 import (
    THRESHOLD_STATE_TONE,
    humanize,
    threshold_state,
    to_display_tz,
)
from sentinel.dashboard.theme import COLORS, plotly_layout, rgba, tone_color


def _y_ceiling(values: list[float], threshold: float | None) -> float:
    top = max([v for v in values if v is not None] + [threshold or 0.0, 0.0])
    ceiling = max(top * 1.18, (threshold or 0) * 1.5, 0.05)
    return round(ceiling + 0.05 - (ceiling % 0.05), 2)


def _x_padding(times: list[datetime]) -> list[datetime] | None:
    if not times:
        return None
    start, end = min(times), max(times)
    pad = max((end - start) * 0.06, timedelta(minutes=20))
    return [start - pad, end + pad]


def metric_vs_threshold(
    times: list[datetime],
    values: list[float],
    threshold: float | None,
    *,
    hover: list[str],
    connect: bool,
    metric_label: str,
    incident_times: list[datetime] | None = None,
    incident_values: list[float] | None = None,
    height: int = 320,
) -> go.Figure:
    """
    Metric values against a configured threshold.

    ``connect=True`` draws a line (per-window series). ``connect=False``
    draws isolated markers (incident-level values) so the chart does not
    imply continuous coverage.
    """

    local_times = [to_display_tz(t) for t in times]
    states = [threshold_state(v, threshold) if threshold else "normal" for v in values]
    colors = [tone_color(THRESHOLD_STATE_TONE[s]) for s in states]
    ceiling = _y_ceiling(values + (incident_values or []), threshold)

    figure = go.Figure()
    if threshold is not None:
        figure.add_hrect(
            y0=threshold, y1=ceiling, fillcolor=rgba(COLORS["rose"], 0.06), line_width=0, layer="below"
        )
        figure.add_hline(
            y=threshold,
            line=dict(color=COLORS["amber"], width=1.5, dash="dash"),
            annotation_text=f"threshold {threshold:.2f}",
            annotation_position="top left",
            annotation_font=dict(color=COLORS["amber"], size=11),
        )

    figure.add_trace(
        go.Scatter(
            x=local_times,
            y=values,
            mode="lines+markers" if connect else "markers",
            line=dict(color=COLORS["cyan"], width=2, shape="linear"),
            marker=dict(
                size=7 if connect else 12,
                color=colors,
                line=dict(color=COLORS["card"], width=2),
            ),
            hovertext=hover,
            hoverinfo="text",
            name=metric_label,
        )
    )

    if incident_times:
        figure.add_trace(
            go.Scatter(
                x=[to_display_tz(t) for t in incident_times],
                y=incident_values,
                mode="markers",
                marker=dict(size=13, color="rgba(0,0,0,0)", line=dict(color=COLORS["rose"], width=2)),
                hoverinfo="skip",
                name="Incident",
            )
        )

    figure.update_layout(
        plotly_layout(
            height=height,
            yaxis=dict(
                plotly_layout()["yaxis"],
                range=[0, ceiling],
                title=dict(text=metric_label, font=dict(color=COLORS["muted"], size=11)),
            ),
            xaxis=dict(plotly_layout()["xaxis"], range=_x_padding(local_times)),
        )
    )
    return figure


def distribution_comparison(
    labels: list[str],
    hover_names: list[str],
    baseline: list[float],
    detected: list[float] | None,
    height: int = 300,
) -> go.Figure:
    """Grouped bars: configured baseline vs detected distribution (0–1)."""

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=baseline,
            name="Baseline",
            marker=dict(color=rgba(COLORS["green"], 0.85), line=dict(width=0)),
            text=[f"{v:.1%}" for v in baseline],
            textposition="outside",
            textfont=dict(color=COLORS["muted"], size=11),
            customdata=hover_names,
            hovertemplate="%{customdata}<br>Baseline %{y:.2%}<extra></extra>",
        )
    )
    if detected is not None:
        figure.add_trace(
            go.Bar(
                x=labels,
                y=detected,
                name="Detected",
                marker=dict(color=COLORS["rose"], line=dict(width=0)),
                text=[f"{v:.1%}" for v in detected],
                textposition="outside",
                textfont=dict(color=COLORS["text"], size=11),
                customdata=hover_names,
                hovertemplate="%{customdata}<br>Detected %{y:.2%}<extra></extra>",
            )
        )

    top = max(baseline + (detected or []) + [0.1])
    layout = plotly_layout(
        height=height,
        barmode="group",
        bargap=0.34,
        bargroupgap=0.08,
        showlegend=True,
        yaxis=dict(plotly_layout()["yaxis"], range=[0, min(1.0, top * 1.22)], tickformat=".0%"),
    )
    layout["margin"] = dict(l=8, r=12, t=34, b=8)
    figure.update_layout(layout)
    return figure


def counts_by_category(
    labels: list[str], counts: list[int], tones: list[str] | None = None, height: int = 260
) -> go.Figure:
    """Horizontal bars for incident counts by type."""

    colors = [tone_color(t) for t in tones] if tones else COLORS["cyan"]
    figure = go.Figure(
        go.Bar(
            x=counts,
            y=labels,
            orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            text=counts,
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=11),
            hovertemplate="%{y}: %{x}<extra></extra>",
        )
    )
    figure.update_layout(
        plotly_layout(
            height=max(160, min(height, 60 + 38 * len(labels))),
            bargap=0.4,
            yaxis=dict(plotly_layout()["yaxis"], autorange="reversed", gridcolor="rgba(0,0,0,0)"),
            xaxis=dict(plotly_layout()["xaxis"], range=[0, max(counts + [1]) * 1.2], dtick=max(1, max(counts + [1]) // 5)),
        )
    )
    return figure


def events_over_time(
    times: list[datetime], tones: list[str], hover: list[str], height: int = 240
) -> go.Figure:
    """One marker per incident on a time axis, colored by severity."""

    local_times = [to_display_tz(t) for t in times]
    figure = go.Figure(
        go.Scatter(
            x=local_times,
            y=[1] * len(local_times),
            mode="markers",
            marker=dict(
                size=14,
                symbol="diamond",
                color=[tone_color(t) for t in tones],
                line=dict(color=COLORS["card"], width=2),
            ),
            hovertext=hover,
            hoverinfo="text",
        )
    )
    figure.update_layout(
        plotly_layout(
            height=height,
            yaxis=dict(plotly_layout()["yaxis"], visible=False, range=[0.5, 1.5]),
            xaxis=dict(plotly_layout()["xaxis"], range=_x_padding(local_times)),
        )
    )
    return figure


_CHANGE_TONE = {"added": "cyan", "type_changed": "amber", "removed": "rose"}


def schema_timeline(rows: list[dict], height: int = 280) -> go.Figure:
    """Schema events: time on x, field on y, colored by change type."""

    figure = go.Figure()
    for change_type, tone in _CHANGE_TONE.items():
        subset = [r for r in rows if r["change_type"] == change_type]
        if not subset:
            continue
        figure.add_trace(
            go.Scatter(
                x=[to_display_tz(r["observed_at"]) for r in subset],
                y=[f"{r['resource_type']}.{r['field_name']}" for r in subset],
                mode="markers",
                name=humanize(change_type),
                marker=dict(size=11, color=tone_color(tone), line=dict(color=COLORS["card"], width=2)),
                hovertext=[
                    f"{humanize(change_type)} · {r['field_name']}<br>"
                    f"{r.get('previous_type') or '—'} → {r.get('observed_type') or '—'}"
                    for r in subset
                ],
                hoverinfo="text",
            )
        )
    fields = {f"{r['resource_type']}.{r['field_name']}" for r in rows}
    layout = plotly_layout(height=max(height, 90 + 30 * len(fields)), showlegend=True)
    layout["margin"] = dict(l=8, r=12, t=34, b=8)
    figure.update_layout(layout)
    return figure
