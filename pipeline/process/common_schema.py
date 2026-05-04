"""Shared annual schema for overlaying source aggregates."""

from __future__ import annotations

import polars as pl

COMMON_ANNUAL_COLUMNS = [
    "source",
    "station_id",
    "station_name",
    "year",
    "temp_mean_mean",
    "temp_high_mean",
    "temp_low_mean",
    "n_days",
    "aggregation_timezone",
    "day_boundary",
    "temperature_mean_method",
]


def select_common_annual_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Return annual aggregates in the common overlay column order."""
    return df.select(COMMON_ANNUAL_COLUMNS).with_columns(
        pl.col("source").cast(pl.String),
        pl.col("station_id").cast(pl.String),
        pl.col("station_name").cast(pl.String),
        pl.col("year").cast(pl.Int32),
        pl.col("temp_mean_mean").cast(pl.Float64),
        pl.col("temp_high_mean").cast(pl.Float64),
        pl.col("temp_low_mean").cast(pl.Float64),
        pl.col("n_days").cast(pl.Int32),
        pl.col("aggregation_timezone").cast(pl.String),
        pl.col("day_boundary").cast(pl.String),
        pl.col("temperature_mean_method").cast(pl.String),
    )
