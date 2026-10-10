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
    "sentinel-consumer",
)


def create_consumer() -> Consumer:
    """
    Create the Sentinel Kafka consumer.
    """

    return Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": KAFKA_CONSUMER_GROUP,
            "auto.offset.reset": "earliest",
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
    rows. For example, one blood-pressure panel produces
    systolic and diastolic rows.

    Parameters
    ----------
    limit:
        Optional number of Kafka messages to consume.
        None means consume continuously.
    """

    consumer = create_consumer()

    consumer.subscribe(
        [KAFKA_TOPIC]
    )

    consumed_messages = 0

    print(
        f"Listening to Kafka topic: {KAFKA_TOPIC}"
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
                    message.value().decode("utf-8")
                )

            except (
                json.JSONDecodeError,
                UnicodeDecodeError,
            ) as exc:

                print(
                    f"Skipping invalid Kafka message: "
                    f"{exc}"
                )

                continue

            if (
                observation.get("resourceType")
                != "Observation"
            ):
                continue

            normalized_rows = (
                normalize_observation(
                    observation
                )
            )

            for row in normalized_rows:
                yield row

            consumed_messages += 1

    except KeyboardInterrupt:
        print("\nConsumer stopped.")

    finally:
        consumer.close()


if __name__ == "__main__":

    print(
        "\nStarting Sentinel Kafka consumer..."
    )

    row_count = 0

    try:

        for row in consume_observations():

            row_count += 1

            value = (
                row.get("numeric_value")
                if row.get("numeric_value") is not None
                else row.get("categorical_display")
                if row.get("categorical_display") is not None
                else row.get("string_value")
            )

            print(
                f"{row_count:>5} | "
                f"{row['code']} | "
                f"{row['display']} | "
                f"{row['value_type']} | "
                f"{value}"
            )

    finally:
        print(
            f"\nNormalized rows received: "
            f"{row_count:,}"
        )