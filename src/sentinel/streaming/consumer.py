import json
import os
import time
from collections.abc import Generator
from datetime import datetime, timezone

from confluent_kafka import TIMESTAMP_NOT_AVAILABLE, Consumer, KafkaError
from dotenv import load_dotenv

from sentinel.streaming.windows import EVENT_TIME_FIELD
from sentinel.transformation.encounters import (
    normalize_encounter,
)
from sentinel.transformation.observations import (
    normalize_observation,
)
from sentinel.transformation.patients import (
    normalize_patient,
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

# Every normalized row carries its FHIR resource type here,
# so the monitor can send each row to the right detectors.
RESOURCE_TYPE_FIELD = "resource_type"

NORMALIZERS = {
    "Observation": normalize_observation,
    "Patient": normalize_patient,
    "Encounter": normalize_encounter,
}

# Seconds to wait before polling again when the topic does not exist
# yet (for example a fresh Kafka before the replay sends anything).
MISSING_TOPIC_RETRY_SECONDS = 5


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


def message_event_time(message) -> datetime | None:
    """
    Return the time the message was sent to Kafka (UTC),
    or None if Kafka did not provide a timestamp.
    """

    timestamp_type, timestamp_ms = message.timestamp()

    if timestamp_type == TIMESTAMP_NOT_AVAILABLE:
        return None

    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    )


def consume_observations(
    limit: int | None = None,
) -> Generator[dict, None, None]:
    """
    Consume raw FHIR Observations, Patients and Encounters from Kafka,
    normalize them, and yield normalized rows.

    One FHIR Observation may produce multiple normalized
    rows. For example, one blood-pressure panel can produce
    systolic and diastolic rows. One Patient produces one row.

    Each row carries:
      - RESOURCE_TYPE_FIELD: "Observation", "Patient" or "Encounter"
      - EVENT_TIME_FIELD: the Kafka send time, so windows
        are built by event time, not arrival time.

    If the topic does not exist yet, the consumer waits for
    it instead of stopping.

    Parameters
    ----------
    limit:
        Optional number of Kafka messages to consume.
        None means consume continuously.

    Yields
    ------
    dict
        One normalized Sentinel row.
    """

    consumer = create_consumer()

    consumer.subscribe(
        [KAFKA_TOPIC]
    )

    consumed_messages = 0
    waiting_for_topic = False

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

                code = message.error().code()

                if code == KafkaError._PARTITION_EOF:
                    continue

                # Topic not created yet: wait, do not stop.
                if code == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    if not waiting_for_topic:
                        print(
                            f"Waiting for topic {KAFKA_TOPIC} "
                            "(start the replay if it is not running)..."
                        )
                        waiting_for_topic = True

                    time.sleep(
                        MISSING_TOPIC_RETRY_SECONDS
                    )
                    continue

                raise RuntimeError(
                    f"Kafka consumer error: "
                    f"{message.error()}"
                )

            if waiting_for_topic:
                print(f"Topic {KAFKA_TOPIC} is available.")
                waiting_for_topic = False

            try:
                resource = json.loads(
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

            resource_type = resource.get(
                "resourceType"
            )

            normalize = NORMALIZERS.get(
                resource_type
            )

            if normalize is None:
                continue

            try:
                normalized_rows = normalize(
                    resource
                )

            except Exception as exc:
                print(
                    f"Skipping {resource_type} that "
                    "could not be normalized: "
                    f"{exc}"
                )

                continue

            # A normalizer may return one row (dict) or many (list).
            if isinstance(normalized_rows, dict):
                normalized_rows = [normalized_rows]

            consumed_messages += 1

            event_time = message_event_time(message)

            for row in normalized_rows:
                row[RESOURCE_TYPE_FIELD] = resource_type

                if event_time is not None:
                    row[EVENT_TIME_FIELD] = event_time

                yield row

    finally:
        consumer.close()