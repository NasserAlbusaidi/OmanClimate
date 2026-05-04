"""ERA5/Open-Meteo aggregate adapters."""

from __future__ import annotations

import polars as pl

from pipeline.process.common_schema import select_common_annual_columns

ERA5_SOURCE = "era5"
ERA5_STATION_ID = "open-meteo-era5-muscat"
ERA5_STATION_NAME = "Muscat ERA5 grid cell"
ERA5_AGGREGATION_TIMEZONE = "Asia/Muscat"
ERA5_DAY_BOUNDARY = "local calendar day after UTC-to-Muscat conversion"
ERA5_TEMPERATURE_MEAN_METHOD = "mean of hourly 2 m temperature"


def annual_to_common_schema(annual: pl.DataFrame) -> pl.DataFrame:
    """Normalize existing ERA5 annual aggregates to the overlay schema."""
    out = annual.select(
        pl.lit(ERA5_SOURCE).alias("source"),
        pl.lit(ERA5_STATION_ID).alias("station_id"),
        pl.lit(ERA5_STATION_NAME).alias("station_name"),
        pl.col("year"),
        pl.col("temp_mean_mean"),
        pl.col("temp_high_mean"),
        pl.col("temp_low_mean"),
        pl.col("n_days"),
        pl.lit(ERA5_AGGREGATION_TIMEZONE).alias("aggregation_timezone"),
        pl.lit(ERA5_DAY_BOUNDARY).alias("day_boundary"),
        pl.lit(ERA5_TEMPERATURE_MEAN_METHOD).alias("temperature_mean_method"),
    )
    return select_common_annual_columns(out)
