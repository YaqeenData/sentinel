"""
Build the Silver Encounter table from Bronze and upload it to GCS.

"""

import io

import polars as pl

from sentinel.ingestion.gcs import get_bucket, read_ndjson
from sentinel.transformation.encounters import normalize_encounter


SILVER_OBJECT = (
    "silver/encounters/run_id=001/encounters.parquet"
)

# Every column starts as text, then we convert the ones that need it.
RAW_SCHEMA = {
    "encounter_id": pl.String,
    "patient_id": pl.String,
    "status": pl.String,
    "class_code": pl.String,
    "type_code": pl.String,
    "type_display": pl.String,
    "start_time": pl.String,
    "end_time": pl.String,
    "reason_code": pl.String,
    "reason_display": pl.String,
    "organization_name": pl.String,
}


def build_encounters_dataframe() -> pl.DataFrame:
    """
    Read raw FHIR Encounters from Bronze and transform them
    into the normalized Silver Encounter structure.
    """

    rows = []

    for encounter in read_ndjson("Encounter"):
        rows.extend(normalize_encounter(encounter))

    df = pl.DataFrame(rows, schema=RAW_SCHEMA)

    # period.start / period.end are full timestamps with an offset,
    df = df.with_columns(
        pl.col("start_time").str.to_datetime(
            format="%+",
            time_zone="UTC",
            strict=True,
        ),

        pl.col("end_time").str.to_datetime(
            format="%+",
            time_zone="UTC",
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
        pl.col("encounter_id").n_unique().alias("unique_encounters"),
        pl.col("patient_id").n_unique().alias("unique_patients"),
        pl.col("encounter_id").null_count().alias("encounter_id_nulls"),
        pl.col("patient_id").null_count().alias("patient_id_nulls"),
        pl.col("start_time").null_count().alias("start_time_nulls"),
        pl.col("start_time").min().alias("earliest"),
        pl.col("start_time").max().alias("latest"),
    )

    print(summary)

    print("\n=== CLASS VALUES ===")
    print(df["class_code"].value_counts(sort=True))

    print("\n=== SILVER SCHEMA ===")
    print(df.schema)

    if df.height == 0:
        raise ValueError("Silver contains no encounters.")

    encounter_id_nulls = df["encounter_id"].null_count()
    patient_id_nulls = df["patient_id"].null_count()
    start_time_nulls = df["start_time"].null_count()
    duplicates = df.height - df["encounter_id"].n_unique()

    # An encounter that ends before it starts is corrupted data.
    ends_before_start = df.filter(
        pl.col("end_time") < pl.col("start_time")
    ).height

    if encounter_id_nulls > 0:
        raise ValueError(
            f"Silver contains {encounter_id_nulls} null encounter_id values."
        )

    # encounter_id is the primary key: one row per encounter.
    if duplicates > 0:
        raise ValueError(
            f"Silver contains {duplicates} duplicate encounter_id values."
        )

    if patient_id_nulls > 0:
        raise ValueError(
            f"Silver contains {patient_id_nulls} null patient_id values."
        )

    if start_time_nulls > 0:
        raise ValueError(
            f"Silver contains {start_time_nulls} null start_time values."
        )

    if ends_before_start > 0:
        raise ValueError(
            f"Silver contains {ends_before_start} encounters "
            f"that end before they start."
        )

    print("\nSilver validation passed.")


def upload_silver(df: pl.DataFrame) -> None:
    """
    Write the Silver DataFrame as Parquet and upload it to GCS.
    """

    bucket = get_bucket()
    blob = bucket.blob(SILVER_OBJECT)

    # Write Parquet into memory, then upload the bytes.
    buffer = io.BytesIO()
    df.write_parquet(buffer)
    buffer.seek(0)

    blob.upload_from_file(
        buffer,
        content_type="application/octet-stream",
    )

    print(
        f"\nUploaded {df.height:,} rows to "
        f"gs://{bucket.name}/{SILVER_OBJECT}"
    )


if __name__ == "__main__":

    print("Building Silver DataFrame...")

    df = build_encounters_dataframe()

    print(
        f"Built Silver DataFrame with "
        f"{df.height:,} rows and {df.width} columns."
    )

    # Validate BEFORE uploading.
    validate_silver(df)

    print("\nUploading Silver DataFrame to GCS...")

    upload_silver(df)