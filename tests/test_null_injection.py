import pytest

from sentinel.injection.nulls import inject_null_spike


def test_injects_nulls_into_selected_field():
    rows = [{"value": i, "other": i * 2} for i in range(100)]

    result = inject_null_spike(rows, "value", 0.30)

    assert sum(row["value"] is None for row in result) == 30
    assert all(row["other"] is not None for row in result)


def test_original_rows_are_unchanged():
    rows = [{"value": i} for i in range(10)]

    result = inject_null_spike(rows, "value", 0.50)

    assert all(row["value"] is not None for row in rows)
    assert result is not rows


def test_empty_rows():
    assert inject_null_spike([], "value", 0.30) == []


def test_zero_null_rate():
    rows = [{"value": 1}, {"value": 2}]

    result = inject_null_spike(rows, "value", 0)

    assert result == rows
    assert all(row["value"] is not None for row in result)


def test_invalid_null_rate():
    with pytest.raises(ValueError):
        inject_null_spike([{"value": 1}], "value", 1.5)


def test_empty_field_name():
    with pytest.raises(ValueError):
        inject_null_spike([{"value": 1}], "", 0.30)
