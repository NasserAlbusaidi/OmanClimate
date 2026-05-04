"""NOAA GHCN-Daily station fetcher contracts."""

from __future__ import annotations

from pathlib import Path

from pipeline.fetch.ghcn import (
    GHCN_BY_STATION_URL,
    REQUESTED_SEEB_STATION_ID,
    SEEB_STATION_ID,
    fetch_station,
    normalize_station_id,
    station_cache_path,
    station_url,
)


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.content = payload

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self, payload: bytes = b"station,data\n"):
        self.payload = payload
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return _FakeResponse(self.payload)


def test_station_url_points_at_noaa_by_station_archive():
    assert station_url(SEEB_STATION_ID) == (
        f"{GHCN_BY_STATION_URL}/MUM00041256.csv.gz"
    )


def test_requested_oman_iso_style_id_maps_to_official_ghcn_id():
    assert REQUESTED_SEEB_STATION_ID == "OMM00041256"
    assert normalize_station_id(REQUESTED_SEEB_STATION_ID) == "MUM00041256"
    assert station_url(REQUESTED_SEEB_STATION_ID) == (
        f"{GHCN_BY_STATION_URL}/MUM00041256.csv.gz"
    )


def test_station_cache_path_uses_source_directory(tmp_path: Path):
    assert station_cache_path(tmp_path, SEEB_STATION_ID) == (
        tmp_path / "MUM00041256.csv.gz"
    )


def test_fetch_station_writes_compressed_station_file(tmp_path: Path):
    sess = _FakeSession(b"raw-gzip-bytes")

    out = fetch_station(data_dir=tmp_path, session=sess)

    assert out == tmp_path / "MUM00041256.csv.gz"
    assert out.read_bytes() == b"raw-gzip-bytes"
    assert sess.calls == [
        ("https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/MUM00041256.csv.gz", 120)
    ]


def test_fetch_station_skips_existing_file_by_default(tmp_path: Path):
    existing = tmp_path / "MUM00041256.csv.gz"
    existing.write_bytes(b"cached")
    sess = _FakeSession(b"fresh")

    out = fetch_station(data_dir=tmp_path, session=sess)

    assert out == existing
    assert existing.read_bytes() == b"cached"
    assert sess.calls == []


def test_fetch_station_force_refetches_existing_file(tmp_path: Path):
    existing = tmp_path / "MUM00041256.csv.gz"
    existing.write_bytes(b"cached")
    sess = _FakeSession(b"fresh")

    fetch_station(data_dir=tmp_path, session=sess, force=True)

    assert existing.read_bytes() == b"fresh"
    assert len(sess.calls) == 1
