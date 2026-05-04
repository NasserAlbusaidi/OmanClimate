"""Fetch and process a rural Oman station for urban-heat-island diagnostics.

Adam (Adam, Ad Dakhiliyah) sits ≈170 km inland on the gravel desert plain,
no nearby coast, no mountains, ~80,000 population. It is a clean rural
comparator for Muscat: same regional climate, none of the urbanisation.

Per project rule 2, the credible regional climate signal is the trend
agreement between Muscat and Adam; the *difference* between their trends
is approximately the urban contribution at Seeb.

This module deliberately keeps its data isolated from the main pipeline:
- Cache directory: ``data/raw/open-meteo-adam/``
- Aggregation runs in-memory; no parquet output. (Phase 3 will refactor
  the main pipeline to be station-aware; until then we don't pollute it.)
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import polars as pl
import requests

from pipeline.fetch.open_meteo import (
    HISTORICAL_START,
    YearChunk,
    _build_session,
    year_chunks,
)
from pipeline.process.aggregates import (
    build_annual,
    build_daily,
    hourly_from_open_meteo,
)

ADAM_LAT = 22.379
ADAM_LON = 57.532
ADAM_NAME = "adam"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = ["temperature_2m", "dewpoint_2m", "relativehumidity_2m"]

log = logging.getLogger(__name__)


def _cache_path(chunk: YearChunk, data_dir: Path) -> Path:
    return data_dir / f"{ADAM_NAME}-{chunk.start.isoformat()}_{chunk.end.isoformat()}.json"


def fetch_adam(
    start: date = HISTORICAL_START,
    end: date | None = None,
    data_dir: Path | None = None,
    *,
    today: date | None = None,
    polite_sleep: float = 0.25,
) -> list[Path]:
    """Year-chunked fetch for Adam coords. Same caching semantics as Muscat."""
    today = today or date.today()
    end = end or today
    data_dir = data_dir or Path("data/raw/open-meteo-adam")
    data_dir.mkdir(parents=True, exist_ok=True)
    sess = _build_session()

    paths: list[Path] = []
    for chunk in year_chunks(start, end):
        path = _cache_path(chunk, data_dir)
        if path.exists() and chunk.year < today.year:
            paths.append(path)
            continue

        params = {
            "latitude": ADAM_LAT,
            "longitude": ADAM_LON,
            "start_date": chunk.start.isoformat(),
            "end_date": chunk.end.isoformat(),
            "hourly": ",".join(HOURLY_VARS),
            "timezone": "GMT",
        }
        log.info("adam %s..%s", chunk.start, chunk.end)
        resp = sess.get(ARCHIVE_URL, params=params, timeout=120)
        resp.raise_for_status()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(resp.json()))
        tmp.replace(path)
        paths.append(path)

        if polite_sleep > 0:
            import time
            time.sleep(polite_sleep)
    return paths


def build_adam_annual(data_dir: Path | None = None) -> pl.DataFrame:
    """Load cached Adam JSONs, run the same aggregation pipeline, return annual frame."""
    data_dir = data_dir or Path("data/raw/open-meteo-adam")
    files = sorted(data_dir.glob(f"{ADAM_NAME}-*.json"))
    if not files:
        raise FileNotFoundError(f"No Adam JSONs in {data_dir}; call fetch_adam() first")

    frames = []
    for p in files:
        with open(p) as fh:
            frames.append(hourly_from_open_meteo(json.load(fh)))
    hourly = (
        pl.concat(frames)
        .unique(subset=["time_utc"], keep="first")
        .sort("time_utc")
    )
    daily = build_daily(hourly)
    return build_annual(daily)
