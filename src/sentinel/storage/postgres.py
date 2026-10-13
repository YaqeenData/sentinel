import os
from datetime import datetime

import psycopg
from dotenv import load_dotenv


load_dotenv()


POSTGRES_HOST = os.getenv(
    "POSTGRES_HOST",
    "localhost",
)

POSTGRES_PORT = int(
    os.getenv(
        "POSTGRES_PORT",
        "5433",
    )
)

POSTGRES_DB = os.getenv(
    "POSTGRES_DB",
)

POSTGRES_USER = os.getenv(
    "POSTGRES_USER",
)

POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
)


def get_connection() -> psycopg.Connection:
    """
    Create a connection to the Sentinel PostgreSQL database.
    """

    if not POSTGRES_DB:
        raise ValueError(
            "POSTGRES_DB is not configured."
        )

    if not POSTGRES_USER:
        raise ValueError(
            "POSTGRES_USER is not configured."
        )

    if not POSTGRES_PASSWORD:
        raise ValueError(
            "POSTGRES_PASSWORD is not configured."
        )

    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def get_resource_id(
    connection: psycopg.Connection,
    resource_type: str,
) -> int:
    """
    Get the database id for a FHIR resource type.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT id
            FROM resources
            WHERE resource_type = %s
            """,
            (resource_type,),
        )

        row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Unknown resource type: {resource_type}"
        )

    return row[0]

def upsert_quality_metric(
    *,
    resource_type: str,
    window_start: datetime,
    window_end: datetime,
    metric_name: str,
    metric_value: float,
    field_name: str | None = None,
) -> int:
    """
    Insert or update one completed-window quality metric.

    Returns
    -------
    int
        The database id of the quality metric.
    """

    with get_connection() as connection:

        resource_id = get_resource_id(
            connection,
            resource_type,
        )

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO quality_metrics (
                    resource_id,
                    window_start,
                    window_end,
                    metric_name,
                    field_name,
                    metric_value
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT ON CONSTRAINT
                    uq_quality_metrics_resource_window_metric_field
                DO UPDATE SET
                    window_end = EXCLUDED.window_end,
                    metric_value = EXCLUDED.metric_value
                RETURNING id
                """,
                (
                    resource_id,
                    window_start,
                    window_end,
                    metric_name,
                    field_name,
                    metric_value,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    if row is None:
        raise RuntimeError(
            "Quality metric write did not return an id."
        )

    return row[0]


def insert_incident(
    *,
    resource_type: str,
    detected_at: datetime,
    incident_type: str,
    severity: str,
    metric_name: str | None = None,
    field_name: str | None = None,
    observed_value: float | None = None,
    baseline_value: float | None = None,
    message: str | None = None,
    status: str = "open",
    quality_metric_id: int | None = None,
    baseline_metric_id: int | None = None,
    schema_change_id: int | None = None,
) -> int:
    """
    Insert a Sentinel data-health incident.

    Returns
    -------
    int
        The id of the newly created incident.
    """

    with get_connection() as connection:

        resource_id = get_resource_id(
            connection,
            resource_type,
        )

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO incidents (
                    resource_id,
                    detected_at,
                    incident_type,
                    metric_name,
                    field_name,
                    observed_value,
                    baseline_value,
                    severity,
                    status,
                    message,
                    quality_metric_id,
                    baseline_metric_id,
                    schema_change_id
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    resource_id,
                    detected_at,
                    incident_type,
                    metric_name,
                    field_name,
                    observed_value,
                    baseline_value,
                    severity,
                    status,
                    message,
                    quality_metric_id,
                    baseline_metric_id,
                    schema_change_id,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    if row is None:
        raise RuntimeError(
            "Incident insert did not return an id."
        )

    return row[0]

def get_open_incident_id(
    *,
    resource_type: str,
    incident_type: str,
    field_name: str | None = None,
) -> int | None:
    """
    Return the most recent matching open incident, if one exists.
    """

    with get_connection() as connection:

        resource_id = get_resource_id(
            connection,
            resource_type,
        )

        query = """
            SELECT id
            FROM incidents
            WHERE resource_id = %s
              AND incident_type = %s
              AND status = 'open'
        """

        params: list = [
            resource_id,
            incident_type,
        ]

        if field_name is not None:
            query += """
            AND field_name = %s
            """
            params.append(field_name)

        query += """
            ORDER BY detected_at DESC
            LIMIT 1
        """

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                params,
            )

            row = cursor.fetchone()

    return row[0] if row else None

def get_open_incidents_by_types(
    *,
    resource_type: str,
    incident_types: tuple[str, ...],
) -> list[dict]:
    """
    Return all currently open incidents for the supplied incident types.
    """

    if not incident_types:
        return []

    with get_connection() as connection:
        resource_id = get_resource_id(
            connection,
            resource_type,
        )

        placeholders = ", ".join(
            ["%s"] * len(incident_types)
        )

        query = f"""
            SELECT
                id,
                incident_type,
                field_name
            FROM incidents
            WHERE resource_id = %s
                AND status = 'open'
                AND incident_type IN ({placeholders})
            ORDER BY detected_at DESC
        """

        params = [
            resource_id,
            *incident_types,
        ]

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                params,
            )

            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "incident_type": row[1],
            "field_name": row[2],
        }
        for row in rows
    ]
    
def resolve_incident(
        incident_id: int,
    ) -> None:
        """
        Mark an existing Sentinel incident as resolved.
        """

        with get_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    UPDATE incidents
                    SET status = 'resolved'
                    WHERE id = %s
                    AND status = 'open'
                    """,
                    (incident_id,),
                )

            connection.commit()