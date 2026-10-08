"""
Run the contract detector on historical Observation data from GCS (Bronze).

Purpose: prove the contract gives NO violations on clean historical data.
If clean data fails, the rule is wrong, not the data.

Reads gs://<GCS_BUCKET>/bronze/synthea/run_id=001/Observation.ndjson
using sentinel.ingestion.gcs, so nothing is downloaded to disk.

Needs in .env: GCP_PROJECT_ID and GCS_BUCKET
Needs once:    gcloud auth application-default login

Usage:
    python -m poetry run python scripts/check_contract_gcs.py
    python -m poetry run python scripts/check_contract_gcs.py 1000
        (argument = rows per window, default 500)
"""

import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv()  # gcs.py reads GCP_PROJECT_ID / GCS_BUCKET from the environment

from sentinel.detection.contract import check  # noqa: E402
from sentinel.ingestion.gcs import read_ndjson  # noqa: E402
from sentinel.transformation.observations import normalize_observation  # noqa: E402


def read_rows():
    """Stream raw FHIR Observations from GCS and yield normalized rows."""
    for observation in read_ndjson("Observation"):
        yield from normalize_observation(observation)


def main():
    window_size = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    total_rows = 0
    windows = 0
    bad_windows = 0
    violations = Counter()   # (field, incident_type, observed) -> bad rows

    def run_window(rows):
        nonlocal windows, bad_windows
        windows += 1
        window = {"resource_type": "Observation", "window_start": f"window-{windows}", "window_end": None}
        anomalies = [r for r in check(rows, window) if r["is_anomaly"]]
        if anomalies:
            bad_windows += 1
        for r in anomalies:
            key = (r["field_name"], r["incident_type"], r["current_value"])
            violations[key] += r["evidence"]["bad_rows"]

    print("Reading Observation.ndjson from GCS Bronze...")

    batch = []
    for row in read_rows():
        total_rows += 1
        batch.append(row)
        if len(batch) == window_size:
            run_window(batch)
            batch = []

    if batch:
        run_window(batch)

    print(f"\nRows checked:        {total_rows}")
    print(f"Windows:             {windows} (of {window_size} rows)")
    print(f"Windows with issues: {bad_windows}")

    if not violations:
        print("\nNo contract violations. The contract fits the clean data.")
        return

    print("\nViolations found (fix the RULE if this is clean data):\n")
    print(f"{'FIELD':<20} {'PROBLEM':<25} {'GOT':<15} {'BAD ROWS':>9}")
    print("-" * 72)
    for (field, problem, got), count in violations.most_common():
        print(f"{str(field):<20} {problem:<25} {str(got):<15} {count:>9}")


if __name__ == "__main__":
    main()
