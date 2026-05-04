"""Phase 3 station-aware Open-Meteo processing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import polars as pl

from pipeline.fetch.open_meteo import cached_files, station_raw_dir
from pipeline.process.aggregates import (
    build_annual,
    build_daily,
    hourly_from_files,
    write_parquet_atomic,
)
from pipeline.process.era5 import annual_to_common_schema
from pipeline.stations import STATIONS, Station

MIN_DAYS_FOR_STATION_ANNUAL = 360


@dataclass(frozen=True)
class StationOutputs:
    station: Station
    daily: pl.DataFrame
    annual: pl.DataFrame
    station_daily_path: Path
    station_annual_path: Path


def _with_station_metadata(df: pl.DataFrame, station: Station) -> pl.DataFrame:
    metadata = [
        pl.lit(station.slug).alias("station_slug"),
        pl.lit(station.label).alias("station_label"),
        pl.lit(station.latitude).alias("latitude"),
        pl.lit(station.longitude).alias("longitude"),
        pl.lit(station.category).alias("category"),
        pl.lit(station.source_note).alias("source_note"),
    ]
    return df.with_columns(metadata).select(
        [
            "station_slug",
            "station_label",
            "latitude",
            "longitude",
            "category",
            "source_note",
            *df.columns,
        ]
    )


def process_station(
    station: Station,
    *,
    raw_root: Path,
    out_dir: Path,
    write_legacy_muscat: bool = True,
) -> StationOutputs:
    """Process one station cache into station-scoped parquet outputs."""
    raw_dir = station_raw_dir(raw_root, station)
    files = list(cached_files(raw_dir, station.slug))
    if not files:
        raise FileNotFoundError(
            f"No Open-Meteo JSON files for station {station.slug!r} in {raw_dir}"
        )

    hourly = hourly_from_files(files)
    daily = build_daily(hourly)
    annual = build_annual(daily)

    station_daily = _with_station_metadata(daily, station)
    station_annual = _with_station_metadata(annual, station)

    stations_dir = out_dir / "stations"
    station_daily_path = stations_dir / f"{station.slug}_daily.parquet"
    station_annual_path = stations_dir / f"{station.slug}_annual.parquet"
    write_parquet_atomic(station_daily, station_daily_path)
    write_parquet_atomic(station_annual, station_annual_path)

    if write_legacy_muscat and station.slug == "muscat":
        write_parquet_atomic(daily, out_dir / "muscat_daily.parquet")
        write_parquet_atomic(annual, out_dir / "muscat_annual.parquet")
        write_parquet_atomic(daily, out_dir / "muscat_era5_daily.parquet")
        write_parquet_atomic(
            annual_to_common_schema(annual),
            out_dir / "muscat_era5_annual.parquet",
        )

    return StationOutputs(
        station=station,
        daily=station_daily,
        annual=station_annual,
        station_daily_path=station_daily_path,
        station_annual_path=station_annual_path,
    )


def process_stations(
    *,
    raw_root: Path,
    out_dir: Path,
    stations: Iterable[Station] = STATIONS,
) -> pl.DataFrame:
    """Process all configured stations and write ``oman_stations_annual.parquet``."""
    outputs = [
        process_station(station, raw_root=raw_root, out_dir=out_dir)
        for station in stations
    ]
    if not outputs:
        raise ValueError("No stations supplied")

    combined = (
        pl.concat([out.annual for out in outputs], how="vertical")
        .filter(pl.col("n_days") >= MIN_DAYS_FOR_STATION_ANNUAL)
        .sort(["station_slug", "year"])
    )
    write_parquet_atomic(combined, out_dir / "oman_stations_annual.parquet")
    return combined
