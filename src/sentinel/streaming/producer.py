import json
import os
import time
from pathlib import Path

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


def replay_observations(
    file_path: str | Path,
    rate: float = 5.0,
    limit: int | None = None,
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

    Returns
    -------
    int
        Number of Kafka messages published.
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

    print("\nStarting replay")
    print(f"Source: {path}")
    print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Rate: {rate} observations/second")

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            if limit is not None and sent >= limit:
                break

            line = line.strip()

            if not line:
                continue

            observation = json.loads(line)

            # The topic is specifically for FHIR Observations.
            if observation.get("resourceType") != "Observation":
                continue

            observation_id = observation.get("id")

            if not observation_id:
                print(
                    "\nSkipping Observation without an id."
                )
                continue

            # If the local producer queue fills up,
            # wait until Kafka accepts more messages.
            while True:
                try:
                    producer.produce(
                        topic=KAFKA_TOPIC,
                        key=observation_id.encode("utf-8"),
                        value=json.dumps(
                            observation
                        ).encode("utf-8"),
                        callback=delivery_report,
                    )

                    break

                except BufferError:
                    producer.poll(1)

            producer.poll(0)

            sent += 1

            print(
                f"\rPublished: {sent:,}",
                end="",
                flush=True,
            )

            time.sleep(delay)

    remaining = producer.flush()

    if remaining:
        raise RuntimeError(
            f"{remaining} Kafka messages were not delivered."
        )

    print(
        f"\nFinished batch. "
        f"Published {sent:,} observations."
    )

    return sent