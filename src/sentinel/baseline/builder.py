"""
Build detector baselines from historical Silver data.

Silver is the reference of healthy data (see the architecture diagram):
the live monitor compares every window with it instead of learning
"normal" from the first minutes of the stream.

Run once (and again whenever Silver changes):

    PYTHONPATH=src python -m sentinel.baseline.builder

Writes config/baselines.json, which scripts/run_monitor.py reads.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import polars as pl
import yaml
from dotenv import load_dotenv

from sentinel.baseline.methods import (
    class_proportions,
    null_rate_history,
    patient_medians,
)


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SILVER_DIR = PROJECT_ROOT / "data" / "silver"

SILVER_OBSERVATIONS = "silver/observations/run_id=001/observations.parquet"
SILVER_ENCOUNTERS = "silver/encounters/run_id=001/encounters.parquet"

CONFIG_PATH = PROJECT_ROOT / "config" / "monitoring.yaml"
BASELINES_PATH = PROJECT_ROOT / "config" / "baselines.json"

# Readings per historical window for the missingness baseline.
# Roughly the number of rows one monitored code gets in a live minute.
MISSINGNESS_WINDOW_SIZE = 100

# Encounter class drift: one row per Encounter, class in class_code.
ENCOUNTER_ID_COLUMN = "encounter_id"
ENCOUNTER_CLASS_COLUMN = "class_code"


def numeric_codes() -> dict[str, str]:
    """{code: display} of the monitored numeric codes, from monitoring.yaml."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    observations = (
        (config.get("numeric_drift") or {}).get("observations") or []
    )

    return {
        str(item["code"]): item.get("display", str(item["code"]))
        for item in observations
    }


def download_silver(
    silver_object: str,
    force: bool = False,
) -> Path:
    """
    Download one Silver parquet from GCS once and keep a local copy
    in data/silver/ (e.g. data/silver/observations.parquet).

    The monitor never talks to GCS: only this builder does.
    """

    local = SILVER_DIR / Path(silver_object).name

    if local.exists() and not force:
        return local

    from google.cloud import storage

    bucket_name = os.environ["GCS_BUCKET"]

    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    storage.Client().bucket(bucket_name).blob(
        silver_object
    ).download_to_filename(str(local))

    print(f"Downloaded gs://{bucket_name}/{silver_object}")

    return local


def build_baselines(
    observations: pl.DataFrame,
    encounters: pl.DataFrame,
    codes: dict[str, str],
) -> dict:
    """Compute every baseline the live detectors need."""

    numeric = {}

    for code, display in codes.items():
        values = patient_medians(observations, code)

        numeric[code] = {
            "display": display,
            "patients": len(values),
            "median": round(median(values), 4) if values else None,
            "patient_medians": [round(v, 4) for v in values],
        }

    null_rates = null_rate_history(
        observations,
        list(codes),
        MISSINGNESS_WINDOW_SIZE,
    )

    proportions = class_proportions(
        encounters,
        ENCOUNTER_ID_COLUMN,
        ENCOUNTER_CLASS_COLUMN,
    )

    return {
        "source": "silver/*/run_id=001",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "numeric": numeric,
        "missingness": {
            "window_size": MISSINGNESS_WINDOW_SIZE,
            "windows": len(null_rates),
            "null_rates": [round(v, 4) for v in null_rates],
        },
        "encounter_class": {
            "field": ENCOUNTER_CLASS_COLUMN,
            "encounters": encounters[ENCOUNTER_ID_COLUMN].n_unique(),
            "proportions": {k: round(v, 6) for k, v in proportions.items()},
        },
    }


def save_baselines(
    baselines: dict,
    path: Path = BASELINES_PATH,
) -> None:
    path.write_text(
        json.dumps(baselines, indent=2),
        encoding="utf-8",
    )


def load_baselines(
    path: Path = BASELINES_PATH,
) -> dict | None:
    """
    Read config/baselines.json.

    Returns None when the file does not exist, so the monitor can
    fall back to learning the baseline from the stream.
    """

    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    codes = numeric_codes()

    observations = pl.read_parquet(download_silver(SILVER_OBSERVATIONS))
    encounters = pl.read_parquet(download_silver(SILVER_ENCOUNTERS))

    baselines = build_baselines(observations, encounters, codes)

    save_baselines(baselines)

    print(f"Saved {BASELINES_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Source: {baselines['source']}")
    print(f"  observations: {observations.height:,} rows")
    print(f"  encounters:   {encounters.height:,} rows")

    print("\nNumeric drift reference (one median per patient):")
    for code, item in baselines["numeric"].items():
        print(
            f"  {item['display']:<26} {code:<8} "
            f"patients={item['patients']:<4} median={item['median']}"
        )

    missingness = baselines["missingness"]
    rates = missingness["null_rates"]
    print(
        f"\nMissingness history: {missingness['windows']} windows "
        f"of {missingness['window_size']} readings, "
        f"null rate {min(rates):.3f} to {max(rates):.3f}"
    )

    encounter = baselines["encounter_class"]
    print(f"\nEncounter class baseline ({encounter['encounters']:,} encounters):")
    for value, share in encounter["proportions"].items():
        print(f"  {value:<6} {share:.2%}")


if __name__ == "__main__":
    main()