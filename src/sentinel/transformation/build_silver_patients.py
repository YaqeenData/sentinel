import io

import polars as pl

from sentinel.ingestion.gcs import get_bucket, read_ndjson
from sentinel.transformation.patients import normalize_patient


SILVER_OBJECT = (
    "silver/patients/run_id=001/patients.parquet"
)

# Every column starts as text, then we convert the ones that need it.
# Declaring the schema explicitly means Polars never has to guess a
# column type from the first rows (important for columns that are
# mostly empty, such as deceased_time).
RAW_SCHEMA = {
    "patient_id": pl.String,
    "gender": pl.String,
    "birth_date": pl.String,
    "deceased_time": pl.String,
    "marital_status_code": pl.String,
    "marital_status_display": pl.String,
    "city": pl.String,
    "state": pl.String,
    "postal_code": pl.String,
    "country": pl.String,
    "language_code": pl.String,
    "language_display": pl.String,
}


def build_patients_dataframe() -> pl.DataFrame:
    """
    Read raw FHIR Patients from Bronze and transform them
    into the normalized Silver Patient structure.
    """

    rows = []

    for patient in read_ndjson("Patient"):
        rows.extend(normalize_patient(patient))

    df = pl.DataFrame(rows, schema=RAW_SCHEMA)

    df = df.with_columns(
        # birthDate is a plain date such as 1987-04-12 (no time).
        pl.col("birth_date").str.to_date(
            format="%Y-%m-%d",
            strict=True,
        ),

        # deceasedDateTime is a full timestamp with an offset.
        # It is null for living patients, which is expected.
        pl.col("deceased_time").str.to_datetime(
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
        pl.col("patient_id").n_unique().alias("unique_patients"),
        pl.col("patient_id").null_count().alias("patient_id_nulls"),
        pl.col("birth_date").null_count().alias("birth_date_nulls"),
        pl.col("deceased_time").is_not_null().sum().alias("deceased"),
        pl.col("birth_date").min().alias("earliest_birth"),
        pl.col("birth_date").max().alias("latest_birth"),
    )

    print(summary)

    print("\n=== GENDER VALUES ===")
    print(df["gender"].value_counts())

    print("\n=== SILVER SCHEMA ===")
    print(df.schema)

    if df.height == 0:
        raise ValueError("Silver contains no patients.")

    patient_id_nulls = df["patient_id"].null_count()
    birth_date_nulls = df["birth_date"].null_count()
    duplicates = df.height - df["patient_id"].n_unique()

    if patient_id_nulls > 0:
        raise ValueError(
            f"Silver contains {patient_id_nulls} null patient_id values."
        )

    # patient_id is the primary key: one row per patient.
    if duplicates > 0:
        raise ValueError(
            f"Silver contains {duplicates} duplicate patient_id values."
        )

    if birth_date_nulls > 0:
        raise ValueError(
            f"Silver contains {birth_date_nulls} null birth_date values."
        )

    print("\nSilver validation passed.")


def upload_silver(df: pl.DataFrame) -> None:
    """
    Write the Silver DataFrame as Parquet and upload it to GCS.
    """

    bucket = get_bucket()
    blob = bucket.blob(SILVER_OBJECT)

   
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

    df = build_patients_dataframe()

    print(
        f"Built Silver DataFrame with "
        f"{df.height:,} rows and {df.width} columns."
    )

    
    validate_silver(df)

    print("\nUploading Silver DataFrame to GCS...")

    upload_silver(df)