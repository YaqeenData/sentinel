import os
import random
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv

from sentinel.injection.control import (
    is_injection_enabled,
)
from sentinel.injection.fhir_categorical import (
    inject_fhir_categorical_observation,
)
from sentinel.streaming.producer import (
    replay_observations,
)


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[3]

REPLAY_ROOT = (
    PROJECT_ROOT
    / "data"
    / "replay"
)

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "monitoring.yaml"
)

SYNTHEA_JAR = os.getenv(
    "SYNTHEA_JAR"
)

REPLAY_RATE = float(
    os.getenv(
        "REPLAY_RATE",
        "50.0",
    )
)

SYNTHEA_POPULATION = int(
    os.getenv(
        "SYNTHEA_POPULATION",
        "200",
    )
)


def load_categorical_config() -> dict[str, Any]:
    """
    Load categorical-drift configuration.
    """

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    return config["categorical_drift"]


def validate_environment() -> Path:
    """
    Validate the local Synthea setup.
    """

    if not SYNTHEA_JAR:
        raise ValueError(
            "SYNTHEA_JAR is not configured. "
            "Add it to your .env file."
        )

    jar_path = Path(
        SYNTHEA_JAR
    ).expanduser()

    if not jar_path.exists():
        raise FileNotFoundError(
            f"Synthea JAR not found: "
            f"{jar_path}"
        )

    if REPLAY_RATE <= 0:
        raise ValueError(
            "REPLAY_RATE must be greater than 0."
        )

    if SYNTHEA_POPULATION <= 0:
        raise ValueError(
            "SYNTHEA_POPULATION must be "
            "greater than 0."
        )

    return jar_path


def generate_synthea_batch(
    jar_path: Path,
    run_id: str,
) -> Path:
    """
    Generate a fresh Synthea bulk-FHIR dataset.

    Returns
    -------
    Path
        Path to the generated Observation.ndjson.
    """

    output_dir = (
        REPLAY_ROOT
        / f"run_id={run_id}"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    print("\n" + "=" * 60)
    print("Generating fresh Synthea batch")
    print("=" * 60)
    print(f"Run ID: {run_id}")
    print(
        f"Population: "
        f"{SYNTHEA_POPULATION}"
    )
    print(f"Output: {output_dir}")

    command = [
        "java",
        "-jar",
        str(jar_path),

        "-p",
        str(SYNTHEA_POPULATION),

        (
            "--exporter.baseDirectory="
            f"{output_dir}"
        ),

        "--exporter.fhir.export=true",

        "--exporter.fhir.bulk_data=true",

        (
            "--exporter.fhir."
            "transaction_bundle=false"
        ),
    ]

    subprocess.run(
        command,
        check=True,
    )

    observation_file = (
        output_dir
        / "fhir"
        / "Observation.ndjson"
    )

    if not observation_file.exists():
        raise FileNotFoundError(
            "Synthea generation completed, "
            "but Observation.ndjson was not found "
            f"at: {observation_file}"
        )

    return observation_file


def cleanup_batch(
    observation_file: Path,
) -> None:
    """
    Remove a temporary replay batch after Kafka
    has successfully received it.

    This never touches the historical dataset in GCS.
    """

    run_directory = (
        observation_file
        .parents[1]
    )

    if run_directory.exists():

        shutil.rmtree(
            run_directory
        )

        print(
            f"Removed temporary batch: "
            f"{run_directory.name}"
        )


def build_live_transform(
    config: dict[str, Any],
) -> Callable[
    [dict[str, Any]],
    dict[str, Any],
]:
    """
    Build the live controlled-failure transform.

    Injection state is checked for every Observation,
    so it can be switched on or off while the producer
    is already running.
    """

    observation_code = (
        config["observation"]["code"]
    )

    source_category = (
        config["injection"]
        ["source_category"]
        ["code"]
    )

    target_category = (
        config["injection"]
        ["target_category"]
        ["code"]
    )

    target_display = (
        config["injection"]
        ["target_category"]
        ["display"]
    )

    fraction = float(
        config["injection"]["fraction"]
    )

    seed = int(
        config["injection"]["seed"]
    )

    if not 0 <= fraction <= 1:
        raise ValueError(
            "Injection fraction must be "
            "between 0 and 1."
        )

    rng = random.Random(seed)

    last_state: bool | None = None

    def transform(
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal last_state

        enabled = is_injection_enabled()

        if enabled != last_state:
            print()

            print(
                "Controlled categorical injection: "
                + (
                    "ON"
                    if enabled
                    else "OFF"
                )
            )

            if enabled:
                print(
                    f"Injecting approximately "
                    f"{fraction:.0%} of eligible "
                    f"{source_category} → "
                    f"{target_category}"
                )

            last_state = enabled

        if not enabled:
            return observation

        # Each eligible Observation has the configured
        # probability of being transformed.
        if rng.random() >= fraction:
            return observation

        return inject_fhir_categorical_observation(
            observation,
            observation_code=observation_code,
            source_category=source_category,
            target_category=target_category,
            target_display=target_display,
        )

    return transform


def run_forever() -> None:
    """
    Continuously generate fresh Synthea batches
    and replay their FHIR Observations into Kafka.

    Controlled categorical failure injection can
    be toggled while this process remains running.
    """

    jar_path = validate_environment()

    config = load_categorical_config()

    transform = build_live_transform(
        config
    )

    REPLAY_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("\nSentinel Live Data Simulator")
    print("=" * 60)

    print(
        f"Patients per batch: "
        f"{SYNTHEA_POPULATION}"
    )

    print(
        f"Replay rate: "
        f"{REPLAY_RATE} observations/sec"
    )

    print(
        "Controlled injection: "
        + (
            "ON"
            if is_injection_enabled()
            else "OFF"
        )
    )

    print(
        "Press Ctrl+C to stop."
    )

    batch_number = 1

    try:

        while True:

            timestamp = datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%dT%H%M%SZ"
            )

            run_id = (
                f"{timestamp}"
                f"_batch_{batch_number:04d}"
            )

            observation_file = (
                generate_synthea_batch(
                    jar_path=jar_path,
                    run_id=run_id,
                )
            )

            print(
                "\nReplaying generated "
                "FHIR Observations..."
            )

            replay_observations(
                file_path=observation_file,
                rate=REPLAY_RATE,
                transform=transform,
            )

            cleanup_batch(
                observation_file
            )

            batch_number += 1

    except KeyboardInterrupt:

        print(
            "\n\nSentinel live-data "
            "simulator stopped."
        )


if __name__ == "__main__":
    run_forever()