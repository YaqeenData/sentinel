from sentinel.detection.contract import check


WINDOW = {
    "resource_type": "Observation",
    "window_start": "2026-10-08T14:00:00",
    "window_end": "2026-10-08T14:01:00",
}


def healthy_row(**changes) -> dict:
    """A valid normalized row. Pass keyword arguments to break one field."""
    row = {
        "observation_id": "obs-1",
        "patient_id": "patient-1",
        "status": "final",
        "code": "29463-7",
        "value_type": "numeric",
        "numeric_value": 72.5,
        "unit": "kg",
    }
    row.update(changes)
    return row


def test_healthy_window_has_no_anomaly():
    results = check([healthy_row(), healthy_row(numeric_value=120)], WINDOW)

    assert len(results) == 1
    assert results[0]["is_anomaly"] is False
    assert results[0]["incident_type"] == "contract_ok"


def test_number_as_string_is_caught():
    rows = [healthy_row(), healthy_row(observation_id="obs-2", numeric_value="72.5")]

    results = check(rows, WINDOW)

    assert len(results) == 1
    result = results[0]
    assert result["is_anomaly"] is True
    assert result["field_name"] == "numeric_value"
    assert result["incident_type"] == "type_mismatch"
    assert result["baseline_value"] == "number"
    assert result["current_value"] == "str"
    assert result["evidence"]["bad_rows"] == 1
    assert result["evidence"]["total_rows"] == 2


def test_missing_patient_is_caught():
    results = check([healthy_row(patient_id=None)], WINDOW)

    assert results[0]["field_name"] == "patient_id"
    assert results[0]["incident_type"] == "missing_required_field"


def test_invalid_status_is_caught():
    results = check([healthy_row(status="done")], WINDOW)

    assert results[0]["field_name"] == "status"
    assert results[0]["incident_type"] == "invalid_value"


def test_many_bad_rows_give_one_result():
    rows = [healthy_row(observation_id=f"obs-{i}", numeric_value="x") for i in range(50)]

    results = check(rows, WINDOW)

    assert len(results) == 1
    assert results[0]["evidence"]["bad_rows"] == 50
    assert len(results[0]["evidence"]["example_observation_ids"]) == 3


def test_categorical_row_is_valid():
    row = healthy_row(
        value_type="categorical",
        numeric_value=None,
        categorical_code="266919005",
    )

    results = check([row], WINDOW)

    assert results[0]["is_anomaly"] is False