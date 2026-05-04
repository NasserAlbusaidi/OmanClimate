"""Sea of Oman SST analytics and static-site export."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from pipeline.analysis.sst import build_sst_payload
from pipeline.viz.sst import write_sst_data


def _sst_annual() -> pl.DataFrame:
    rows = []
    for year in range(1982, 1992):
        offset = year - 1982
        rows.append(
            {
                "year": year,
                "sst_mean": 26.0 + offset * 0.12,
                "sst_jun_sep_mean": 28.0 + offset * 0.10,
                "sst_may_oct_mean": 27.5 + offset * 0.15,
                "sst_anomaly_vs_1982_2011": offset * 0.12,
                "n_days": 365,
            }
        )
    return pl.DataFrame(rows)


def _station_annual() -> pl.DataFrame:
    rows = []
    for slug in ["muscat", "sohar"]:
        for year in range(1982, 1993):
            offset = year - 1982
            station_offset = 25 if slug == "sohar" else 0
            rows.append(
                {
                    "station_slug": slug,
                    "station_label": slug.title(),
                    "year": year,
                    "hours_wetbulb_above_28_sum": 100 + station_offset + offset * 9,
                    "days_overnight_low_above_30": 30 + station_offset + offset * 2,
                    "n_days": 365,
                }
            )
    return pl.DataFrame(rows)


def _salalah_daily() -> pl.DataFrame:
    rows = []
    for year in range(1982, 1993):
        start = date(year, 6, 1)
        offset = year - 1982
        for day_offset in range(90):
            rows.append(
                {
                    "station_slug": "salalah",
                    "date": start + timedelta(days=day_offset),
                    "hours_wetbulb_above_28": offset + day_offset % 4,
                }
            )
    return pl.DataFrame(rows)


def test_build_sst_payload_includes_source_region_latest_and_trend():
    payload = build_sst_payload(_sst_annual(), _station_annual(), _salalah_daily())

    assert payload["source"] == "NOAA OISST v2.1"
    assert payload["region"]["west"] == 56.0
    assert payload["annual_start_year"] == 1982
    assert payload["baseline"] == "1982-2011"
    assert payload["latest"]["year"] == 1991
    assert payload["trend"]["slope_per_year"] > 0
    assert payload["trend"]["slope_c_per_year"] == payload["trend"]["slope_per_year"]
    assert payload["trend"]["start_year"] == 1982
    assert payload["years"][0]["year"] == 1982


def test_sst_correlations_include_same_year_and_lagged_station_signals():
    payload = build_sst_payload(_sst_annual(), _station_annual(), _salalah_daily())

    correlations = payload["correlations"]
    pairs = {(item["target"], item["lag_years"]) for item in correlations}

    assert ("muscat_wetbulb_hours", 0) in pairs
    assert ("muscat_wetbulb_hours", 1) in pairs
    assert ("salalah_khareef_wetbulb_hours", 0) in pairs
    for item in correlations:
        if item["r"] is not None:
            assert -1 <= item["r"] <= 1


def test_write_sst_data_emits_local_site_js(tmp_path: Path):
    sst_path = tmp_path / "sst.parquet"
    station_path = tmp_path / "station.parquet"
    salalah_path = tmp_path / "salalah.parquet"
    _sst_annual().write_parquet(sst_path)
    _station_annual().write_parquet(station_path)
    _salalah_daily().write_parquet(salalah_path)

    out = tmp_path / "sst-data.js"
    result = write_sst_data(sst_path, station_path, salalah_path, out)

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith("window.OMAN_SST_DATA = ")
    data = json.loads(text.removeprefix("window.OMAN_SST_DATA = ").rstrip(";\n"))
    assert data["source"] == "NOAA OISST v2.1"
