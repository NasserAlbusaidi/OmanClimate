"""Smoke tests for Phase 3 station visualisations."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import polars as pl
import pytest

from pipeline.stations import STATIONS
from pipeline.viz.stations import (
    render_all,
    render_annual_mean_temperature,
    render_muscat_saiq_comparison,
    render_tropical_nights,
    render_wetbulb_hours,
)


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


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


def test_phase3_station_charts_render_non_empty_pngs(tmp_path: Path):
    annual = _write_station_annual(tmp_path / "oman_stations_annual.parquet")

    renderers = [
        render_annual_mean_temperature,
        render_tropical_nights,
        render_wetbulb_hours,
        render_muscat_saiq_comparison,
    ]
    for renderer in renderers:
        out = tmp_path / f"{renderer.__name__}.png"
        renderer(annual, out)
        assert out.exists()
        assert out.stat().st_size > 1_000


def test_render_all_returns_expected_phase3_chart_paths(tmp_path: Path):
    annual = _write_station_annual(tmp_path / "oman_stations_annual.parquet")
    out_dir = tmp_path / "charts"

    paths = render_all(annual, out_dir)

    assert [p.name for p in paths] == [
        "annual_mean_temp_by_station.png",
        "tropical_nights_by_station.png",
        "wetbulb_hours_by_station.png",
        "muscat_saiq_comparison.png",
    ]
    assert all(p.exists() and p.stat().st_size > 1_000 for p in paths)
