"""
Run the contract detector on a local Observation NDJSON file.

Purpose: prove the contract gives NO violations on clean historical data.
If clean data fails, the rule is wrong, not the data.

Usage:
    python -m poetry run python scripts/check_contract_on_file.py Observation.ndjson
    python -m poetry run python scripts/check_contract_on_file.py Observation.ndjson 1000
        (second argument = rows per window, default 500)
"""

import json
import sys
from collections import Counter

from sentinel.detection.contract import check
from sentinel.transformation.observations import normalize_observation


def read_rows(file_path: str):
    """Read raw FHIR Observations and yield normalized rows."""
    with open(file_path, encoding="utf-8") as file:
        for line in file:
            if line.strip():
                yield from normalize_observation(json.loads(line))


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_contract_on_file.py <Observation.ndjson> [rows_per_window]")
        sys.exit(1)

    file_path = sys.argv[1]
    window_size = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    total_rows = 0
    windows = 0
    bad_windows = 0
    violations = Counter()   # (field, incident_type, observed) -> bad rows

    batch = []

    def run_window(rows):
        nonlocal windows, bad_windows
        windows += 1
        window = {"resource_type": "Observation", "window_start": f"window-{windows}", "window_end": None}
        results = check(rows, window)
        anomalies = [r for r in results if r["is_anomaly"]]
        if anomalies:
            bad_windows += 1
        for r in anomalies:
            key = (r["field_name"], r["incident_type"], r["current_value"])
            violations[key] += r["evidence"]["bad_rows"]

    for row in read_rows(file_path):
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