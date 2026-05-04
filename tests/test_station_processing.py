"""Station-aware processing from Open-Meteo raw JSON to Phase 3 aggregates."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.process.stations import process_stations
from pipeline.stations import station_by_slug


def _write_open_meteo_payload(
    raw_root: Path,
    slug: str,
    *,
    year: int,
    start_utc: datetime,
    hours: int,
    base_temp: float,
) -> Path:
    path = raw_root / slug / f"{slug}-{year}-01-01_{year}-12-31.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    times = [(start_utc + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    payload = {
        "hourly": {
            "time": times,
            "temperature_2m": [base_temp + (i % 24) * 0.1 for i in range(hours)],
            "dewpoint_2m": [base_temp - 8 for _ in range(hours)],
            "relativehumidity_2m": [60.0 for _ in range(hours)],
        }
    }
    path.write_text(json.dumps(payload))
    return path


def test_process_stations_writes_per_station_outputs_and_combined_full_years(tmp_path):
    raw_root = tmp_path / "raw" / "open-meteo"
    out_dir = tmp_path / "processed"
    stations = [station_by_slug("muscat"), station_by_slug("saiq")]

    for station, base_temp in [(stations[0], 28.0), (stations[1], 18.0)]:
        _write_open_meteo_payload(
            raw_root,
            station.slug,
            year=2020,
            start_utc=datetime(2020, 1, 1),
            hours=24 * 365,
            base_temp=base_temp,
        )
        _write_open_meteo_payload(
            raw_root,
            station.slug,
            year=2021,
            start_utc=datetime(2021, 1, 1),
            hours=24 * 2,
            base_temp=base_temp,
        )

    combined = process_stations(raw_root=raw_root, out_dir=out_dir, stations=stations)

    assert (out_dir / "stations" / "muscat_daily.parquet").exists()
    assert (out_dir / "stations" / "muscat_annual.parquet").exists()
    assert (out_dir / "stations" / "saiq_daily.parquet").exists()
    assert (out_dir / "stations" / "saiq_annual.parquet").exists()
    assert (out_dir / "oman_stations_annual.parquet").exists()

    # Station-aware processing also refreshes legacy Muscat paths for Phase 2 charts.
    assert (out_dir / "muscat_daily.parquet").exists()
    assert (out_dir / "muscat_annual.parquet").exists()

    annual = pl.read_parquet(out_dir / "oman_stations_annual.parquet")
    assert annual.equals(combined)
    assert set(annual["station_slug"]) == {"muscat", "saiq"}
    assert set(annual["year"]) == {2020}
    assert annual.select(pl.col("n_days").min()).item() >= 360

    required_columns = {
        "station_slug",
        "station_label",
        "latitude",
        "longitude",
        "category",
        "source_note",
        "year",
        "temp_mean_mean",
        "days_overnight_low_above_30",
        "hours_wetbulb_above_28_sum",
        "n_days",
    }
    assert required_columns.issubset(set(annual.columns))
