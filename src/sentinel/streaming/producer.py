import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from confluent_kafka import Producer
from dotenv import load_dotenv


load_dotenv()


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

KAFKA_TOPIC = os.getenv(
    "KAFKA_TOPIC",
    "fhir-observations",
)


def create_producer() -> Producer:
    """
    Create a Kafka producer.
    """

    return Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        }
    )


def delivery_report(err, msg) -> None:
    """
    Kafka delivery callback.
    """

    if err is not None:
        print(f"\nDelivery failed: {err}")


def reference_id(
    reference: str | None,
) -> str | None:
    """
    Id from a FHIR reference.

    Handles both "Patient/<id>" and "urn:uuid:<id>".
    """

    if not reference:
        return None

    return (
        reference
        .rsplit("/", 1)[-1]
        .removeprefix("urn:uuid:")
    )


def patient_id_of(
    resource: dict[str, Any],
) -> str | None:
    """Patient id from a FHIR resource's subject reference."""

    return reference_id(
        (resource.get("subject") or {}).get("reference")
    )


def _publish(
    producer: Producer,
    key: str,
    resource: dict[str, Any],
) -> None:
    """
    Send one FHIR resource to Kafka.

    If the local producer queue fills up,
    wait until Kafka accepts more messages.
    """

    while True:
        try:
            producer.produce(
                topic=KAFKA_TOPIC,
                key=key.encode("utf-8"),
                value=json.dumps(
                    resource
                ).encode("utf-8"),
                callback=delivery_report,
            )

            break

        except BufferError:
            producer.poll(1)

    producer.poll(0)


def replay_observations(
    file_path: str | Path,
    rate: float = 5.0,
    limit: int | None = None,
    transform: Callable[
        [dict[str, Any]],
        dict[str, Any] | None,
    ]
    | None = None,
    patients: dict[str, dict[str, Any]] | None = None,
    patient_transform: Callable[
        [dict[str, Any]],
        dict[str, Any],
    ]
    | None = None,
    encounters_by_patient: dict[str, list[dict[str, Any]]] | None = None,
    encounter_transform: Callable[
        [dict[str, Any]],
        dict[str, Any],
    ]
    | None = None,
) -> int:
    """
    Replay raw Synthea FHIR Observation resources into Kafka.

    Parameters
    ----------
    file_path:
        Path to Synthea Observation.ndjson.

    rate:
        Number of FHIR Observation resources to publish
        per second.

    limit:
        Optional maximum number of observations to publish.
        None means publish the entire file.

    transform:
        Optional function applied to each FHIR Observation
        immediately before it is published to Kafka.

        This can be used by the live-data simulator for
        controlled failure injection while keeping the
        producer itself independent of any specific
        injection strategy.

        Returning None means "do not send this Observation"
        (used to simulate a volume drop).

    patients:
        Optional {patient_id: raw FHIR Patient} for the batch.

    patient_transform:
        Optional function applied to each Patient before it is
        published (used for patient contract injection).

    encounters_by_patient:
        Optional {patient_id: [raw FHIR Encounters]} for the batch.

    encounter_transform:
        Optional function applied to each Encounter before it is
        published (used for Encounter class injection).

    The first time a patient appears in the Observation file, the
    producer sends that Patient, then ALL of the patient's Encounters,
    then the Observation: the way a real system registers a patient
    and their visits before recording measurements. Sending every
    Encounter (not only those that have Observations) keeps the class
    mix the same as the source data.

    Returns
    -------
    int
        Number of Observation messages published.
    """

    if rate <= 0:
        raise ValueError(
            "Replay rate must be greater than 0."
        )

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Observation file not found: {path}"
        )

    producer = create_producer()

    delay = 1 / rate
    sent = 0
    dropped = 0
    patients_sent = 0
    encounters_sent = 0
    seen_patient_ids: set[str] = set()

    send_patient_data = (
        patients is not None
        or encounters_by_patient is not None
    )

    print("\nStarting replay")
    print(f"Source: {path}")
    print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Rate: {rate} observations/second")

    if transform is not None:
        print(
            "Transform: enabled"
        )

    if patients is not None:
        print(
            f"Patients: {len(patients):,} "
            "(each sent before its first Observation)"
        )

    if encounters_by_patient is not None:
        total_encounters = sum(
            len(items) for items in encounters_by_patient.values()
        )
        print(
            f"Encounters: {total_encounters:,} "
            "(all of a patient's Encounters, right after the Patient)"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            if (
                limit is not None
                and sent >= limit
            ):
                break

            line = line.strip()

            if not line:
                continue

            observation = json.loads(
                line
            )

            if (
                observation.get(
                    "resourceType"
                )
                != "Observation"
            ):
                continue

            # First time this patient appears: send the Patient,
            # then all of their Encounters. This happens before the
            # Observation transform, so a volume drop never hides
            # Patients or Encounters.
            if send_patient_data:
                patient_id = patient_id_of(
                    observation
                )

                if (
                    patient_id
                    and patient_id not in seen_patient_ids
                ):
                    seen_patient_ids.add(patient_id)

                    patient = (patients or {}).get(patient_id)

                    if patient is not None:
                        if patient_transform is not None:
                            patient = patient_transform(
                                patient
                            )

                        # Key by the original id, so even a Patient
                        # whose id was removed by injection is sent.
                        _publish(
                            producer,
                            patient_id,
                            patient,
                        )

                        patients_sent += 1

                    for encounter in (
                        (encounters_by_patient or {}).get(patient_id, [])
                    ):
                        encounter_id = encounter.get("id") or patient_id

                        if encounter_transform is not None:
                            encounter = encounter_transform(
                                encounter
                            )

                        _publish(
                            producer,
                            encounter_id,
                            encounter,
                        )

                        encounters_sent += 1

            # Optional upstream transformation.
            #
            # Sentinel's live simulator can use
            # this hook for controlled failure
            # injection before the resource enters
            # Kafka.
            #
            # The downstream detector remains
            # completely unaware of the injection.
            if transform is not None:
                observation = transform(
                    observation
                )

            # The transform dropped this Observation
            # (volume drop injection). Keep the replay
            # pace so the drop shows as fewer records
            # per window, not a faster stream.
            if observation is None:
                dropped += 1

                time.sleep(
                    delay
                )
                continue

            observation_id = (
                observation.get("id")
            )

            if not observation_id:
                print(
                    "\nSkipping Observation "
                    "without an id."
                )
                continue

            _publish(
                producer,
                observation_id,
                observation,
            )

            sent += 1

            print(
                f"\rPublished: {sent:,} | Dropped: {dropped:,}"
                f" | Patients: {patients_sent:,}"
                f" | Encounters: {encounters_sent:,}",
                end="",
                flush=True,
            )

            time.sleep(
                delay
            )

    remaining = producer.flush()

    if remaining:
        raise RuntimeError(
            f"{remaining} Kafka messages "
            "were not delivered."
        )

    print(
        f"\nFinished batch. "
        f"Published {sent:,} observations"
        f" (dropped {dropped:,}),"
        f" {patients_sent:,} patients"
        f" and {encounters_sent:,} encounters."
    )

    return sent