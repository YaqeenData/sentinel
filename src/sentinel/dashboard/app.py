"""
Sentinel data-health dashboard.

Run:
    python -m poetry run streamlit run src/sentinel/dashboard/app.py
"""

import streamlit as st

from sentinel.dashboard.quries import get_latest_window


st.set_page_config(page_title="Sentinel · Data Health", layout="wide")

st.title("Sentinel · Data Health")
st.caption(
    "This dashboard monitors the health of the FHIR data stream, "
    "not the health of patients."
)

window = get_latest_window()

if window is None:
    st.info("No completed quality window yet. Start the stream and wait one window.")
    st.stop()

if window["is_sample"]:
    st.warning("Showing sample data. PostgreSQL metrics are not connected yet.")

st.subheader("Latest completed window")

col_records, col_nulls, col_time = st.columns(3)

col_records.metric("Records in window", f"{window['record_count']:,}")
col_nulls.metric("Null rate", f"{window['null_rate']:.1%}")
col_time.metric("Data as of", window["window_end"].strftime("%H:%M:%S UTC"))

st.caption(
    f"Window: {window['window_start']:%Y-%m-%d %H:%M:%S} → "
    f"{window['window_end']:%H:%M:%S} UTC"
)