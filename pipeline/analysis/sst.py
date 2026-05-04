"""Sea of Oman SST association analytics."""

from __future__ import annotations

import math
from typing import Any

import polars as pl
from scipy import stats

from pipeline.analysis.trends import ols_with_ci
from pipeline.fetch.sst import SEA_OF_OMAN_REGION
from pipeline.viz._common import MIN_DAYS_FOR_TREND

SST_FULL_YEAR_MIN_DAYS = 360
SST_ANNUAL_START_YEAR = 1982
SST_BASELINE_LABEL = "1982-2011"
METHOD_NOTE = (
    "Associations compare yearly SST and station humid-heat signals; "
    "they do not prove causation."
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


def _records(frame: pl.DataFrame) -> list[dict[str, Any]]:
    records = []
    for row in frame.to_dicts():
        clean = {}
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                clean[key] = _json_number(value)
            elif hasattr(value, "isoformat"):
                clean[key] = value.isoformat()
            else:
                clean[key] = value
        records.append(clean)
    return records


def _pearson(x: list[float], y: list[float]) -> tuple[float | None, float | None]:
    pairs = [
        (float(left), float(right))
        for left, right in zip(x, y, strict=True)
        if math.isfinite(float(left)) and math.isfinite(float(right))
    ]
    if len(pairs) < 3:
        return None, None

    xs = [left for left, _ in pairs]
    ys = [right for _, right in pairs]
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None, None

    result = stats.pearsonr(xs, ys)
    return _json_number(result.statistic), _json_number(result.pvalue)


def _station_signal(
    station_annual: pl.DataFrame,
    *,
    station_slug: str,
    column: str,
) -> pl.DataFrame:
    return (
        station_annual.filter(
            (pl.col("station_slug") == station_slug)
            & (pl.col("n_days") >= MIN_DAYS_FOR_TREND)
            & pl.col(column).is_not_null()
            & pl.col(column).is_finite()
        )
        .select(["year", pl.col(column).alias("value")])
        .sort("year")
    )


def _salalah_khareef_signal(salalah_daily: pl.DataFrame) -> pl.DataFrame:
    daily = salalah_daily
    if "station_slug" in daily.columns:
        daily = daily.filter(pl.col("station_slug") == "salalah")

    return (
        daily.with_columns(
            [
                pl.col("date").dt.year().alias("year"),
                pl.col("date").dt.month().alias("month"),
            ]
        )
        .filter(
            pl.col("month").is_between(6, 9)
            & pl.col("hours_wetbulb_above_28").is_not_null()
            & pl.col("hours_wetbulb_above_28").is_finite()
        )
        .group_by("year")
        .agg(
            [
                pl.col("hours_wetbulb_above_28").sum().alias("value"),
                pl.col("date").count().cast(pl.Int32).alias("n_days"),
            ]
        )
        .filter(pl.col("n_days") >= 90)
        .select(["year", "value"])
        .sort("year")
    )


def _correlation(
    sst: pl.DataFrame,
    signal: pl.DataFrame,
    *,
    target: str,
    lag_years: int,
) -> dict[str, Any]:
    joined = (
        sst.select(["year", "sst_may_oct_mean"])
        .with_columns((pl.col("year") + lag_years).alias("signal_year"))
        .join(signal, left_on="signal_year", right_on="year", how="inner")
        .drop_nulls(["sst_may_oct_mean", "value"])
        .filter(pl.col("sst_may_oct_mean").is_finite() & pl.col("value").is_finite())
    )
    r, p = _pearson(
        joined["sst_may_oct_mean"].to_list(),
        joined["value"].to_list(),
    )
    return {
        "target": target,
        "sst_metric": "sst_may_oct_mean",
        "lag_years": lag_years,
        "n": joined.height,
        "r": r,
        "p_value": p,
    }


def build_sst_correlations(
    sst_annual: pl.DataFrame,
    station_annual: pl.DataFrame,
    salalah_daily: pl.DataFrame,
) -> list[dict[str, Any]]:
    """Compare May-Oct SST against same-year and next-year heat signals."""
    sst = (
        sst_annual.filter(
            (pl.col("n_days") >= SST_FULL_YEAR_MIN_DAYS)
            & pl.col("sst_may_oct_mean").is_not_null()
            & pl.col("sst_may_oct_mean").is_finite()
        )
        .select(["year", "sst_may_oct_mean"])
        .sort("year")
    )
    signals = [
        (
            "muscat_wetbulb_hours",
            _station_signal(
                station_annual,
                station_slug="muscat",
                column="hours_wetbulb_above_28_sum",
            ),
        ),
        (
            "sohar_wetbulb_hours",
            _station_signal(
                station_annual,
                station_slug="sohar",
                column="hours_wetbulb_above_28_sum",
            ),
        ),
        (
            "muscat_tropical_nights",
            _station_signal(
                station_annual,
                station_slug="muscat",
                column="days_overnight_low_above_30",
            ),
        ),
        (
            "sohar_tropical_nights",
            _station_signal(
                station_annual,
                station_slug="sohar",
                column="days_overnight_low_above_30",
            ),
        ),
        ("salalah_khareef_wetbulb_hours", _salalah_khareef_signal(salalah_daily)),
    ]

    correlations = []
    for target, signal in signals:
        for lag_years in (0, 1):
            correlations.append(
                _correlation(sst, signal, target=target, lag_years=lag_years)
            )
    return correlations


def build_sst_payload(
    sst_annual: pl.DataFrame,
    station_annual: pl.DataFrame,
    salalah_daily: pl.DataFrame,
) -> dict[str, Any]:
    """Build the static-site SST payload."""
    full = (
        sst_annual.filter(pl.col("n_days") >= SST_FULL_YEAR_MIN_DAYS)
        .sort("year")
    )
    if full.is_empty():
        raise ValueError("No full SST years available")

    latest = full.tail(1)
    trend = {
        "metric": "sst_mean",
        "start_year": int(full["year"].min()),
        "slope_per_year": None,
        "slope_c_per_year": None,
        "p_value": None,
        "r2": None,
    }
    fit = full.drop_nulls(["year", "sst_mean"]).filter(pl.col("sst_mean").is_finite())
    if fit.height >= 3:
        ols = ols_with_ci(fit["year"].to_numpy(), fit["sst_mean"].to_numpy())
        trend = {
            "metric": "sst_mean",
            "start_year": int(fit["year"].min()),
            "slope_per_year": _json_number(ols["slope"]),
            "slope_c_per_year": _json_number(ols["slope"]),
            "p_value": _json_number(ols["p_value"]),
            "r2": _json_number(ols["r2"]),
        }

    return {
        "source": "NOAA OISST v2.1",
        "region": {
            "slug": SEA_OF_OMAN_REGION.slug,
            "label": SEA_OF_OMAN_REGION.label,
            "north": SEA_OF_OMAN_REGION.north,
            "south": SEA_OF_OMAN_REGION.south,
            "west": SEA_OF_OMAN_REGION.west,
            "east": SEA_OF_OMAN_REGION.east,
        },
        "annual_start_year": SST_ANNUAL_START_YEAR,
        "baseline": SST_BASELINE_LABEL,
        "latest": _records(latest)[0],
        "trend": trend,
        "years": _records(full),
        "correlations": build_sst_correlations(full, station_annual, salalah_daily),
        "method_note": METHOD_NOTE,
    }
