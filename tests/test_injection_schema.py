import pytest

from sentinel.detection.contract import check
from sentinel.injection.schema import SCHEMA_ERROR_KINDS, corrupt, inject_schema_errors
from sentinel.transformation.observations import normalize_observation

WINDOW = {"resource_type": "Observation", "window_start": "2026-10-11T14:00:00", "window_end": "2026-10-11T14:01:00"}


def fhir_observation(obs_id: str = "obs-1") -> dict:
    """A clean, Synthea-style FHIR Observation (body weight)."""
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "subject": {"reference": "urn:uuid:patient-1"},
        "encounter": {"reference": "urn:uuid:encounter-1"},
        "effectiveDateTime": "2026-10-11T10:00:00+00:00",
        "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}]},
        "valueQuantity": {"value": 72.5, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg"},
    }


def contract_results(observations: list[dict]) -> list[dict]:
    rows = [row for obs in observations for row in normalize_observation(obs)]
    return [r for r in check(rows, WINDOW) if r["is_anomaly"]]


def test_clean_observation_passes_the_contract():
    assert contract_results([fhir_observation()]) == []


@pytest.mark.parametrize("kind, expected_type, field", [
    ("number_as_string", "type_mismatch", "numeric_value"),
    ("missing_patient", "missing_required_field", "patient_id"),
    ("invalid_status", "invalid_value", "status"),
])
def test_each_injected_error_is_caught_end_to_end(kind, expected_type, field):
    anomalies = contract_results([corrupt(fhir_observation(), kind)])

    assert any(a["incident_type"] == expected_type and a["field_name"] == field for a in anomalies)


def test_corrupt_does_not_change_the_original():
    original = fhir_observation()
    corrupt(original, "number_as_string")

    assert original["valueQuantity"]["value"] == 72.5


def test_rate_zero_changes_nothing_and_rate_one_changes_everything():
    clean = [fhir_observation(f"obs-{i}") for i in range(20)]

    assert list(inject_schema_errors(clean, rate=0.0, seed=1)) == clean
    assert all(o != c for o, c in zip(inject_schema_errors(clean, rate=1.0, seed=1), clean))


def test_same_seed_gives_same_corruption():
    clean = [fhir_observation(f"obs-{i}") for i in range(20)]

    first = list(inject_schema_errors(clean, rate=0.5, seed=42))
    second = list(inject_schema_errors(clean, rate=0.5, seed=42))

    assert first == second


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError):
        corrupt(fhir_observation(), "not_a_kind")


def test_all_kinds_are_listed():
    assert set(SCHEMA_ERROR_KINDS) == {"number_as_string", "missing_patient", "invalid_status"}