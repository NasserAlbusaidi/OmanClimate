"""NOAA GHCN-Daily parsing and aggregate contracts."""

from __future__ import annotations

import gzip
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from pipeline.process.common_schema import COMMON_ANNUAL_COLUMNS
from pipeline.process.ghcn import (
    annual_from_ghcn_daily,
    daily_from_ghcn_csv,
)


def _write_station_csv(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")
    return path


def test_daily_from_ghcn_csv_uses_unflagged_tavg_in_tenths_c(tmp_path: Path):
    raw = _write_station_csv(
        tmp_path / "MUM00041256.csv.gz",
        [
            "MUM00041256,20200101,TAVG,255,,,S,2400",
            "MUM00041256,20200101,TMAX,301,,,S,2400",
            "MUM00041256,20200101,TMIN,208,,,S,2400",
        ],
    )

    daily = daily_from_ghcn_csv(raw)
    row = daily.row(0, named=True)

    assert row["source"] == "ghcn"
    assert row["station_id"] == "MUM00041256"
    assert row["date"] == date(2020, 1, 1)
    assert row["temp_mean"] == pytest.approx(25.5)
    assert row["temp_high"] == pytest.approx(30.1)
    assert row["temp_low"] == pytest.approx(20.8)
    assert row["temp_mean_method"] == "TAVG"
    assert row["aggregation_timezone"] == "station-observation-day"
    assert row["n_temperature_elements"] == 3


def test_daily_from_ghcn_csv_accepts_requested_station_alias(tmp_path: Path):
    raw = _write_station_csv(
        tmp_path / "MUM00041256.csv.gz",
        [
            "MUM00041256,20200101,TAVG,255,,,S,2400",
            "MUM00041256,20200101,TMAX,301,,,S,2400",
            "MUM00041256,20200101,TMIN,208,,,S,2400",
        ],
    )

    daily = daily_from_ghcn_csv(raw, station_id="OMM00041256")

    assert daily.row(0, named=True)["station_id"] == "MUM00041256"


def test_daily_from_ghcn_csv_filters_quality_flag_and_falls_back_to_tmax_tmin(
    tmp_path: Path,
):
    raw = _write_station_csv(
        tmp_path / "MUM00041256.csv.gz",
        [
            "MUM00041256,20200101,TAVG,999,,X,S,2400",
            "MUM00041256,20200101,TMAX,320,,,S,2400",
            "MUM00041256,20200101,TMIN,220,,,S,2400",
        ],
    )

    daily = daily_from_ghcn_csv(raw)
    row = daily.row(0, named=True)

    assert row["temp_mean"] == pytest.approx(27.0)
    assert row["temp_mean_method"] == "TMAX_TMIN_AVG"
    assert row["n_temperature_elements"] == 2


def test_daily_from_ghcn_csv_drops_rows_without_mean_temperature(tmp_path: Path):
    raw = _write_station_csv(
        tmp_path / "MUM00041256.csv.gz",
        [
            "MUM00041256,20200101,TMAX,320,,,S,2400",
            "MUM00041256,20200102,TMIN,220,,,S,2400",
        ],
    )

    daily = daily_from_ghcn_csv(raw)

    assert daily.is_empty()


def test_annual_from_ghcn_daily_uses_common_overlay_schema():
    daily = pl.DataFrame(
        {
            "source": ["ghcn", "ghcn", "ghcn"],
            "station_id": ["MUM00041256"] * 3,
            "station_name": ["SEEB INTL"] * 3,
            "date": [date(2020, 1, 1), date(2020, 1, 2), date(2021, 1, 1)],
            "temp_high": [30.0, 32.0, 31.0],
            "temp_low": [20.0, 22.0, 21.0],
            "temp_mean": [25.0, 27.0, 26.0],
            "temp_mean_method": ["TAVG", "TMAX_TMIN_AVG", "TAVG"],
            "aggregation_timezone": ["station-observation-day"] * 3,
            "day_boundary": ["GHCN-Daily station daily summary"] * 3,
            "n_temperature_elements": [3, 2, 3],
        }
    )

    annual = annual_from_ghcn_daily(daily)
    rows = {row["year"]: row for row in annual.iter_rows(named=True)}

    assert annual.columns == COMMON_ANNUAL_COLUMNS
    assert rows[2020]["temp_mean_mean"] == pytest.approx(26.0)
    assert rows[2020]["temp_high_mean"] == pytest.approx(31.0)
    assert rows[2020]["temp_low_mean"] == pytest.approx(21.0)
    assert rows[2020]["n_days"] == 2
    assert rows[2020]["temperature_mean_method"] == "mixed"
    assert rows[2021]["temperature_mean_method"] == "TAVG"
