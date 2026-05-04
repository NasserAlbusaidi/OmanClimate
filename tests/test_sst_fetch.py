"""NOAA OISST regional fetch helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pipeline.fetch.sst import (
    SEA_OF_OMAN_REGION,
    SSTRegion,
    SSTMonthlyMeanChunk,
    SSTYearChunk,
    cache_path,
    fetch_sst_chunk,
    fetch_sst_range,
    ncss_params,
    ncss_url,
    should_skip,
    sst_month_chunks,
    sst_monthly_mean_chunk,
    sst_year_chunks,
)


def test_sst_year_chunks_default_to_complete_oisst_years():
    chunks = sst_year_chunks(date(1982, 1, 1), date(1984, 12, 31))

    assert [chunk.year for chunk in chunks] == [1982, 1983, 1984]
    assert chunks[0].start == date(1982, 1, 1)
    assert chunks[-1].end == date(1984, 12, 31)


def test_sst_month_chunks_preserve_partial_first_and_last_months():
    chunks = sst_month_chunks(date(1982, 1, 1), date(1982, 3, 15))

    assert chunks == [
        SSTYearChunk(1982, date(1982, 1, 1), date(1982, 1, 31)),
        SSTYearChunk(1982, date(1982, 2, 1), date(1982, 2, 28)),
        SSTYearChunk(1982, date(1982, 3, 1), date(1982, 3, 15)),
    ]


def test_sst_monthly_mean_chunk_uses_single_regional_source_file():
    chunk = sst_monthly_mean_chunk(date(1982, 1, 1), date(2026, 5, 4))

    assert chunk == SSTMonthlyMeanChunk(date(1982, 1, 1), date(2026, 5, 4))
    assert ncss_url(chunk).endswith(
        "/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
    )
    assert cache_path(chunk, Path("/tmp")).name == (
        "sst.mon.mean.1982-01-01_2026-05-04.sea-of-oman.nc"
    )


def test_sst_chunk_uses_psl_ncss_url_and_region_params():
    chunk = SSTYearChunk(2024, date(2024, 1, 1), date(2024, 12, 31))

    assert ncss_url(chunk).endswith(
        "/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres/sst.day.mean.2024.nc"
    )
    params = ncss_params(chunk, SEA_OF_OMAN_REGION)
    assert params["var"] == "sst"
    assert params["north"] == "26.5"
    assert params["south"] == "22.0"
    assert params["west"] == "56.0"
    assert params["east"] == "61.0"
    assert params["time_start"] == "2024-01-01T00:00:00Z"
    assert params["time_end"] == "2024-12-31T00:00:00Z"
    assert params["accept"] == "netcdf3"


def test_sst_cache_path_is_region_scoped(tmp_path):
    chunk = SSTYearChunk(2024, date(2024, 1, 1), date(2024, 12, 31))

    assert cache_path(chunk, tmp_path).name == "sst.day.mean.2024.sea-of-oman.nc"


def test_sst_cache_path_uses_month_when_chunk_is_full_month(tmp_path):
    chunk = SSTYearChunk(2024, date(2024, 1, 1), date(2024, 1, 31))

    assert cache_path(chunk, tmp_path).name == "sst.day.mean.2024-01.sea-of-oman.nc"


def test_sst_cache_path_uses_date_range_when_chunk_is_partial_month(tmp_path):
    chunk = SSTYearChunk(2024, date(2024, 1, 15), date(2024, 1, 20))

    assert cache_path(chunk, tmp_path).name == (
        "sst.day.mean.2024-01-15_2024-01-20.sea-of-oman.nc"
    )


def test_sst_cache_path_uses_custom_region_slug(tmp_path):
    region = SSTRegion(
        slug="arabian-sea",
        label="Arabian Sea",
        north=22.0,
        south=16.0,
        west=54.0,
        east=60.0,
    )
    chunk = SSTYearChunk(2024, date(2024, 1, 1), date(2024, 12, 31))

    assert cache_path(chunk, tmp_path, region=region).name == (
        "sst.day.mean.2024.arabian-sea.nc"
    )


def test_should_skip_completed_cached_year(tmp_path):
    chunk = SSTYearChunk(2020, date(2020, 1, 1), date(2020, 12, 31))
    path = cache_path(chunk, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"cached")

    assert should_skip(path, chunk, today=date(2026, 5, 4)) is True


def test_fetch_sst_chunk_writes_netcdf_bytes_and_uses_subset_params(tmp_path):
    class FakeResponse:
        content = b"netcdf-bytes"

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, params=None, timeout=None):
            self.calls.append((url, params, timeout))
            return FakeResponse()

    session = FakeSession()
    chunk = SSTYearChunk(2024, date(2024, 1, 1), date(2024, 12, 31))
    path = fetch_sst_chunk(
        chunk,
        tmp_path,
        today=date(2026, 5, 4),
        session=session,
        sleep_after=0,
    )

    assert path.read_bytes() == b"netcdf-bytes"
    assert len(session.calls) == 1
    url, params, timeout = session.calls[0]
    assert url == ncss_url(chunk)
    assert params["north"] == "26.5"
    assert timeout == 180


def test_fetch_sst_range_uses_today_as_default_end(tmp_path):
    class FakeResponse:
        content = b"netcdf-bytes"

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, params=None, timeout=None):
            self.calls.append((url, params, timeout))
            return FakeResponse()

    session = FakeSession()
    paths = fetch_sst_range(
        start=date(1982, 1, 1),
        data_dir=tmp_path,
        today=date(1982, 3, 2),
        session=session,
        polite_sleep=0,
    )

    assert [path.name for path in paths] == [
        "sst.mon.mean.1982-01-01_1982-03-02.sea-of-oman.nc",
    ]
    assert len(session.calls) == 1
    assert session.calls[0][1]["time_end"] == "1982-03-02T00:00:00Z"


def test_fetch_sst_range_requests_monthly_mean_ncss_boundaries(tmp_path):
    class FakeResponse:
        content = b"netcdf-bytes"

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, params=None, timeout=None):
            self.calls.append((url, params, timeout))
            return FakeResponse()

    session = FakeSession()
    fetch_sst_range(
        start=date(1982, 1, 15),
        end=date(1982, 3, 2),
        data_dir=tmp_path,
        today=date(1982, 3, 2),
        session=session,
        polite_sleep=0,
    )

    assert [call[1]["time_start"] for call in session.calls] == [
        "1982-01-15T00:00:00Z",
    ]
    assert [call[1]["time_end"] for call in session.calls] == [
        "1982-03-02T00:00:00Z",
    ]
    assert [call[0] for call in session.calls] == [ncss_url(SSTMonthlyMeanChunk(date(1982, 1, 15), date(1982, 3, 2)))]
