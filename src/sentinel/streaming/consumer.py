import json
import os
from collections.abc import Generator

from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv

from sentinel.transformation.observations import (
    normalize_observation,
)


load_dotenv()


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

KAFKA_TOPIC = os.getenv(
    "KAFKA_TOPIC",
    "fhir-observations",
)

KAFKA_CONSUMER_GROUP = os.getenv(
    "KAFKA_CONSUMER_GROUP",
    "sentinel-live-monitor",
)

KAFKA_AUTO_OFFSET_RESET = os.getenv(
    "KAFKA_AUTO_OFFSET_RESET",
    "latest",
)


def create_consumer() -> Consumer:
    """
    Create the Sentinel Kafka consumer.

    Offset behavior is configurable through the environment.

    For the live Sentinel monitor, use:
        KAFKA_AUTO_OFFSET_RESET=latest

    so a new consumer group starts from fresh messages
    instead of replaying the entire Kafka backlog.
    """

    return Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": KAFKA_CONSUMER_GROUP,
            "auto.offset.reset": KAFKA_AUTO_OFFSET_RESET,
            "enable.auto.commit": True,
        }
    )


def consume_observations(
    limit: int | None = None,
) -> Generator[dict, None, None]:
    """
    Consume raw FHIR Observations from Kafka,
    normalize them, and yield normalized rows.

    One FHIR Observation may produce multiple normalized
    rows. For example, one blood-pressure panel can produce
    systolic and diastolic rows.

    Parameters
    ----------
    limit:
        Optional number of Kafka messages to consume.
        None means consume continuously.

    Yields
    ------
    dict
        One normalized Sentinel Observation row.
    """

    consumer = create_consumer()

    consumer.subscribe(
        [KAFKA_TOPIC]
    )

    consumed_messages = 0

    print(
        f"Listening to Kafka topic: {KAFKA_TOPIC}"
    )
    print(
        f"Consumer group: {KAFKA_CONSUMER_GROUP}"
    )
    print(
        f"Offset reset: {KAFKA_AUTO_OFFSET_RESET}"
    )

    try:

        while (
            limit is None
            or consumed_messages < limit
        ):

            message = consumer.poll(
                timeout=1.0
            )

            if message is None:
                continue

            if message.error():

                if (
                    message.error().code()
                    == KafkaError._PARTITION_EOF
                ):
                    continue

                raise RuntimeError(
                    f"Kafka consumer error: "
                    f"{message.error()}"
                )

            try:
                observation = json.loads(
                    message.value().decode(
                        "utf-8"
                    )
                )

            except (
                json.JSONDecodeError,
                UnicodeDecodeError,
            ) as exc:

                print(
                    "Skipping invalid Kafka message: "
                    f"{exc}"
                )

                continue

            if (
                observation.get(
                    "resourceType"
                )
                != "Observation"
            ):
                continue

            try:
                normalized_rows = (
                    normalize_observation(
                        observation
                    )
                )

            except Exception as exc:
                print(
                    "Skipping Observation that "
                    "could not be normalized: "
                    f"{exc}"
                )

                continue

            consumed_messages += 1

            for row in normalized_rows:
                yield row

    finally:
        consumer.close()