"""
Run the contract detector on live Observation rows from Kafka.

Same check() as scripts/check_contract_gcs.py. Only two things change:
  - source: Kafka (consume_observations) instead of GCS
  - window: every N seconds instead of every N rows

Usage:
    python -m poetry run python scripts/check_contract_stream.py        (60-second windows)
    python -m poetry run python scripts/check_contract_stream.py 30     (30-second windows)
"""

import sys

from sentinel.detection.contract import check, to_incident
from sentinel.streaming.consumer import consume_observations
from sentinel.streaming.windows import tumbling_windows


def main():
    args = [a for a in sys.argv[1:] if a != "--save"]
    seconds = int(args[0]) if args else 60
    save = "--save" in sys.argv
    if save:
        from sentinel.storage.posgres import save_incident
    print(f"Contract check on Kafka stream, {seconds}-second windows\n")

    for w in tumbling_windows(consume_observations(), window_seconds=seconds):
        rows = w.rows
        window = {"resource_type": "Observation", "window_start": w.window_start.isoformat(), "window_end": w.window_end.isoformat()}
        stamp = window["window_start"][11:19]
        anomalies = [r for r in check(rows, window) if r["is_anomaly"]]

        if not anomalies:
            print(f"[{stamp}] {len(rows):>6} rows  contract_ok")
            continue

        for r in anomalies:
            if save:
                save_incident(**to_incident(r))
            print(f"[{stamp}] {len(rows):>6} rows  "
                  f"{str(r['field_name']):<18} {r['incident_type']:<24} "
                  f"got={r['current_value']}  bad_rows={r['evidence']['bad_rows']}")


if __name__ == "__main__":
    main()
