"""
Read-only PostgreSQL queries for the Sentinel dashboard.

All connections come from the existing
``sentinel.storage.postgres.get_connection`` helper. Every function accepts
an optional open connection so the dashboard can load a full snapshot over
one connection (``load_dashboard_snapshot``), while each function also works
on its own. No Streamlit code lives here.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from sentinel.storage.postgres import get_connection


_INCIDENT_COLUMNS = """
    i.id,
    r.resource_type,
    i.detected_at,
    i.incident_type,
    i.metric_name,
    i.field_name,
    i.observed_value,
    i.baseline_value,
    i.severity,
    i.status,
    i.message,
    qm.window_start,
    qm.window_end
"""

_INCIDENT_FROM = """
    FROM incidents AS i
    JOIN resources AS r
        ON r.id = i.resource_id
    LEFT JOIN quality_metrics AS qm
        ON qm.id = i.quality_metric_id
"""


@contextmanager
def _connection(
    connection: psycopg.Connection | None,
) -> Iterator[psycopg.Connection]:
    if connection is not None:
        yield connection
        return
    with get_connection() as owned:
        yield owned


def _fetch_all(
    query: str,
    params: dict[str, Any] | None = None,
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    with _connection(connection) as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params or {})
            return cursor.fetchall()


def _fetch_one(
    query: str,
    params: dict[str, Any] | None = None,
    connection: psycopg.Connection | None = None,
) -> dict | None:
    rows = _fetch_all(query, params, connection)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


def get_latest_incident(
    incident_type: str | None = None,
    status: str | None = None,
    connection: psycopg.Connection | None = None,
) -> dict | None:
    """
    Most recently detected incident, optionally filtered by type and status.
    Includes the processing window of the linked quality metric, if any.
    """

    return _fetch_one(
        f"""
        SELECT {_INCIDENT_COLUMNS}
        {_INCIDENT_FROM}
        WHERE (%(incident_type)s::text IS NULL OR i.incident_type = %(incident_type)s::text)
          AND (%(status)s::text IS NULL OR i.status = %(status)s::text)
        ORDER BY i.detected_at DESC, i.id DESC
        LIMIT 1;
        """,
        {"incident_type": incident_type, "status": status},
        connection,
    )


def get_open_incident_count(connection: psycopg.Connection | None = None) -> int:
    """Number of currently open incidents."""

    row = _fetch_one(
        "SELECT COUNT(*) AS open_count FROM incidents WHERE status = 'open';",
        connection=connection,
    )
    return int(row["open_count"]) if row else 0


def get_open_incident_counts(
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """Open-incident counts per (resource_type, severity)."""

    return _fetch_all(
        """
        SELECT r.resource_type, i.severity, COUNT(*) AS incident_count
        FROM incidents AS i
        JOIN resources AS r
            ON r.id = i.resource_id
        WHERE i.status = 'open'
        GROUP BY r.resource_type, i.severity;
        """,
        connection=connection,
    )


def get_recent_incidents(
    limit: int = 500,
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """Recent incidents, newest first."""

    return _fetch_all(
        f"""
        SELECT {_INCIDENT_COLUMNS}
        {_INCIDENT_FROM}
        ORDER BY i.detected_at DESC, i.id DESC
        LIMIT %(limit)s;
        """,
        {"limit": limit},
        connection,
    )


def get_incident_counts_by_type(
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """All-time incident counts grouped by incident type."""

    return _fetch_all(
        """
        SELECT incident_type, COUNT(*) AS incident_count
        FROM incidents
        GROUP BY incident_type
        ORDER BY incident_count DESC;
        """,
        connection=connection,
    )


def get_incident_counts_by_status(
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """All-time incident counts grouped by status."""

    return _fetch_all(
        """
        SELECT COALESCE(status, 'open') AS status, COUNT(*) AS incident_count
        FROM incidents
        GROUP BY COALESCE(status, 'open');
        """,
        connection=connection,
    )


def get_incident_counts_by_severity(
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """All-time incident counts grouped by severity."""

    return _fetch_all(
        """
        SELECT severity, COUNT(*) AS incident_count
        FROM incidents
        GROUP BY severity;
        """,
        connection=connection,
    )


def get_incident_history(
    incident_type: str,
    metric_name: str | None = None,
    limit: int = 1000,
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """
    Incidents of one type (and metric), oldest first — the persisted
    metric values at detection time. Used for detector trend charts.
    """

    rows = _fetch_all(
        f"""
        SELECT {_INCIDENT_COLUMNS}
        {_INCIDENT_FROM}
        WHERE i.incident_type = %(incident_type)s
          AND (%(metric_name)s::text IS NULL OR i.metric_name = %(metric_name)s::text)
        ORDER BY i.detected_at DESC, i.id DESC
        LIMIT %(limit)s;
        """,
        {"incident_type": incident_type, "metric_name": metric_name, "limit": limit},
        connection,
    )
    return list(reversed(rows))


# ---------------------------------------------------------------------------
# Metrics, schema, resources
# ---------------------------------------------------------------------------


def get_metric_series(
    metric_name: str,
    field_name: str | None,
    limit: int = 500,
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """
    Per-window values of one profiled metric from quality_metrics, oldest
    first. Empty when the pipeline does not persist that metric per window.
    """

    rows = _fetch_all(
        """
        SELECT r.resource_type, qm.window_start, qm.window_end, qm.metric_value
        FROM quality_metrics AS qm
        JOIN resources AS r
            ON r.id = qm.resource_id
        WHERE qm.metric_name = %(metric_name)s
          AND qm.field_name IS NOT DISTINCT FROM %(field_name)s::text
        ORDER BY qm.window_end DESC
        LIMIT %(limit)s;
        """,
        {"metric_name": metric_name, "field_name": field_name, "limit": limit},
        connection,
    )
    return list(reversed(rows))


def get_latest_window_health(
    resource_type: str = "Observation",
    connection: psycopg.Connection | None = None,
) -> dict | None:
    """
    record_count and null_rate of the latest completed window.

    Only completed windows are written to quality_metrics, so the newest
    record_count row is the latest completed window. null_rate is joined
    from the same window and may be missing (NULL).
    """

    return _fetch_one(
        """
        SELECT
            rc.window_start,
            rc.window_end,
            rc.metric_value AS record_count,
            nr.metric_value AS null_rate,
            nr.field_name   AS null_rate_field
        FROM quality_metrics AS rc
        JOIN resources AS r
            ON r.id = rc.resource_id
        LEFT JOIN quality_metrics AS nr
            ON nr.resource_id = rc.resource_id
           AND nr.window_start = rc.window_start
           AND nr.metric_name = 'null_rate'
        WHERE r.resource_type = %(resource_type)s
          AND rc.metric_name = 'record_count'
          AND rc.field_name IS NULL
        ORDER BY rc.window_end DESC
        LIMIT 1;
        """,
        {"resource_type": resource_type},
        connection,
    )


def get_schema_history(
    limit: int = 500,
    connection: psycopg.Connection | None = None,
) -> list[dict]:
    """Recorded schema events, newest first."""

    return _fetch_all(
        """
        SELECT
            sh.id,
            r.resource_type,
            sh.observed_at,
            sh.field_name,
            sh.previous_type,
            sh.observed_type,
            sh.change_type
        FROM schema_history AS sh
        JOIN resources AS r
            ON r.id = sh.resource_id
        ORDER BY sh.observed_at DESC, sh.id DESC
        LIMIT %(limit)s;
        """,
        {"limit": limit},
        connection,
    )


def get_resource_types(connection: psycopg.Connection | None = None) -> list[str]:
    """FHIR resource types registered in the resources table."""

    rows = _fetch_all(
        "SELECT resource_type FROM resources ORDER BY id;",
        connection=connection,
    )
    return [row["resource_type"] for row in rows]


def get_data_as_of(connection: psycopg.Connection | None = None) -> datetime | None:
    """
    Newest timestamp Sentinel has written: latest processing window end,
    incident detection, or schema observation — whichever is latest.
    """

    row = _fetch_one(
        """
        SELECT GREATEST(
            (SELECT MAX(window_end) FROM quality_metrics),
            (SELECT MAX(detected_at) FROM incidents),
            (SELECT MAX(observed_at) FROM schema_history)
        ) AS data_as_of;
        """,
        connection=connection,
    )
    return row["data_as_of"] if row else None


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def load_dashboard_snapshot(
    categorical_incident_type: str | None,
    categorical_metric_name: str | None,
    categorical_field_name: str | None,
    incident_limit: int = 500,
) -> dict[str, Any]:
    """
    Everything the dashboard renders, read over a single connection.
    Categorical arguments come from monitoring.yaml; pass ``None`` when the
    categorical detector is not configured.
    """

    with get_connection() as connection:
        snapshot: dict[str, Any] = {
            "incidents": get_recent_incidents(incident_limit, connection),
            "open_counts": get_open_incident_counts(connection),
            "counts_by_type": get_incident_counts_by_type(connection),
            "counts_by_status": get_incident_counts_by_status(connection),
            "counts_by_severity": get_incident_counts_by_severity(connection),
            "latest_open_incident": get_latest_incident(status="open", connection=connection),
            "latest_incident": get_latest_incident(connection=connection),
            "schema_history": get_schema_history(connection=connection),
            "resource_types": get_resource_types(connection),
            "data_as_of": get_data_as_of(connection),
            "window_health": get_latest_window_health(connection=connection),
            "categorical_history": [],
            "categorical_window_series": [],
            "contract_violation_series": get_metric_series(
            "contract_violation_count",
            None,
            connection=connection,
            ),
            "contract_rows_checked_series": get_metric_series(
                "contract_rows_checked",
                None,
                connection=connection,
            ),
        }
        

        if categorical_incident_type:
            snapshot["categorical_history"] = get_incident_history(
                categorical_incident_type, categorical_metric_name, connection=connection
            )
        if categorical_metric_name:
            snapshot["categorical_window_series"] = get_metric_series(
                categorical_metric_name, categorical_field_name, connection=connection
            )

    snapshot["fetched_at"] = datetime.now(timezone.utc)
    return snapshot
