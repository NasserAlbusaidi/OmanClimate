"""Station catalog and station-aware Open-Meteo cache contracts."""

from __future__ import annotations

from datetime import date

from pipeline.fetch.open_meteo import YearChunk, cache_path, station_raw_dir, year_chunks
from pipeline.stations import STATIONS, station_by_slug


def test_station_catalog_has_unique_slugs_and_valid_coordinates():
    slugs = [s.slug for s in STATIONS]
    assert slugs == ["muscat", "salalah", "sohar", "sur", "nizwa", "saiq"]
    assert len(slugs) == len(set(slugs))

    for station in STATIONS:
        assert -90 <= station.latitude <= 90
        assert -180 <= station.longitude <= 180
        assert station.label
        assert station.category
        assert station.source_note


def test_station_catalog_lookups_return_expected_metadata():
    muscat = station_by_slug("muscat")
    saiq = station_by_slug("saiq")

    assert muscat.label == "Muscat / Seeb"
    assert muscat.latitude == 23.5859
    assert muscat.longitude == 58.4059
    assert "mountain" in saiq.category
    assert saiq.latitude == 23.0670
    assert saiq.longitude == 57.6330


def test_station_cache_filenames_are_deterministic(tmp_path):
    chunk = YearChunk(
        year=2024,
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        station_slug="salalah",
    )

    assert chunk.filename == "salalah-2024-01-01_2024-12-31.json"
    assert station_raw_dir(tmp_path, "salalah") == tmp_path / "salalah"
    assert cache_path(chunk, station_raw_dir(tmp_path, "salalah")) == (
        tmp_path / "salalah" / "salalah-2024-01-01_2024-12-31.json"
    )


def test_legacy_muscat_chunk_filename_is_unchanged():
    chunk = YearChunk(year=2024, start=date(2024, 1, 1), end=date(2024, 12, 31))
    assert chunk.filename == "muscat-2024-01-01_2024-12-31.json"

    chunks = year_chunks(date(2024, 1, 1), date(2024, 12, 31))
    assert chunks[0].filename == "muscat-2024-01-01_2024-12-31.json"
