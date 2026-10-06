from sentinel.transformation.observations import normalize_observation


def test_numeric_observation():
    observation = {
        "resourceType": "Observation",
        "id": "obs-1",
        "status": "final",
        "code": {
            "coding": [
                {
                    "code": "8867-4",
                    "display": "Heart rate",
                }
            ]
        },
        "subject": {"reference": "Patient/patient-1"},
        "encounter": {"reference": "Encounter/encounter-1"},
        "effectiveDateTime": "2026-10-06T10:00:00+03:00",
        "valueQuantity": {
            "value": 79,
            "unit": "/min",
            "code": "/min",
        },
    }

    rows = normalize_observation(observation)

    assert len(rows) == 1

    row = rows[0]

    assert row["code"] == "8867-4"
    assert row["value_type"] == "numeric"
    assert row["numeric_value"] == 79
    assert row["unit"] == "/min"
    assert row["patient_id"] == "patient-1"
    assert row["encounter_id"] == "encounter-1"


def test_categorical_observation():
    observation = {
        "resourceType": "Observation",
        "id": "obs-2",
        "status": "final",
        "code": {
            "coding": [
                {
                    "code": "72166-2",
                    "display": "Tobacco smoking status",
                }
            ]
        },
        "valueCodeableConcept": {
            "coding": [
                {
                    "code": "266919005",
                    "display": "Never smoked tobacco (finding)",
                }
            ]
        },
    }

    rows = normalize_observation(observation)

    assert len(rows) == 1

    row = rows[0]

    assert row["value_type"] == "categorical"
    assert row["categorical_code"] == "266919005"
    assert row["categorical_display"] == "Never smoked tobacco (finding)"
    assert row["numeric_value"] is None


def test_component_observation():
    observation = {
        "resourceType": "Observation",
        "id": "obs-3",
        "status": "final",
        "code": {
            "coding": [
                {
                    "code": "85354-9",
                    "display": "Blood pressure panel",
                }
            ]
        },
        "component": [
            {
                "code": {
                    "coding": [
                        {
                            "code": "8462-4",
                            "display": "Diastolic Blood Pressure",
                        }
                    ]
                },
                "valueQuantity": {
                    "value": 78,
                    "code": "mm[Hg]",
                },
            },
            {
                "code": {
                    "coding": [
                        {
                            "code": "8480-6",
                            "display": "Systolic Blood Pressure",
                        }
                    ]
                },
                "valueQuantity": {
                    "value": 128,
                    "code": "mm[Hg]",
                },
            },
        ],
    }

    rows = normalize_observation(observation)

    assert len(rows) == 2

    assert rows[0]["parent_code"] == "85354-9"
    assert rows[0]["code"] == "8462-4"
    assert rows[0]["numeric_value"] == 78

    assert rows[1]["parent_code"] == "85354-9"
    assert rows[1]["code"] == "8480-6"
    assert rows[1]["numeric_value"] == 128