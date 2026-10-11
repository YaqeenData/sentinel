from sentinel.streaming import windows


def test_rows_are_split_every_60_seconds(monkeypatch):
    # time.time() calls: start, row1, row2, row3, row4, final close
    clock = iter([0, 0, 10, 61, 62, 70])
    monkeypatch.setattr(windows.time, "time", lambda: next(clock))

    rows = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
    result = list(windows.tumbling_windows(rows, seconds=60))

    assert [[r["id"] for r in batch] for _, batch in result] == [[1, 2], [3, 4]]
    assert all(w["resource_type"] == "Observation" for w, _ in result)


def test_empty_stream_gives_no_windows():
    assert list(windows.tumbling_windows([], seconds=60)) == []
