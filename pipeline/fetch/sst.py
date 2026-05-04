"""Fetch NOAA OISST sea-surface temperature subsets as NetCDF.

The NOAA PSL THREDDS NCSS endpoint can return regional subsets from the
high-resolution OISST files. This fetcher uses the monthly mean product for
the full Sea of Oman time series because PSL returns 502 for full-year daily
subsets while a complete monthly regional subset is small and reliable.
"""

from __future__ import annotations

import logging
import time
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OISST_START = date(1981, 9, 1)
DEFAULT_FETCH_START = date(1982, 1, 1)
DEFAULT_DATA_DIR = Path("data/raw/noaa-oisst")
PSL_NCSS_ROOT = (
    "https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres"
)
MONTHLY_SOURCE_FILENAME = "sst.mon.mean.nc"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SSTRegion:
    slug: str
    label: str
    north: float
    south: float
    west: float
    east: float


SEA_OF_OMAN_REGION = SSTRegion(
    slug="sea-of-oman",
    label="Sea of Oman",
    north=26.5,
    south=22.0,
    west=56.0,
    east=61.0,
)


@dataclass(frozen=True)
class SSTYearChunk:
    year: int
    start: date
    end: date

    @property
    def source_filename(self) -> str:
        return f"sst.day.mean.{self.year}.nc"

    def cache_filename(self, region: SSTRegion = SEA_OF_OMAN_REGION) -> str:
        return f"sst.day.mean.{self.cache_period}.{region.slug}.nc"

    @property
    def cache_period(self) -> str:
        if self.start == date(self.year, 1, 1) and self.end == date(self.year, 12, 31):
            return str(self.year)

        if (
            self.start.day == 1
            and self.start.year == self.end.year
            and self.start.month == self.end.month
            and self.end.day == monthrange(self.end.year, self.end.month)[1]
        ):
            return f"{self.start.year}-{self.start.month:02d}"

        return f"{self.start.isoformat()}_{self.end.isoformat()}"


@dataclass(frozen=True)
class SSTMonthlyMeanChunk:
    start: date
    end: date

    @property
    def source_filename(self) -> str:
        return MONTHLY_SOURCE_FILENAME

    def cache_filename(self, region: SSTRegion = SEA_OF_OMAN_REGION) -> str:
        return f"sst.mon.mean.{self.start.isoformat()}_{self.end.isoformat()}.{region.slug}.nc"


def sst_year_chunks(
    start: date = DEFAULT_FETCH_START,
    end: date | None = None,
) -> list[SSTYearChunk]:
    """Split [start, end] into OISST calendar-year chunks."""
    start = max(start, OISST_START)
    end = end or date.today()
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")

    chunks: list[SSTYearChunk] = []
    for year in range(start.year, end.year + 1):
        chunks.append(
            SSTYearChunk(
                year=year,
                start=max(start, date(year, 1, 1)),
                end=min(end, date(year, 12, 31)),
            )
        )
    return chunks


def sst_month_chunks(
    start: date = DEFAULT_FETCH_START,
    end: date | None = None,
) -> list[SSTYearChunk]:
    """Split [start, end] into OISST calendar-month chunks."""
    start = max(start, OISST_START)
    end = end or date.today()
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")

    chunks: list[SSTYearChunk] = []
    current = start
    while current <= end:
        month_end = date(
            current.year,
            current.month,
            monthrange(current.year, current.month)[1],
        )
        chunk_end = min(end, month_end)
        chunks.append(SSTYearChunk(current.year, current, chunk_end))

        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return chunks


def sst_monthly_mean_chunk(
    start: date = DEFAULT_FETCH_START,
    end: date | None = None,
) -> SSTMonthlyMeanChunk:
    """Return one monthly-mean OISST chunk for [start, end]."""
    start = max(start, OISST_START)
    end = end or date.today()
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")
    return SSTMonthlyMeanChunk(start=start, end=end)


def ncss_url(chunk: SSTYearChunk | SSTMonthlyMeanChunk) -> str:
    return f"{PSL_NCSS_ROOT}/{chunk.source_filename}"


def _format_float(value: float) -> str:
    return f"{value:.1f}"


def _ncss_time(value: date) -> str:
    return f"{value.isoformat()}T00:00:00Z"


def ncss_params(
    chunk: SSTYearChunk | SSTMonthlyMeanChunk,
    region: SSTRegion = SEA_OF_OMAN_REGION,
) -> dict[str, str]:
    return {
        "var": "sst",
        "north": _format_float(region.north),
        "south": _format_float(region.south),
        "west": _format_float(region.west),
        "east": _format_float(region.east),
        "time_start": _ncss_time(chunk.start),
        "time_end": _ncss_time(chunk.end),
        "accept": "netcdf3",
        "disableProjSubset": "on",
        "horizStride": "1",
        "timeStride": "1",
    }


def cache_path(
    chunk: SSTYearChunk | SSTMonthlyMeanChunk,
    data_dir: Path = DEFAULT_DATA_DIR,
    region: SSTRegion = SEA_OF_OMAN_REGION,
) -> Path:
    return data_dir / chunk.cache_filename(region)


def should_skip(path: Path, chunk: SSTYearChunk | SSTMonthlyMeanChunk, today: date) -> bool:
    """Skip iff a cached file exists for a completed date chunk."""
    if not path.exists():
        return False
    return chunk.end < today


def _build_session() -> requests.Session:
    sess = requests.Session()
    retry = Retry(
        total=5,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def fetch_sst_chunk(
    chunk: SSTYearChunk | SSTMonthlyMeanChunk,
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    today: date | None = None,
    region: SSTRegion = SEA_OF_OMAN_REGION,
    session: requests.Session | None = None,
    sleep_after: float = 0.25,
) -> Path:
    """Fetch one OISST date chunk to cache and return the NetCDF path."""
    today = today or date.today()
    path = cache_path(chunk, data_dir, region)
    if should_skip(path, chunk, today):
        log.debug("cache hit %s", path.name)
        return path

    sess = session or _build_session()
    url = ncss_url(chunk)
    params = ncss_params(chunk, region)
    log.info("fetching %s %s..%s", region.label, chunk.start, chunk.end)
    resp = sess.get(url, params=params, timeout=180)
    resp.raise_for_status()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(resp.content)
    tmp.replace(path)

    if sleep_after > 0:
        time.sleep(sleep_after)
    return path


def fetch_sst_range(
    start: date = DEFAULT_FETCH_START,
    end: date | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    today: date | None = None,
    region: SSTRegion = SEA_OF_OMAN_REGION,
    session: requests.Session | None = None,
    polite_sleep: float = 0.25,
) -> list[Path]:
    """Fetch one monthly-mean OISST regional subset for the date range."""
    today = today or date.today()
    end = end or today
    sess = session or _build_session()

    chunk = sst_monthly_mean_chunk(start=start, end=end)
    return [
        fetch_sst_chunk(
            chunk,
            data_dir,
            today=today,
            region=region,
            session=sess,
            sleep_after=polite_sleep,
        )
    ]
