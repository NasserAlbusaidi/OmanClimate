"""Personal climate analytics for Phase 4."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from pipeline.analysis.personal import build_personal_payload, compare_birth_year
from pipeline.stations import STATIONS
from pipeline.viz.personal_climate import write_personal_climate_data


def _write_station_annual(path: Path) -> Path:
    rows = []
    for station_idx, station in enumerate(STATIONS):
        for year in range(1978, 1986):
            offset = year - 1980
            rows.append(
                {
                    "station_slug": station.slug,
                    "station_label": station.label,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "category": station.category,
                    "source_note": station.source_note,
                    "year": year,
                    "temp_high_mean": 34.0 + station_idx,
                    "temp_low_mean": 22.0 + station_idx,
                    "temp_mean_mean": 28.0 + station_idx + offset * 0.1,
                    "dewpoint_mean_mean": 18.0,
                    "wet_bulb_max_p99": 26.0,
                    "hours_above_30_sum": 1000,
                    "hours_above_35_sum": 500,
                    "hours_above_40_sum": 20,
                    "hours_wetbulb_above_28_sum": 40 + station_idx * 10 + offset * 3,
                    "days_overnight_low_above_30": 10 + station_idx + offset,
                    "n_days": 365,
                    "summer_start": None,
                    "summer_end": None,
                    "summer_length": 60 + offset,
                    "heatwaves_3day_above_35": 2,
                    "heatwaves_5day_above_40": station_idx + max(offset, 0),
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(path)
    return path


def test_personal_payload_filters_to_trustworthy_years(tmp_path: Path):
    annual = pl.read_parquet(_write_station_annual(tmp_path / "annual.parquet"))

    payload = build_personal_payload(annual)

    assert payload["fit_start_year"] == 1980
    assert payload["generation_years"] == 30
    assert payload["default_birth_year"] == 1985
    assert payload["latest_year"] == 1985
    muscat = payload["stations"][0]
    assert muscat["slug"] == "muscat"
    assert sorted(muscat["series"]["temp_mean_c"]) == [
        "1980",
        "1981",
        "1982",
        "1983",
        "1984",
        "1985",
    ]
    assert "1979" not in muscat["series"]["temp_mean_c"]
    assert muscat["series"]["temp_mean_c"]["1985"] == pytest.approx(28.5)


def test_compare_birth_year_lifetime_and_generation_delta(tmp_path: Path):
    annual = pl.read_parquet(_write_station_annual(tmp_path / "annual.parquet"))
    payload = build_personal_payload(annual)

    comparison = compare_birth_year(payload, station_slug="muscat", birth_year=1982)

    temp = comparison["metrics"]["temp_mean_c"]
    assert temp["birth_year_value"] == pytest.approx(28.2)
    assert temp["latest_value"] == pytest.approx(28.5)
    assert temp["lifetime_delta"] == pytest.approx(0.3)
    assert temp["generation_baseline_year"] == 1952
    assert temp["generation_delta"] is None
    assert comparison["generation_available"] is False


def test_write_personal_climate_data_emits_local_site_js(tmp_path: Path):
    annual = _write_station_annual(tmp_path / "annual.parquet")
    out = tmp_path / "personal-climate-data.js"

    result = write_personal_climate_data(annual, out)

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith("window.OMAN_PERSONAL_CLIMATE_DATA = ")
    data = json.loads(
        text.removeprefix("window.OMAN_PERSONAL_CLIMATE_DATA = ").rstrip(";\n")
    )
    assert data["stations"][0]["slug"] == "muscat"
    assert data["metrics"][0]["key"] == "temp_mean_c"
    nights = next(metric for metric in data["metrics"] if metric["key"] == "tropical_nights")
    assert nights["label"] == "30°C nights"
