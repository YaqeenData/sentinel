import polars as pl


def profile_numeric_window(df: pl.DataFrame) -> dict:
    """
    Calculate data-health metrics for one numeric signal window.

    Expected column:
        numeric_value

    Returns metrics only.
    No anomaly detection happens here.
    """

    if df.is_empty():
        raise ValueError("Cannot profile an empty window.")

    metrics = df.select(
        pl.len().alias("record_count"),

        pl.col("numeric_value")
        .null_count()
        .alias("null_count"),

        pl.col("numeric_value")
        .null_count()
        .truediv(pl.len())
        .alias("null_rate"),

        pl.col("numeric_value")
        .mean()
        .alias("mean"),

        pl.col("numeric_value")
        .std()
        .alias("std"),

        pl.col("numeric_value")
        .median()
        .alias("median"),

        pl.col("numeric_value")
        .quantile(0.25)
        .alias("p25"),

        pl.col("numeric_value")
        .quantile(0.75)
        .alias("p75"),
    )

    return metrics.row(0, named=True)