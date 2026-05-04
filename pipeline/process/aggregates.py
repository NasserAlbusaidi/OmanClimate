"""Daily and annual aggregations of hourly weather data.

Pipeline contract:

    raw JSON  ─►  hourly polars frame (UTC + Muscat-local cols)
              ─►  daily frame (one row per Asia/Muscat calendar day)
              ─►  annual frame (one row per calendar year)

Hours-above thresholds use strict ``>`` to match common climate-report
conventions ("hours above 35 °C" excludes hours that are exactly 35).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import polars as pl

from pipeline.analysis.heatwaves import count_runs
from pipeline.analysis.seasons import longest_above_threshold
from pipeline.process.timezones import add_muscat_local_columns
from pipeline.process.wet_bulb import stull_wet_bulb

T30 = 30.0
T35 = 35.0
T40 = 40.0
WB28 = 28.0
OVERNIGHT_LOW_THRESHOLD = 30.0
SUMMER_HIGH_THRESHOLD = 35.0
HEATWAVE_MILD_THRESHOLD = 35.0
HEATWAVE_MILD_MIN_DAYS = 3
HEATWAVE_SEVERE_THRESHOLD = 40.0
HEATWAVE_SEVERE_MIN_DAYS = 5


def hourly_from_open_meteo(payload: dict) -> pl.DataFrame:
    """Flatten an Open-Meteo Archive JSON response into a polars frame."""
    hourly = payload["hourly"]
    return pl.DataFrame(
        {
            "time_utc": pl.Series(hourly["time"]).str.to_datetime(
                format="%Y-%m-%dT%H:%M",
                time_unit="us",
            ),
            "temperature_c": hourly["temperature_2m"],
            "dewpoint_c": hourly["dewpoint_2m"],
            "relative_humidity_pct": hourly["relativehumidity_2m"],
        }
    )


def hourly_from_files(paths: Iterable[Path]) -> pl.DataFrame:
    """Concat hourly frames from multiple cached JSON files, sorted by time."""
    import json

    frames = []
    for p in sorted(paths):
        with open(p) as fh:
            frames.append(hourly_from_open_meteo(json.load(fh)))
    if not frames:
        raise ValueError("No raw JSON files supplied to hourly_from_files")
    return (
        pl.concat(frames)
        .unique(subset=["time_utc"], keep="first")
        .sort("time_utc")
    )


def add_wet_bulb(df: pl.DataFrame) -> pl.DataFrame:
    """Compute wet-bulb temp column from temperature + RH."""
    wb = stull_wet_bulb(
        df["temperature_c"].to_numpy(),
        df["relative_humidity_pct"].to_numpy(),
    )
    return df.with_columns(pl.Series("wet_bulb_c", wb))


def build_daily(hourly: pl.DataFrame) -> pl.DataFrame:
    """Aggregate hourly observations to one row per Asia/Muscat day."""
    df = add_muscat_local_columns(hourly)
    df = add_wet_bulb(df)

    return (
        df.group_by("date_local")
        .agg(
            pl.col("temperature_c").max().alias("temp_high"),
            pl.col("temperature_c").min().alias("temp_low"),
            pl.col("temperature_c").mean().alias("temp_mean"),
            pl.col("dewpoint_c").mean().alias("dewpoint_mean"),
            pl.col("wet_bulb_c").max().alias("wet_bulb_max"),
            (pl.col("temperature_c") > T30).sum().cast(pl.Int32).alias("hours_above_30"),
            (pl.col("temperature_c") > T35).sum().cast(pl.Int32).alias("hours_above_35"),
            (pl.col("temperature_c") > T40).sum().cast(pl.Int32).alias("hours_above_40"),
            (pl.col("wet_bulb_c") > WB28).sum().cast(pl.Int32).alias("hours_wetbulb_above_28"),
            pl.col("temperature_c").is_not_null().sum().cast(pl.Int32).alias("n_hours"),
        )
        .rename({"date_local": "date"})
        .sort("date")
    )


def _per_year_derived(daily: pl.DataFrame) -> pl.DataFrame:
    """Compute date-aware per-year metrics: summer start/end/length + heatwave counts.

    Done in Python (not polars expressions) because the run-detection
    functions return tuples and integer counts; trying to express them
    as polars aggregations would obscure the intent.
    """
    rows = []
    df = daily.sort("date")
    for (year,), group in df.group_by(["year"], maintain_order=True):
        dates = group["date"].to_list()
        highs = group["temp_high"].to_list()

        s_start, s_end, s_len = longest_above_threshold(dates, highs, SUMMER_HIGH_THRESHOLD)
        mild = count_runs(highs, HEATWAVE_MILD_THRESHOLD, HEATWAVE_MILD_MIN_DAYS)
        severe = count_runs(highs, HEATWAVE_SEVERE_THRESHOLD, HEATWAVE_SEVERE_MIN_DAYS)

        rows.append(
            {
                "year": int(year),
                "summer_start": s_start,
                "summer_end": s_end,
                "summer_length": s_len,
                "heatwaves_3day_above_35": mild,
                "heatwaves_5day_above_40": severe,
            }
        )

    return pl.DataFrame(
        rows,
        schema={
            "year": pl.Int32,
            "summer_start": pl.Date,
            "summer_end": pl.Date,
            "summer_length": pl.Int32,
            "heatwaves_3day_above_35": pl.Int32,
            "heatwaves_5day_above_40": pl.Int32,
        },
    )


def build_annual(daily: pl.DataFrame) -> pl.DataFrame:
    """Aggregate daily frame to one row per calendar year (Asia/Muscat)."""
    if daily.is_empty():
        raise ValueError("Daily frame is empty; cannot build annual aggregates")

    df = daily.with_columns(pl.col("date").dt.year().alias("year")).sort("date")

    derived = _per_year_derived(df)

    annual = df.group_by("year", maintain_order=True).agg(
        pl.col("temp_high").mean().alias("temp_high_mean"),
        pl.col("temp_low").mean().alias("temp_low_mean"),
        pl.col("temp_mean").mean().alias("temp_mean_mean"),
        pl.col("dewpoint_mean").mean().alias("dewpoint_mean_mean"),
        pl.col("wet_bulb_max").quantile(0.99, "linear").alias("wet_bulb_max_p99"),
        pl.col("hours_above_30").sum().cast(pl.Int32).alias("hours_above_30_sum"),
        pl.col("hours_above_35").sum().cast(pl.Int32).alias("hours_above_35_sum"),
        pl.col("hours_above_40").sum().cast(pl.Int32).alias("hours_above_40_sum"),
        pl.col("hours_wetbulb_above_28").sum().cast(pl.Int32).alias("hours_wetbulb_above_28_sum"),
        (pl.col("temp_low") > OVERNIGHT_LOW_THRESHOLD)
        .sum()
        .cast(pl.Int32)
        .alias("days_overnight_low_above_30"),
        pl.col("date").count().cast(pl.Int32).alias("n_days"),
    ).with_columns(pl.col("year").cast(pl.Int32))

    return annual.join(derived, on="year", how="left").sort("year")


def write_parquet_atomic(df: pl.DataFrame, path: Path) -> None:
    """Write parquet to a temp file then rename — avoids torn writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.write_parquet(tmp)
    tmp.replace(path)
