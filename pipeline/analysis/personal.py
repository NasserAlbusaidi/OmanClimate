"""Phase 4 personal climate comparison helpers."""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from pipeline.stations import STATIONS
from pipeline.viz._common import MIN_DAYS_FOR_TREND, TRUSTWORTHY_FIT_START

GENERATION_YEARS = 30
DEFAULT_BIRTH_YEAR = 1995

PERSONAL_METRICS: tuple[dict[str, str], ...] = (
    {
        "key": "temp_mean_c",
        "column": "temp_mean_mean",
        "label": "Annual mean temperature",
        "unit": "deg C",
        "format": "decimal",
    },
    {
        "key": "tropical_nights",
        "column": "days_overnight_low_above_30",
        "label": "Tropical nights",
        "unit": "days",
        "format": "integer",
    },
    {
        "key": "wetbulb_hours_above_28",
        "column": "hours_wetbulb_above_28_sum",
        "label": "Wet-bulb hours above 28 deg C",
        "unit": "hours",
        "format": "integer",
    },
    {
        "key": "summer_length_days",
        "column": "summer_length",
        "label": "Longest summer run",
        "unit": "days",
        "format": "integer",
    },
    {
        "key": "severe_heatwaves",
        "column": "heatwaves_5day_above_40",
        "label": "Severe heatwaves",
        "unit": "events",
        "format": "integer",
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


def build_personal_payload(annual: pl.DataFrame) -> dict[str, Any]:
    """Build station annual series for browser-side birth-year comparisons."""
    full_years = (
        annual.filter(pl.col("n_days") >= MIN_DAYS_FOR_TREND)
        .filter(pl.col("year") >= TRUSTWORTHY_FIT_START)
        .sort(["station_slug", "year"])
    )
    if full_years.is_empty():
        raise ValueError("No full station years at or after 1980")

    latest_year = int(full_years["year"].max())
    default_birth_year = min(max(DEFAULT_BIRTH_YEAR, TRUSTWORTHY_FIT_START), latest_year)
    stations = []

    for station in STATIONS:
        station_df = full_years.filter(pl.col("station_slug") == station.slug).sort("year")
        series = {metric["key"]: {} for metric in PERSONAL_METRICS}
        for row in station_df.to_dicts():
            year_key = str(int(row["year"]))
            for metric in PERSONAL_METRICS:
                series[metric["key"]][year_key] = _json_number(row.get(metric["column"]))
        stations.append(
            {
                "slug": station.slug,
                "label": station.label,
                "category": station.category,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "series": series,
            }
        )

    return {
        "fit_start_year": TRUSTWORTHY_FIT_START,
        "latest_year": latest_year,
        "generation_years": GENERATION_YEARS,
        "default_birth_year": default_birth_year,
        "metrics": [
            {
                "key": metric["key"],
                "label": metric["label"],
                "unit": metric["unit"],
                "format": metric["format"],
            }
            for metric in PERSONAL_METRICS
        ],
        "stations": stations,
    }


def compare_birth_year(
    payload: dict[str, Any],
    *,
    station_slug: str,
    birth_year: int,
) -> dict[str, Any]:
    """Compare a station birth year to the latest year and 30-year baseline."""
    station = next((item for item in payload["stations"] if item["slug"] == station_slug), None)
    if station is None:
        raise KeyError(f"Unknown station slug {station_slug!r}")

    latest_year = int(payload["latest_year"])
    generation_years = int(payload["generation_years"])
    baseline_year = int(birth_year) - generation_years
    generation_available = baseline_year >= int(payload["fit_start_year"])
    metrics: dict[str, dict[str, Any]] = {}

    for metric in payload["metrics"]:
        key = metric["key"]
        series = station["series"][key]
        birth_value = series.get(str(int(birth_year)))
        latest_value = series.get(str(latest_year))
        baseline_value = series.get(str(baseline_year)) if generation_available else None
        lifetime_delta = None if birth_value is None or latest_value is None else latest_value - birth_value
        generation_delta = None if birth_value is None or baseline_value is None else birth_value - baseline_value
        metrics[key] = {
            "birth_year_value": birth_value,
            "latest_value": latest_value,
            "lifetime_delta": lifetime_delta,
            "generation_baseline_year": baseline_year,
            "generation_baseline_value": baseline_value,
            "generation_delta": generation_delta,
        }

    return {
        "station_slug": station_slug,
        "birth_year": int(birth_year),
        "latest_year": latest_year,
        "generation_available": generation_available,
        "metrics": metrics,
    }
