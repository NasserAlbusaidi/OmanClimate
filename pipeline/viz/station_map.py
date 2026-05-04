"""Data export for the Phase 3 interactive station map."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.analysis.trends import mann_kendall, ols_with_ci
from pipeline.stations import STATIONS
from pipeline.viz._common import MIN_DAYS_FOR_TREND, TRUSTWORTHY_FIT_START


MAP_METRICS: tuple[dict[str, str], ...] = (
    {
        "key": "temp_mean_c",
        "column": "temp_mean_mean",
        "label": "Annual mean temperature",
        "unit": "deg C",
    },
    {
        "key": "tropical_nights",
        "column": "days_overnight_low_above_30",
        "label": "Tropical nights",
        "unit": "days",
    },
    {
        "key": "wetbulb_hours_above_28",
        "column": "hours_wetbulb_above_28_sum",
        "label": "Wet-bulb hours above 28 deg C",
        "unit": "hours",
    },
)


def _json_number(value: Any) -> float | int | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if number.is_integer():
        return int(number)
    return number


def _trend_summary(df: pl.DataFrame, column: str) -> dict[str, float | str | None]:
    fit_df = (
        df.filter(pl.col("year") >= TRUSTWORTHY_FIT_START)
        .drop_nulls(["year", column])
        .sort("year")
    )
    if fit_df.height < 3:
        return {
            "slope_per_year": None,
            "p_value": None,
            "trend": "insufficient data",
        }

    years = fit_df["year"].to_numpy()
    values = fit_df[column].to_numpy()
    ols = ols_with_ci(years, values)
    mk = mann_kendall(years, values)
    return {
        "slope_per_year": _json_number(ols["slope"]),
        "p_value": _json_number(mk["p_value"]),
        "trend": mk["trend"],
    }


def _station_summary(df: pl.DataFrame, station_slug: str) -> dict[str, Any]:
    station = next(station for station in STATIONS if station.slug == station_slug)
    station_df = df.filter(pl.col("station_slug") == station_slug).sort("year")

    latest: dict[str, float | int | None] = {}
    latest_year: int | None = None
    if station_df.height:
        latest_row = station_df.tail(1).to_dicts()[0]
        latest_year = int(latest_row["year"])
        for metric in MAP_METRICS:
            latest[metric["key"]] = _json_number(latest_row.get(metric["column"]))
    else:
        latest = {metric["key"]: None for metric in MAP_METRICS}

    return {
        "slug": station.slug,
        "label": station.label,
        "category": station.category,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "latest_year": latest_year,
        "latest": latest,
        "trends": {
            metric["key"]: _trend_summary(station_df, metric["column"])
            for metric in MAP_METRICS
        },
    }


def build_station_map_data(annual_parquet: Path) -> dict[str, Any]:
    """Build the station summaries consumed by the static site map."""
    annual = (
        pl.read_parquet(annual_parquet)
        .filter(pl.col("n_days") >= MIN_DAYS_FOR_TREND)
        .sort(["station_slug", "year"])
    )
    latitudes = [station.latitude for station in STATIONS]
    longitudes = [station.longitude for station in STATIONS]

    return {
        "fit_start_year": TRUSTWORTHY_FIT_START,
        "min_days_for_trend": MIN_DAYS_FOR_TREND,
        "bounds": {
            "latitude_min": min(latitudes),
            "latitude_max": max(latitudes),
            "longitude_min": min(longitudes),
            "longitude_max": max(longitudes),
        },
        "metrics": [
            {
                "key": metric["key"],
                "label": metric["label"],
                "unit": metric["unit"],
            }
            for metric in MAP_METRICS
        ],
        "stations": [
            _station_summary(annual, station.slug)
            for station in STATIONS
        ],
    }


def write_station_map_data(annual_parquet: Path, out_path: Path) -> Path:
    """Write station-map data as JSON or as local-file-friendly JavaScript."""
    data = build_station_map_data(annual_parquet)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True, allow_nan=False)
    if out_path.suffix == ".js":
        out_path.write_text(
            f"window.OMAN_STATION_MAP_DATA = {payload};\n",
            encoding="utf-8",
        )
    else:
        out_path.write_text(f"{payload}\n", encoding="utf-8")
    return out_path
