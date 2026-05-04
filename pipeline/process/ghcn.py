"""Process NOAA GHCN-Daily station CSVs into daily and annual aggregates."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from pipeline.fetch.ghcn import SEEB_STATION_ID, normalize_station_id
from pipeline.process.common_schema import select_common_annual_columns

SEEB_STATION_NAME = "Seeb International"
GHCN_SOURCE = "ghcn"
GHCN_AGGREGATION_TIMEZONE = "station-observation-day"
GHCN_DAY_BOUNDARY = "GHCN-Daily station daily summary"

GHCN_COLUMNS = [
    "station_id",
    "date_text",
    "element",
    "value",
    "mflag",
    "qflag",
    "sflag",
    "obs_time",
]
TEMPERATURE_ELEMENTS = ["TAVG", "TMAX", "TMIN"]


def _read_station_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(
        path,
        has_header=False,
        new_columns=GHCN_COLUMNS,
        null_values="",
        schema_overrides={
            "station_id": pl.String,
            "date_text": pl.String,
            "element": pl.String,
            "value": pl.Int32,
            "mflag": pl.String,
            "qflag": pl.String,
            "sflag": pl.String,
            "obs_time": pl.String,
        },
    )


def daily_from_ghcn_csv(
    path: Path,
    *,
    station_id: str = SEEB_STATION_ID,
    station_name: str = SEEB_STATION_NAME,
) -> pl.DataFrame:
    """Build one daily row per GHCN station date.

    Quality-flagged temperature elements are excluded. ``TAVG`` is used when
    present; otherwise the daily mean falls back to ``(TMAX + TMIN) / 2``.
    """
    station_id = normalize_station_id(station_id)
    raw = _read_station_csv(path)
    filtered = (
        raw.filter(
            (pl.col("station_id") == station_id)
            & pl.col("element").is_in(TEMPERATURE_ELEMENTS)
            & (pl.col("value") != -9999)
            & (pl.col("qflag").is_null() | (pl.col("qflag").str.strip_chars() == ""))
        )
        .with_columns(
            pl.col("date_text").str.strptime(pl.Date, "%Y%m%d").alias("date"),
            (pl.col("value").cast(pl.Float64) / 10.0).alias("value_c"),
        )
    )

    if filtered.is_empty():
        return pl.DataFrame(
            schema={
                "source": pl.String,
                "station_id": pl.String,
                "station_name": pl.String,
                "date": pl.Date,
                "temp_high": pl.Float64,
                "temp_low": pl.Float64,
                "temp_mean": pl.Float64,
                "temp_mean_method": pl.String,
                "aggregation_timezone": pl.String,
                "day_boundary": pl.String,
                "n_temperature_elements": pl.Int32,
            }
        )

    daily = filtered.group_by(["station_id", "date"], maintain_order=True).agg(
        pl.col("value_c").filter(pl.col("element") == "TAVG").first().alias("tavg_c"),
        pl.col("value_c").filter(pl.col("element") == "TMAX").first().alias("tmax_c"),
        pl.col("value_c").filter(pl.col("element") == "TMIN").first().alias("tmin_c"),
        pl.col("element").n_unique().cast(pl.Int32).alias("n_temperature_elements"),
    )

    return (
        daily.with_columns(
            pl.when(pl.col("tavg_c").is_not_null())
            .then(pl.col("tavg_c"))
            .when(pl.col("tmax_c").is_not_null() & pl.col("tmin_c").is_not_null())
            .then((pl.col("tmax_c") + pl.col("tmin_c")) / 2.0)
            .otherwise(None)
            .alias("temp_mean"),
            pl.when(pl.col("tavg_c").is_not_null())
            .then(pl.lit("TAVG"))
            .when(pl.col("tmax_c").is_not_null() & pl.col("tmin_c").is_not_null())
            .then(pl.lit("TMAX_TMIN_AVG"))
            .otherwise(None)
            .alias("temp_mean_method"),
        )
        .filter(pl.col("temp_mean").is_not_null())
        .select(
            pl.lit(GHCN_SOURCE).alias("source"),
            pl.col("station_id"),
            pl.lit(station_name).alias("station_name"),
            pl.col("date"),
            pl.col("tmax_c").alias("temp_high"),
            pl.col("tmin_c").alias("temp_low"),
            pl.col("temp_mean"),
            pl.col("temp_mean_method"),
            pl.lit(GHCN_AGGREGATION_TIMEZONE).alias("aggregation_timezone"),
            pl.lit(GHCN_DAY_BOUNDARY).alias("day_boundary"),
            pl.col("n_temperature_elements"),
        )
        .sort("date")
    )


def annual_from_ghcn_daily(daily: pl.DataFrame) -> pl.DataFrame:
    """Aggregate GHCN daily rows to the common annual overlay schema."""
    if daily.is_empty():
        raise ValueError("GHCN daily frame is empty; cannot build annual aggregates")

    df = daily.with_columns(pl.col("date").dt.year().alias("year"))

    methods = (
        df.group_by(
            ["source", "station_id", "station_name", "year"],
            maintain_order=True,
        )
        .agg(
            pl.col("temp_mean_method").n_unique().alias("method_count"),
            pl.col("temp_mean_method").first().alias("first_method"),
        )
        .with_columns(
            pl.when(pl.col("method_count") == 1)
            .then(pl.col("first_method"))
            .otherwise(pl.lit("mixed"))
            .alias("temperature_mean_method")
        )
        .select(
            ["source", "station_id", "station_name", "year", "temperature_mean_method"]
        )
    )

    annual = df.group_by(
        [
            "source",
            "station_id",
            "station_name",
            "year",
            "aggregation_timezone",
            "day_boundary",
        ],
        maintain_order=True,
    ).agg(
        pl.col("temp_mean").mean().alias("temp_mean_mean"),
        pl.col("temp_high").mean().alias("temp_high_mean"),
        pl.col("temp_low").mean().alias("temp_low_mean"),
        pl.col("date").count().cast(pl.Int32).alias("n_days"),
    )

    return (
        annual.join(methods, on=["source", "station_id", "station_name", "year"], how="left")
        .pipe(select_common_annual_columns)
        .sort("year")
    )
