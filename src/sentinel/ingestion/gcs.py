import json
import os
from collections.abc import Iterator

from google.cloud import storage


BRONZE_PREFIX = "bronze/synthea/run_id=001"


def get_bucket():
    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET"]

    client = storage.Client(project=project_id)
    return client.bucket(bucket_name)


def list_bronze_objects():
    bucket = get_bucket()

    blobs = bucket.list_blobs(prefix=f"{BRONZE_PREFIX}/")

    return [blob.name for blob in blobs]


def read_ndjson(resource_name: str) -> Iterator[dict]:
    """Yield FHIR resources from a Bronze NDJSON object."""

    bucket = get_bucket()
    blob = bucket.blob(
        f"{BRONZE_PREFIX}/{resource_name}.ndjson"
    )

    with blob.open("r") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)
                
if __name__ == "__main__":
    observations = read_ndjson("Observation")

    for _ in range(5):
        observation = next(observations)

        print(
            observation["resourceType"],
            observation["id"],
            observation.get("code", {}).get("text")
        )