"""Fetch NOAA GHCN-Daily station data, cached as compressed CSV.

The station-level GHCN-Daily archive publishes one ``.csv.gz`` file per
station under ``by_station``. We use that instead of the all-stations tarball
so the raw cache stays small and source-specific:

    data/raw/ghcn/MUM00041256.csv.gz
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GHCN_BY_STATION_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station"
REQUESTED_SEEB_STATION_ID = "OMM00041256"
SEEB_STATION_ID = "MUM00041256"
DEFAULT_DATA_DIR = Path("data/raw/ghcn")
STATION_ALIASES = {
    # The user-facing request used an ISO-style Oman prefix. NOAA GHCN station
    # IDs use FIPS country prefixes; Seeb appears in ghcnd-stations.txt as
    # MUM00041256 with WMO ID 41256.
    REQUESTED_SEEB_STATION_ID: SEEB_STATION_ID,
}

log = logging.getLogger(__name__)


def normalize_station_id(station_id: str = SEEB_STATION_ID) -> str:
    return STATION_ALIASES.get(station_id, station_id)


def station_url(station_id: str = SEEB_STATION_ID) -> str:
    station_id = normalize_station_id(station_id)
    return f"{GHCN_BY_STATION_URL}/{station_id}.csv.gz"


def station_cache_path(
    data_dir: Path = DEFAULT_DATA_DIR,
    station_id: str = SEEB_STATION_ID,
) -> Path:
    station_id = normalize_station_id(station_id)
    return data_dir / f"{station_id}.csv.gz"


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


def fetch_station(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    station_id: str = SEEB_STATION_ID,
    session: requests.Session | None = None,
    force: bool = False,
) -> Path:
    """Fetch one GHCN-Daily station CSV into ``data_dir``.

    NOAA updates station CSVs daily for the full period of record. To keep the
    default command idempotent, an existing file is reused unless ``force`` is
    true.
    """
    station_id = normalize_station_id(station_id)
    path = station_cache_path(data_dir, station_id)
    if path.exists() and not force:
        log.debug("cache hit %s", path)
        return path

    sess = session or _build_session()
    url = station_url(station_id)
    log.info("fetching %s", url)
    resp = sess.get(url, timeout=120)
    resp.raise_for_status()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(resp.content)
    tmp.replace(path)
    return path
