"""Fetch hourly weather from Open-Meteo Archive, cached per-year as JSON.

API: https://archive-api.open-meteo.com/v1/archive (no auth, free tier).
Reanalysis (ERA5) data starts 1940-01-01. We always request ``timezone=GMT``
and rely on `pipeline/process/timezones.py` for the Asia/Muscat conversion.

Caching contract:
- Legacy Muscat fetches keep one flat file per calendar year:
  ``muscat-YYYY-01-01_YYYY-12-31.json``.
- Phase 3 station fetches use station folders:
  ``data/raw/open-meteo/{station_slug}/{station_slug}-YYYY-...json``.
- Completed years (year < today.year) are immutable and skipped if present.
- The current year is always refetched (data is incomplete by definition).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pipeline.stations import STATIONS, Station

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MUSCAT_LAT = 23.5859
MUSCAT_LON = 58.4059
HOURLY_VARS = ["temperature_2m", "dewpoint_2m", "relativehumidity_2m"]
HISTORICAL_START = date(1940, 1, 1)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class YearChunk:
    year: int
    start: date
    end: date
    station_slug: str = "muscat"

    @property
    def filename(self) -> str:
        return f"{self.station_slug}-{self.start.isoformat()}_{self.end.isoformat()}.json"


def year_chunks(start: date, end: date, *, station_slug: str = "muscat") -> list[YearChunk]:
    """Split [start, end] (inclusive) into one chunk per calendar year."""
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")
    chunks = []
    for y in range(start.year, end.year + 1):
        chunk_start = max(start, date(y, 1, 1))
        chunk_end = min(end, date(y, 12, 31))
        chunks.append(
            YearChunk(
                year=y,
                start=chunk_start,
                end=chunk_end,
                station_slug=station_slug,
            )
        )
    return chunks


def cache_path(chunk: YearChunk, data_dir: Path) -> Path:
    return data_dir / chunk.filename


def station_raw_dir(raw_root: Path, station: Station | str) -> Path:
    """Return the Phase 3 raw cache directory for a station."""
    slug = station.slug if isinstance(station, Station) else station
    return raw_root / slug


def should_skip(path: Path, chunk: YearChunk, today: date) -> bool:
    """Skip the fetch iff the cache file exists and the year has already ended.

    The current year is always refetched: ERA5 data lags by ~5 days but the
    Open-Meteo "ECMWF IFS" forecast model fills the recent gap, so the row
    count grows daily.
    """
    if not path.exists():
        return False
    return chunk.year < today.year


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


def fetch_chunk(
    chunk: YearChunk,
    data_dir: Path,
    today: date,
    *,
    session: requests.Session | None = None,
    lat: float = MUSCAT_LAT,
    lon: float = MUSCAT_LON,
    sleep_after: float = 0.0,
) -> Path:
    """Fetch one year-chunk to ``data_dir`` (cached). Returns the JSON path."""
    path = cache_path(chunk, data_dir)
    if should_skip(path, chunk, today):
        log.debug("cache hit %s", path.name)
        return path

    sess = session or _build_session()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": chunk.start.isoformat(),
        "end_date": chunk.end.isoformat(),
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "GMT",
    }
    log.info("fetching %s..%s", chunk.start, chunk.end)
    resp = sess.get(ARCHIVE_URL, params=params, timeout=120)
    resp.raise_for_status()
    payload = resp.json()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(path)

    if sleep_after > 0:
        time.sleep(sleep_after)
    return path


def fetch_range(
    start: date = HISTORICAL_START,
    end: date | None = None,
    data_dir: Path | None = None,
    *,
    today: date | None = None,
    session: requests.Session | None = None,
    polite_sleep: float = 0.25,
) -> list[Path]:
    """Fetch a date range chunk-by-chunk; returns the list of cached paths."""
    today = today or date.today()
    end = end or today
    data_dir = data_dir or Path("data/raw/open-meteo")
    sess = session or _build_session()

    paths: list[Path] = []
    for chunk in year_chunks(start, end):
        paths.append(
            fetch_chunk(
                chunk,
                data_dir,
                today=today,
                session=sess,
                sleep_after=polite_sleep,
            )
        )
    return paths


def fetch_station_range(
    station: Station,
    start: date = HISTORICAL_START,
    end: date | None = None,
    raw_root: Path | None = None,
    *,
    today: date | None = None,
    session: requests.Session | None = None,
    polite_sleep: float = 0.25,
) -> list[Path]:
    """Fetch one configured station into ``raw_root/{station.slug}``."""
    today = today or date.today()
    end = end or today
    raw_root = raw_root or Path("data/raw/open-meteo")
    data_dir = station_raw_dir(raw_root, station)
    sess = session or _build_session()

    paths: list[Path] = []
    for chunk in year_chunks(start, end, station_slug=station.slug):
        paths.append(
            fetch_chunk(
                chunk,
                data_dir,
                today=today,
                session=sess,
                lat=station.latitude,
                lon=station.longitude,
                sleep_after=polite_sleep,
            )
        )
    return paths


def fetch_all_stations(
    *,
    start: date = HISTORICAL_START,
    end: date | None = None,
    raw_root: Path | None = None,
    stations: Iterable[Station] = STATIONS,
) -> list[Path]:
    """Fetch every configured Phase 3 station."""
    raw_root = raw_root or Path("data/raw/open-meteo")
    sess = _build_session()
    paths: list[Path] = []
    for station in stations:
        paths.extend(
            fetch_station_range(
                station,
                start=start,
                end=end,
                raw_root=raw_root,
                session=sess,
            )
        )
    return paths


def cached_files(data_dir: Path, station_slug: str = "muscat") -> Iterable[Path]:
    return sorted(data_dir.glob(f"{station_slug}-*.json"))
