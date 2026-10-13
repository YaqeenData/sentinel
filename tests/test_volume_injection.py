import pytest

from sentinel.injection.volume import inject_volume_failure


def test_inject_volume_drop():
    rows = [{"id": i} for i in range(100)]

    result = inject_volume_failure(rows, mode="drop", factor=0.25)

    assert len(result) == 25
    assert len(rows) == 100


def test_inject_volume_spike():
    rows = [{"id": i} for i in range(100)]

    result = inject_volume_failure(rows, mode="spike", factor=0.5)

    assert len(result) == 150
    assert len(rows) == 100


def test_empty_rows():
    assert inject_volume_failure([], mode="drop") == []
    assert inject_volume_failure([], mode="spike") == []


def test_invalid_mode():
    with pytest.raises(ValueError):
        inject_volume_failure([{"id": 1}], mode="unknown")


def test_invalid_drop_factor():
    with pytest.raises(ValueError):
        inject_volume_failure([{"id": 1}], mode="drop", factor=1.0)


def test_invalid_factor():
    with pytest.raises(ValueError):
        inject_volume_failure([{"id": 1}], factor=0)
