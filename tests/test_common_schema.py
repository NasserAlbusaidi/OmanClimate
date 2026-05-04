"""Common annual schema used to overlay source aggregates."""

from __future__ import annotations

import polars as pl

from pipeline.process.common_schema import COMMON_ANNUAL_COLUMNS
from pipeline.process.era5 import annual_to_common_schema


def test_era5_annual_to_common_schema_keeps_overlay_columns_in_order():
    annual = pl.DataFrame(
        {
            "year": [2020],
            "temp_high_mean": [33.0],
            "temp_low_mean": [24.0],
            "temp_mean_mean": [28.5],
            "n_days": [366],
        }
    )

    out = annual_to_common_schema(annual)
    row = out.row(0, named=True)

    assert out.columns == COMMON_ANNUAL_COLUMNS
    assert row["source"] == "era5"
    assert row["station_id"] == "open-meteo-era5-muscat"
    assert row["station_name"] == "Muscat ERA5 grid cell"
    assert row["year"] == 2020
    assert row["temp_mean_mean"] == 28.5
    assert row["aggregation_timezone"] == "Asia/Muscat"
    assert row["day_boundary"] == "local calendar day after UTC-to-Muscat conversion"
    assert row["temperature_mean_method"] == "mean of hourly 2 m temperature"
