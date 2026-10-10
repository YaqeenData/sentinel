"""
Sentinel storage layer.

The only module that talks to the PostgreSQL monitoring database.
Every other part of Sentinel reads and writes through these functions.
"""

import os
from datetime import datetime

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


load_dotenv()


POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "sentinel")
POSTGRES_USER = os.getenv("POSTGRES_USER", "sentinel")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


# ------------------------------------------------------------
# SQL
# ------------------------------------------------------------

SELECT_RESOURCE_ID = """
    SELECT id
    FROM resources
    WHERE resource_type = %s
"""

UPSERT_QUALITY_METRIC = """
    INSERT INTO quality_metrics (
        resource_id,
        window_start,
        window_end,
        metric_name,
        field_name,
        metric_value
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (resource_id, window_start, metric_name, field_name)
    DO UPDATE SET
        window_end   = EXCLUDED.window_end,
        metric_value = EXCLUDED.metric_value,
        created_at   = now()
"""

SELECT_LATEST_QUALITY_WINDOW = """
    SELECT
        id,
        window_start,
        window_end,
        metric_name,
        field_name,
        metric_value,
        created_at
    FROM quality_metrics
    WHERE resource_id = %s
      AND window_end = (
            SELECT max(window_end)
            FROM quality_metrics
            WHERE resource_id = %s
          )
    ORDER BY metric_name, field_name
"""

INSERT_BASELINE = """
    INSERT INTO baseline_metrics (
        resource_id,
        metric_name,
        field_name,
        baseline_value,
        lower_threshold,
        upper_threshold
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id
"""

SELECT_CURRENT_BASELINE = """
    SELECT
        id,
        metric_name,
        field_name,
        baseline_value,
        lower_threshold,
        upper_threshold,
        calculated_at
    FROM baseline_metrics
    WHERE resource_id = %s
      AND metric_name = %s
      AND field_name IS NOT DISTINCT FROM %s
    ORDER BY calculated_at DESC, id DESC
    LIMIT 1
"""

INSERT_SCHEMA_CHANGE = """
    INSERT INTO schema_history (
        resource_id,
        observed_at,
        field_name,
        observed_type,
        previous_type,
        change_type
    )
    VALUES (%s, COALESCE(%s, now()), %s, %s, %s, %s)
    RETURNING id
"""

INSERT_INCIDENT = """
    INSERT INTO incidents (
        resource_id,
        detected_at,
        incident_type,
        metric_name,
        field_name,
        observed_value,
        baseline_value,
        severity,
        message,
        quality_metric_id,
        baseline_metric_id,
        schema_change_id
    )
    VALUES (%s, COALESCE(%s, now()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""


# ------------------------------------------------------------
# Connection
# ------------------------------------------------------------

def get_connection() -> psycopg.Connection:
    """
    Open a connection to the Sentinel monitoring database.
    """

    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        row_factory=dict_row,
    )


def get_resource_id(
    connection: psycopg.Connection,
    resource_type: str,
) -> int:
    """
    Return the id of a monitored resource type, for example "Observation".
    """

    with connection.cursor() as cursor:
        cursor.execute(SELECT_RESOURCE_ID, (resource_type,))
        row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Unknown resource type: {resource_type!r}. "
            f"Add it to the resources table first."
        )

    return row["id"]


# ------------------------------------------------------------
# quality_metrics
# ------------------------------------------------------------

def save_quality_window(
    resource_type: str,
    window_start: datetime,
    window_end: datetime,
    metrics: list[dict],
) -> int:
    """
    Persist the metrics of one completed quality window.

    Safe to rerun: the same resource + window + metric + field
    is updated, never duplicated.

    metrics: one dict per metric, for example
        {"metric_name": "record_count", "field_name": None, "metric_value": 300}
        {"metric_name": "null_rate", "field_name": "numeric_value", "metric_value": 0.02}

    Returns the number of metric rows written.
    """

    if not metrics:
        return 0

    with get_connection() as connection:
        resource_id = get_resource_id(connection, resource_type)

        rows = [
            (
                resource_id,
                window_start,
                window_end,
                metric["metric_name"],
                metric.get("field_name"),
                metric["metric_value"],
            )
            for metric in metrics
        ]

        with connection.cursor() as cursor:
            cursor.executemany(UPSERT_QUALITY_METRIC, rows)

    return len(rows)


def get_latest_quality_window(
    resource_type: str,
) -> list[dict]:
    """
    Return the metric rows of the latest completed window
    for one resource type. Empty list when nothing is stored yet.
    """

    with get_connection() as connection:
        resource_id = get_resource_id(connection, resource_type)

        with connection.cursor() as cursor:
            cursor.execute(
                SELECT_LATEST_QUALITY_WINDOW,
                (resource_id, resource_id),
            )
            return cursor.fetchall()


# ------------------------------------------------------------
# baseline_metrics
# ------------------------------------------------------------

def save_baseline(
    resource_type: str,
    metric_name: str,
    baseline_value: float,
    field_name: str | None = None,
    lower_threshold: float | None = None,
    upper_threshold: float | None = None,
) -> int:
    """
    Store a newly calculated baseline.

    Every call adds a new row; older baselines are kept as history.
    Returns the id of the new baseline row.
    """

    with get_connection() as connection:
        resource_id = get_resource_id(connection, resource_type)

        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_BASELINE,
                (
                    resource_id,
                    metric_name,
                    field_name,
                    baseline_value,
                    lower_threshold,
                    upper_threshold,
                ),
            )
            return cursor.fetchone()["id"]


def get_current_baseline(
    resource_type: str,
    metric_name: str,
    field_name: str | None = None,
) -> dict | None:
    """
    Return the newest baseline for one metric + field,
    or None when no baseline has been calculated yet.
    """

    with get_connection() as connection:
        resource_id = get_resource_id(connection, resource_type)

        with connection.cursor() as cursor:
            cursor.execute(
                SELECT_CURRENT_BASELINE,
                (resource_id, metric_name, field_name),
            )
            return cursor.fetchone()


# ------------------------------------------------------------
# schema_history
# ------------------------------------------------------------

def save_schema_change(
    resource_type: str,
    field_name: str,
    change_type: str,
    previous_type: str | None = None,
    observed_type: str | None = None,
    observed_at: datetime | None = None,
) -> int:
    """
    Record one observed schema change.

    change_type must be one of: added, removed, type_changed.
    observed_at defaults to the current time.
    Returns the id of the new schema_history row.
    """

    with get_connection() as connection:
        resource_id = get_resource_id(connection, resource_type)

        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_SCHEMA_CHANGE,
                (
                    resource_id,
                    observed_at,
                    field_name,
                    observed_type,
                    previous_type,
                    change_type,
                ),
            )
            return cursor.fetchone()["id"]


# ------------------------------------------------------------
# incidents
# ------------------------------------------------------------

def save_incident(
    resource_type: str,
    incident_type: str,
    severity: str,
    metric_name: str | None = None,
    field_name: str | None = None,
    observed_value: float | None = None,
    baseline_value: float | None = None,
    message: str | None = None,
    quality_metric_id: int | None = None,
    baseline_metric_id: int | None = None,
    schema_change_id: int | None = None,
    detected_at: datetime | None = None,
) -> int:
    """
    Record one detected incident. New incidents start with status 'open'.

    incident_type must be one of the values allowed by the schema.
    severity must be one of: low, medium, high, critical.

    Evidence ids:
        metric incident -> quality_metric_id + baseline_metric_id
        schema incident -> schema_change_id

    detected_at defaults to the current time.
    Returns the id of the new incident row.
    """

    with get_connection() as connection:
        resource_id = get_resource_id(connection, resource_type)

        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_INCIDENT,
                (
                    resource_id,
                    detected_at,
                    incident_type,
                    metric_name,
                    field_name,
                    observed_value,
                    baseline_value,
                    severity,
                    message,
                    quality_metric_id,
                    baseline_metric_id,
                    schema_change_id,
                ),
            )
            return cursor.fetchone()["id"]