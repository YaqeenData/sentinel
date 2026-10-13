"""
Plotly figures for the Sentinel dashboard.

Each function receives real rows (already loaded from PostgreSQL or
monitoring.yaml) and returns a figure. No data is generated here.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import plotly.graph_objects as go

from sentinel.dashboard.model import (
    THRESHOLD_STATE_TONE,
    humanize,
    threshold_state,
    to_display_tz,
)
from sentinel.dashboard.theme import COLORS, plotly_layout, rgba, tone_color


# Room for axis tick labels and titles so they are never clipped.
_AXIS_MARGIN = dict(l=56, r=16, t=24, b=40)


def _y_ceiling(values: list[float], threshold: float | None) -> float:
    top = max([v for v in values if v is not None] + [threshold or 0.0, 0.0])
    ceiling = max(top * 1.18, (threshold or 0) * 1.5, 0.05)
    return round(ceiling + 0.05 - (ceiling % 0.05), 2)


def _x_padding(
    times: list[datetime],
    min_pad: timedelta = timedelta(minutes=20),
) -> list[datetime] | None:
    if not times:
        return None
    start, end = min(times), max(times)
    pad = max((end - start) * 0.06, min_pad)
    return [start - pad, end + pad]


def _break_gaps(
    times: list[datetime],
    values: list[float],
    extras: list[list],
    gap: timedelta,
) -> tuple[list, list, list[list]]:
    """
    Insert an empty point wherever two neighbours are further apart than
    ``gap``, so the line stops instead of drawing across hours without data.
    ``extras`` (colours, hover) get a matching filler at the same place.
    """

    out_t: list = []
    out_v: list = []
    out_e: list[list] = [[] for _ in extras]
    for index, (moment, value) in enumerate(zip(times, values)):
        if index and moment - times[index - 1] > gap:
            out_t.append(times[index - 1] + (moment - times[index - 1]) / 2)
            out_v.append(None)
            for column in out_e:
                column.append(None)
        out_t.append(moment)
        out_v.append(value)
        for column, source in zip(out_e, extras):
            column.append(source[index])
    return out_t, out_v, out_e


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
    gap: timedelta | None = None,
) -> go.Figure:
    """
    Metric values against a configured threshold.

    ``connect=True`` draws a line (per-window series). ``connect=False``
    draws isolated markers (incident-level values) so the chart does not
    imply continuous coverage.

    ``gap``: with a line, two points further apart than this are not joined
    (the monitor was stopped in between), and the time axis hugs the data.
    """

    local_times = [to_display_tz(t) for t in times]
    states = [threshold_state(v, threshold) if threshold else "normal" for v in values]
    colors = [tone_color(THRESHOLD_STATE_TONE[s]) for s in states]
    ceiling = _y_ceiling(values + (incident_values or []), threshold)
    axis_range = (
        _x_padding(local_times, timedelta(minutes=2))
        if gap is not None
        else _x_padding(local_times)
    )
    if connect and gap is not None:
        local_times, values, (colors, hover) = _break_gaps(local_times, values, [colors, hover], gap)
        # The filler points draw nothing; give them a valid colour anyway.
        colors = [c or COLORS["cyan"] for c in colors]
        hover = [h or "" for h in hover]

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
            connectgaps=False,
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

    layout = plotly_layout(
        height=height,
        yaxis=dict(
            plotly_layout()["yaxis"],
            range=[0, ceiling],
            automargin=True,
            title=dict(text=metric_label, font=dict(color=COLORS["muted"], size=11)),
        ),
        xaxis=dict(plotly_layout()["xaxis"], range=axis_range, automargin=True),
    )
    layout["margin"] = _AXIS_MARGIN
    figure.update_layout(layout)
    return figure


def numeric_vs_baseline(
    times: list[datetime],
    values: list[float],
    baseline: float | None,
    *,
    hover: list[str],
    tones: list[str],
    metric_label: str,
    height: int = 300,
) -> go.Figure:
    """
    Numeric-drift values (e.g. a window median) against the healthy baseline.

    Markers are colored by incident severity. The y-axis is zoomed around
    the data and the baseline instead of starting at 0, so a shift of a few
    units stays visible.
    """

    local_times = [to_display_tz(t) for t in times]
    points = [v for v in values if v is not None]
    if baseline is not None:
        points.append(baseline)
    if points:
        low, high = min(points), max(points)
        pad = max((high - low) * 0.25, abs(high) * 0.05, 1.0)
        y_range = [low - pad, high + pad]
    else:
        y_range = None

    figure = go.Figure()
    if baseline is not None:
        figure.add_hline(
            y=baseline,
            line=dict(color=COLORS["muted"], width=1.5, dash="dash"),
            annotation_text=f"baseline {baseline:.2f}",
            annotation_position="top left",
            annotation_font=dict(color=COLORS["muted"], size=11),
        )

    figure.add_trace(
        go.Scatter(
            x=local_times,
            y=values,
            mode="markers",
            marker=dict(
                size=12,
                color=[tone_color(t) for t in tones],
                line=dict(color=COLORS["card"], width=2),
            ),
            hovertext=hover,
            hoverinfo="text",
            name=metric_label,
        )
    )

    layout = plotly_layout(
        height=height,
        yaxis=dict(
            plotly_layout()["yaxis"],
            range=y_range,
            automargin=True,
            title=dict(text=metric_label, font=dict(color=COLORS["muted"], size=11)),
        ),
        xaxis=dict(plotly_layout()["xaxis"], range=_x_padding(local_times), automargin=True),
    )
    layout["margin"] = _AXIS_MARGIN
    figure.update_layout(layout)
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
        yaxis=dict(plotly_layout()["yaxis"], range=[0, min(1.0, top * 1.22)], tickformat=".0%", automargin=True),
        xaxis=dict(plotly_layout()["xaxis"], automargin=True),
    )
    layout["margin"] = dict(l=48, r=12, t=34, b=36)
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