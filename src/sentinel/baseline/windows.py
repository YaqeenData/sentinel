import polars as pl


def create_signal_windows(
    df: pl.DataFrame,
    code: str,
    window_size: int = 20,
) -> list[pl.DataFrame]:
    """
    Filter Silver observations to one signal and split them
    into fixed-size historical windows.

    Incomplete final windows are excluded.
    """

    signal_df = (
        df
        .filter(pl.col("code") == code)
        .sort("event_time")
    )

    full_window_count = signal_df.height // window_size

    windows = []

    for window_id in range(full_window_count):
        offset = window_id * window_size

        window = signal_df.slice(
            offset,
            window_size,
        )

        windows.append(window)

    return windows