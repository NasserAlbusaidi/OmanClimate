"""Station-map data for the Phase 3 static site."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from pipeline.stations import STATIONS
from pipeline.viz.station_map import build_station_map_data, write_station_map_data


def _write_station_annual(path: Path) -> Path:
    rows = []
    years = list(range(1980, 1986))
    for station_idx, station in enumerate(STATIONS):
        for offset, year in enumerate(years):
            rows.append(
                {
                    "station_slug": station.slug,
                    "station_label": station.label,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "category": station.category,
                    "source_note": station.source_note,
                    "year": year,
                    "temp_high_mean": 34.0 + station_idx + offset * 0.05,
                    "temp_low_mean": 22.0 + station_idx * 0.5 + offset * 0.04,
                    "temp_mean_mean": 28.0 + station_idx * 0.4 + offset * 0.06,
                    "dewpoint_mean_mean": 18.0 + station_idx * 0.2,
                    "wet_bulb_max_p99": 26.0 + station_idx * 0.1 + offset * 0.02,
                    "hours_above_30_sum": 1000 + station_idx * 25 + offset,
                    "hours_above_35_sum": 500 + station_idx * 20 + offset,
                    "hours_above_40_sum": 20 + station_idx + offset,
                    "hours_wetbulb_above_28_sum": 50 + station_idx * 8 + offset,
                    "days_overnight_low_above_30": 10 + station_idx * 2 + offset,
                    "n_days": 365,
                    "summer_start": None,
                    "summer_end": None,
                    "summer_length": 60 + station_idx + offset,
                    "heatwaves_3day_above_35": 2 + station_idx,
                    "heatwaves_5day_above_40": station_idx,
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(path)
    return path


def test_station_map_data_summarizes_latest_values_and_trends(tmp_path: Path):
    annual = _write_station_annual(tmp_path / "oman_stations_annual.parquet")

    data = build_station_map_data(annual)

    assert data["fit_start_year"] == 1980
    assert data["min_days_for_trend"] == 360
    assert [station["slug"] for station in data["stations"]] == [
        station.slug for station in STATIONS
    ]

    muscat = data["stations"][0]
    assert muscat["slug"] == "muscat"
    assert muscat["latest_year"] == 1985
    assert muscat["latest"]["temp_mean_c"] == pytest.approx(28.30)
    assert muscat["latest"]["tropical_nights"] == pytest.approx(15)
    assert muscat["latest"]["wetbulb_hours_above_28"] == pytest.approx(55)
    assert muscat["trends"]["temp_mean_c"]["slope_per_year"] == pytest.approx(0.06)
    assert muscat["trends"]["temp_mean_c"]["p_value"] < 0.05
    assert muscat["trends"]["temp_mean_c"]["trend"] == "increasing"


def test_write_station_map_data_can_emit_local_site_js(tmp_path: Path):
    annual = _write_station_annual(tmp_path / "oman_stations_annual.parquet")
    out = tmp_path / "station-map-data.js"

    result = write_station_map_data(annual, out)

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith("window.OMAN_STATION_MAP_DATA = ")
    payload = text.removeprefix("window.OMAN_STATION_MAP_DATA = ").rstrip(";\n")
    data = json.loads(payload)
    assert data["stations"][0]["slug"] == "muscat"
    assert data["stations"][-1]["slug"] == "saiq"


def test_static_site_wires_station_map_data():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'src="station-map-data.js"' in html
    assert 'id="station-map"' in html
    assert "OMAN_STATION_MAP_DATA" in html
