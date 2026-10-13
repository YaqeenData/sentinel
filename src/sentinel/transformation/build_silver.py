import os
import tempfile

import polars as pl
from google.cloud import storage

from sentinel.ingestion.gcs import read_ndjson
from sentinel.transformation.observations import normalize_observation


SILVER_OBJECT = (
    "silver/observations/run_id=001/observations.parquet"
)


def build_observations_dataframe() -> pl.DataFrame:
    """
    Read raw FHIR Observations from Bronze and transform them
    into the normalized Silver Observation structure.
    """

    rows = []

    for observation in read_ndjson("Observation"):
        rows.extend(normalize_observation(observation))

    df = pl.DataFrame(rows)

    # Convert Silver columns to their expected data types.
    #
    # FHIR timestamps are ISO-8601/RFC-3339 timestamps such as:
    # 2017-11-29T11:43:42+03:00
    #
    # %+ allows Polars to parse the timezone offset.
    # strict=True ensures parsing problems fail loudly
    # instead of silently becoming null.
    df = df.with_columns(
        pl.col("event_time").str.to_datetime(
            format="%+",
            time_zone="UTC",
            strict=True,
        ),

        pl.col("issued_time").str.to_datetime(
            format="%+",
            time_zone="UTC",
            strict=True,
        ),

        pl.col("numeric_value").cast(
            pl.Float64,
            strict=True,
        ),
    )

    return df


def validate_silver(df: pl.DataFrame) -> None:
    """
    Run basic validation before persisting Silver.
    """

    print("\n=== SILVER VALIDATION ===")

    summary = df.select(
        pl.len().alias("rows"),

        pl.col("event_time")
        .null_count()
        .alias("event_time_nulls"),

        pl.col("issued_time")
        .null_count()
        .alias("issued_time_nulls"),

        pl.col("event_time")
        .min()
        .alias("earliest"),

        pl.col("event_time")
        .max()
        .alias("latest"),
    )

    print(summary)

    print("\n=== SILVER SCHEMA ===")
    print(df.schema)

    # Do not upload corrupted Silver timestamps.
    event_time_nulls = df["event_time"].null_count()
    issued_time_nulls = df["issued_time"].null_count()

    if event_time_nulls > 0:
        raise ValueError(
            f"Silver contains {event_time_nulls} null event_time values."
        )

    if issued_time_nulls > 0:
        raise ValueError(
            f"Silver contains {issued_time_nulls} null issued_time values."
        )

    print("\nSilver validation passed.")


def upload_silver(df: pl.DataFrame) -> None:
    """
    Write the Silver DataFrame as Parquet and upload it to GCS.
    """

    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET"]

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(SILVER_OBJECT)

    with tempfile.NamedTemporaryFile(
        suffix=".parquet"
    ) as tmp:

        df.write_parquet(tmp.name)

        blob.upload_from_filename(tmp.name)

    print(
        f"\nUploaded {df.height:,} rows to "
        f"gs://{bucket_name}/{SILVER_OBJECT}"
    )


if __name__ == "__main__":

    print("Building Silver DataFrame...")

    df = build_observations_dataframe()

    print(
        f"Built Silver DataFrame with "
        f"{df.height:,} rows and {df.width} columns."
    )

    # Validate BEFORE uploading.
    validate_silver(df)

    print("\nUploading Silver DataFrame to GCS...")

    upload_silver(df)