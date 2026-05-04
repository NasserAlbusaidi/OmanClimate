"""Sea of Oman SST processing."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pytest
import xarray as xr

from pipeline.process.sst import (
    build_sst_annual,
    daily_sst_from_netcdf_files,
    monthly_sst_from_netcdf_files,
    write_sst_outputs,
)


def _daily_sst(start_year: int = 1982, end_year: int = 2012) -> pl.DataFrame:
    rows = []
    for year in range(start_year, end_year + 1):
        offset = year - start_year
        day = date(year, 1, 1)
        while day.year == year:
            seasonal = 2.0 if 6 <= day.month <= 9 else 0.0
            rows.append({"date": day, "sst_mean": 24.0 + offset * 0.1 + seasonal})
            day += timedelta(days=1)
    return pl.DataFrame(rows)


def test_build_sst_annual_computes_means_seasons_anomaly_and_days():
    annual = build_sst_annual(_daily_sst())

    first = annual.filter(pl.col("year") == 1982).row(0, named=True)
    expected_annual_mean = 24.0 + (122 * 2.0 / 365.0)
    expected_jun_sep_mean = 26.0
    expected_may_oct_mean = (122 * 26.0 + 62 * 24.0) / 184.0

    assert first["n_days"] == 365
    assert abs(first["sst_mean"] - expected_annual_mean) < 1e-9
    assert abs(first["sst_jun_sep_mean"] - expected_jun_sep_mean) < 1e-9
    assert abs(first["sst_may_oct_mean"] - expected_may_oct_mean) < 1e-9
    assert "sst_anomaly_vs_1982_2011" in annual.columns

    baseline = annual.filter(pl.col("year").is_between(1982, 2011))
    assert abs(baseline["sst_anomaly_vs_1982_2011"].mean()) < 1e-9


def test_build_sst_annual_excludes_incomplete_1981_from_annual_claims():
    partial = pl.DataFrame(
        [{"date": date(1981, 9, 1) + timedelta(days=i), "sst_mean": 28.0} for i in range(122)]
    )
    annual = build_sst_annual(pl.concat([partial, _daily_sst(1982, 1983)]))

    assert 1981 not in set(annual["year"])


def test_build_sst_annual_excludes_post_1982_partial_years():
    partial = pl.DataFrame(
        [{"date": date(1983, 1, 1) + timedelta(days=i), "sst_mean": 25.0} for i in range(40)]
    )
    annual = build_sst_annual(pl.concat([_daily_sst(1982, 1982), partial]))

    assert 1982 in set(annual["year"])
    assert 1983 not in set(annual["year"])


def test_build_sst_annual_ignores_nan_sst_values():
    daily = pl.concat(
        [
            _daily_sst(1982, 1982),
            pl.DataFrame(
                [
                    {"date": date(1983, 1, 1) + timedelta(days=i), "sst_mean": float("nan")}
                    for i in range(365)
                ]
            ),
        ]
    )

    annual = build_sst_annual(daily)

    assert 1983 not in set(annual["year"])
    assert annual["sst_mean"].is_nan().sum() == 0
    assert annual["sst_anomaly_vs_1982_2011"].is_nan().sum() == 0


def test_build_sst_annual_weights_monthly_means_by_days():
    rows = []
    for month, days in [(1, 31), (2, 28), (3, 31), (4, 30), (5, 31), (6, 30),
                        (7, 31), (8, 31), (9, 30), (10, 31), (11, 30), (12, 31)]:
        value = 26.0 if 6 <= month <= 9 else 24.0
        rows.append({"date": date(1982, month, 1), "sst_mean": value, "n_days": days})
    monthly = pl.DataFrame(rows)

    annual = build_sst_annual(monthly)
    first = annual.row(0, named=True)

    assert first["n_days"] == 365
    assert abs(first["sst_mean"] - (24.0 + (122 * 2.0 / 365.0))) < 1e-9
    assert abs(first["sst_jun_sep_mean"] - 26.0) < 1e-9
    assert abs(first["sst_may_oct_mean"] - ((122 * 26.0 + 62 * 24.0) / 184.0)) < 1e-9


def test_daily_sst_from_netcdf_files_keeps_only_finite_daily_means(tmp_path: Path):
    path = tmp_path / "sample.nc"
    ds = xr.Dataset(
        {
            "sst": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[25.0, 26.0], [27.0, 28.0]],
                        [[np.nan, np.nan], [np.nan, np.nan]],
                    ]
                ),
            )
        },
        coords={
            "time": pd.date_range("1982-01-01", periods=2, freq="D"),
            "lat": [23.0, 24.0],
            "lon": [57.0, 58.0],
        },
    )
    ds.to_netcdf(path, engine="scipy")

    daily = daily_sst_from_netcdf_files([path])

    assert daily.height == 1
    row = daily.row(0, named=True)
    assert row["date"] == date(1982, 1, 1)
    assert abs(row["sst_mean"] - 26.5) < 1e-9
    assert daily["sst_mean"].is_finite().all()


def test_daily_sst_from_netcdf_files_raises_when_all_values_are_nan(tmp_path: Path):
    path = tmp_path / "all_nan.nc"
    ds = xr.Dataset(
        {
            "sst": (
                ("time", "lat", "lon"),
                np.array([[[np.nan, np.nan], [np.nan, np.nan]]]),
            )
        },
        coords={
            "time": pd.date_range("1982-01-01", periods=1, freq="D"),
            "lat": [23.0, 24.0],
            "lon": [57.0, 58.0],
        },
    )
    ds.to_netcdf(path, engine="scipy")

    with pytest.raises(ValueError, match="No finite SST values found in OISST files"):
        daily_sst_from_netcdf_files([path])


def test_monthly_sst_from_netcdf_files_adds_month_day_weights(tmp_path: Path):
    path = tmp_path / "monthly.nc"
    ds = xr.Dataset(
        {
            "sst": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[25.0, 26.0], [27.0, 28.0]],
                        [[26.0, 27.0], [28.0, 29.0]],
                    ]
                ),
            )
        },
        coords={
            "time": pd.date_range("1982-01-01", periods=2, freq="MS"),
            "lat": [23.0, 24.0],
            "lon": [57.0, 58.0],
        },
    )
    ds.to_netcdf(path, engine="scipy")

    monthly = monthly_sst_from_netcdf_files([path])

    assert monthly["date"].to_list() == [date(1982, 1, 1), date(1982, 2, 1)]
    assert monthly["n_days"].to_list() == [31, 28]
    assert abs(monthly["sst_mean"][0] - 26.5) < 1e-9


def test_build_sst_annual_raises_when_no_finite_baseline_values():
    with pytest.raises(ValueError, match="No finite SST baseline values for 1982-2011"):
        build_sst_annual(_daily_sst(2012, 2012))


def test_write_sst_outputs_writes_monthly_and_annual_parquet(tmp_path: Path):
    out = write_sst_outputs(_daily_sst(1982, 1983), tmp_path)

    assert out.monthly_path == tmp_path / "sea_of_oman_sst_monthly.parquet"
    assert out.annual_path == tmp_path / "sea_of_oman_sst_annual.parquet"
    assert out.monthly_path.exists()
    assert out.annual_path.exists()
