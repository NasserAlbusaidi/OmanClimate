"""Open-Meteo fetcher — pure helpers tested directly, HTTP layer mocked."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pipeline.fetch.open_meteo import (
    YearChunk,
    cache_path,
    fetch_chunk,
    fetch_range,
    fetch_station_range,
    should_skip,
    year_chunks,
)
from pipeline.stations import station_by_slug


def test_year_chunks_full_years():
    chunks = year_chunks(date(2020, 1, 1), date(2022, 12, 31))
    assert [c.year for c in chunks] == [2020, 2021, 2022]
    assert chunks[0].start == date(2020, 1, 1)
    assert chunks[0].end == date(2020, 12, 31)
    assert chunks[-1].end == date(2022, 12, 31)


def test_year_chunks_partial_first_and_last():
    chunks = year_chunks(date(2020, 6, 1), date(2022, 3, 15))
    assert chunks[0].start == date(2020, 6, 1)
    assert chunks[0].end == date(2020, 12, 31)
    assert chunks[1].start == date(2021, 1, 1)
    assert chunks[1].end == date(2021, 12, 31)
    assert chunks[2].start == date(2022, 1, 1)
    assert chunks[2].end == date(2022, 3, 15)


def test_year_chunks_single_year():
    chunks = year_chunks(date(1940, 1, 1), date(1940, 12, 31))
    assert len(chunks) == 1
    assert chunks[0].year == 1940


def test_year_chunks_rejects_inverted_range():
    with pytest.raises(ValueError):
        year_chunks(date(2024, 1, 1), date(2023, 12, 31))


def test_filename_contains_iso_dates():
    c = YearChunk(year=2024, start=date(2024, 1, 1), end=date(2024, 12, 31))
    assert c.filename == "muscat-2024-01-01_2024-12-31.json"


def test_should_skip_completed_year_with_cache(tmp_path):
    chunk = YearChunk(2020, date(2020, 1, 1), date(2020, 12, 31))
    p = cache_path(chunk, tmp_path)
    p.write_text("{}")
    assert should_skip(p, chunk, today=date(2026, 5, 2)) is True


def test_should_skip_no_file(tmp_path):
    chunk = YearChunk(2020, date(2020, 1, 1), date(2020, 12, 31))
    p = cache_path(chunk, tmp_path)
    assert should_skip(p, chunk, today=date(2026, 5, 2)) is False


def test_should_skip_current_year_always_refetches(tmp_path):
    chunk = YearChunk(2026, date(2026, 1, 1), date(2026, 12, 31))
    p = cache_path(chunk, tmp_path)
    p.write_text("{}")
    assert should_skip(p, chunk, today=date(2026, 5, 2)) is False


# ---- HTTP layer (mocked) ----------------------------------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return _FakeResponse(self.payload)


_PAYLOAD = {
    "latitude": 23.5859,
    "longitude": 58.4059,
    "hourly": {
        "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
        "temperature_2m": [22.5, 22.0],
        "dewpoint_2m": [15.1, 15.3],
        "relativehumidity_2m": [65, 67],
    },
}


def test_fetch_chunk_writes_cache(tmp_path):
    sess = _FakeSession(_PAYLOAD)
    chunk = YearChunk(2020, date(2020, 1, 1), date(2020, 12, 31))
    p = fetch_chunk(chunk, tmp_path, today=date(2026, 5, 2), session=sess)
    assert p.exists()
    assert json.loads(p.read_text())["hourly"]["temperature_2m"] == [22.5, 22.0]
    assert len(sess.calls) == 1
    params = sess.calls[0][1]
    assert params["start_date"] == "2020-01-01"
    assert params["end_date"] == "2020-12-31"
    assert params["timezone"] == "GMT"


def test_fetch_chunk_skips_cached_completed_year(tmp_path):
    sess = _FakeSession(_PAYLOAD)
    chunk = YearChunk(2020, date(2020, 1, 1), date(2020, 12, 31))
    p = cache_path(chunk, tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"already": "cached"}))

    fetch_chunk(chunk, tmp_path, today=date(2026, 5, 2), session=sess)
    assert sess.calls == []  # no HTTP call
    assert json.loads(p.read_text()) == {"already": "cached"}


def test_fetch_chunk_refetches_current_year(tmp_path):
    sess = _FakeSession(_PAYLOAD)
    chunk = YearChunk(2026, date(2026, 1, 1), date(2026, 12, 31))
    p = cache_path(chunk, tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"stale": True}))

    fetch_chunk(chunk, tmp_path, today=date(2026, 5, 2), session=sess)
    assert len(sess.calls) == 1
    assert "stale" not in json.loads(p.read_text())


def test_fetch_range_one_call_per_year(tmp_path):
    sess = _FakeSession(_PAYLOAD)
    fetch_range(
        start=date(2023, 1, 1),
        end=date(2024, 12, 31),
        data_dir=tmp_path,
        today=date(2026, 5, 2),
        session=sess,
        polite_sleep=0,
    )
    assert len(sess.calls) == 2
    starts = [c[1]["start_date"] for c in sess.calls]
    assert starts == ["2023-01-01", "2024-01-01"]


def test_fetch_station_range_uses_station_subfolder_slug_and_coordinates(tmp_path):
    sess = _FakeSession(_PAYLOAD)
    station = station_by_slug("saiq")

    paths = fetch_station_range(
        station,
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        raw_root=tmp_path,
        today=date(2026, 5, 2),
        session=sess,
        polite_sleep=0,
    )

    assert paths == [tmp_path / "saiq" / "saiq-2024-01-01_2024-12-31.json"]
    assert paths[0].exists()
    params = sess.calls[0][1]
    assert params["latitude"] == 23.0670
    assert params["longitude"] == 57.6330
