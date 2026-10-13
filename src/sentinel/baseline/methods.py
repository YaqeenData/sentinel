"""
Baseline calculations from historical Silver data.

Each function turns Silver rows into the reference a live detector needs:
  - patient_medians:   numeric drift (one value per patient, like the monitor)
  - null_rate_history: missingness (null rate of many historical windows)
  - class_proportions: Encounter class drift (share of each class)
"""

import polars as pl

from sentinel.baseline.profiler import profile_numeric_window
from sentinel.baseline.windows import create_signal_windows


def patient_medians(
    df: pl.DataFrame,
    code: str,
) -> list[float]:
    """
    One median per patient for one numeric code.

    The live monitor compares patient medians, not single readings,
    so a patient with many readings cannot outweigh the others.
    """

    return (
        df
        .filter(
            (pl.col("code") == code)
            & pl.col("numeric_value").is_not_null()
        )
        .group_by("patient_id")
        .agg(pl.col("numeric_value").median().alias("patient_median"))
        .sort("patient_id")
        ["patient_median"]
        .to_list()
    )


def null_rate_history(
    df: pl.DataFrame,
    codes: list[str],
    window_size: int,
) -> list[float]:
    """
    Null rate of every full historical window, for every code.

    Uses create_signal_windows and profile_numeric_window, so the
    historical windows are measured the same way as any profiled window.
    """

    rates = []

    for code in codes:
        for window in create_signal_windows(df, code, window_size):
            rates.append(
                float(profile_numeric_window(window)["null_rate"])
            )

    return rates


def class_proportions(
    df: pl.DataFrame,
    id_column: str,
    class_column: str,
) -> dict[str, float]:
    """
    Share of each class over distinct records (e.g. Encounter.class_code).

    Every record counts once, the same way the live monitor counts
    each Encounter once. Records without a class are left out.
    """

    missing = {id_column, class_column} - set(df.columns)
    if missing:
        raise ValueError(
            f"Silver data has no column(s) {sorted(missing)}. "
            f"Columns: {df.columns}"
        )

    counts = (
        df
        .unique(subset=[id_column])
        .filter(pl.col(class_column).is_not_null())
        .group_by(class_column)
        .agg(pl.len().alias("count"))
    )

    total = int(counts["count"].sum())
    if total == 0:
        return {}

    return {
        str(row[class_column]): row["count"] / total
        for row in counts.sort("count", descending=True).iter_rows(named=True)
    }