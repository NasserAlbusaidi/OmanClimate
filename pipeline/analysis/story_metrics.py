"""Phase 5 story-signal metrics."""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from pipeline.analysis.trends import mann_kendall
from pipeline.viz._common import MIN_DAYS_FOR_TREND, TRUSTWORTHY_FIT_START

LATEST_WINDOW_YEARS = 10
BASELINE_START = 1980
BASELINE_END = 1989
SIGNAL_ORDER = {"strong": 0, "moderate": 1, "watch": 2}


def _json_number(value: Any) -> float | int | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if number.is_integer():
        return int(number)
    return number


def _delta_percent(delta: float | int | None, baseline: float | int | None) -> float | None:
    if delta is None or baseline is None or baseline == 0:
        return None
    return float(delta / abs(baseline) * 100.0)


def classify_signal(*, trend: str, p_value: float | None, delta_percent: float | None) -> str:
    """Classify story signal strength from trend significance and effect size."""
    if p_value is None or delta_percent is None:
        return "watch"
    if trend in {"increasing", "decreasing"} and p_value < 0.05 and abs(delta_percent) >= 25:
        return "strong"
    if p_value < 0.10 or abs(delta_percent) >= 15:
        return "moderate"
    return "watch"


def _window_summary(frame: pl.DataFrame, metric: str) -> dict[str, float | int | str | None]:
    if frame.is_empty():
        return {
            "latest_year": None,
            "baseline_value": None,
            "latest_value": None,
            "delta": None,
            "delta_percent": None,
            "trend": "no trend",
            "p_value": None,
        }

    latest_year = int(frame["year"].max())
    baseline = frame.filter((pl.col("year") >= BASELINE_START) & (pl.col("year") <= BASELINE_END))
    latest = frame.filter(pl.col("year") >= latest_year - LATEST_WINDOW_YEARS + 1)
    baseline_value = _json_number(baseline[metric].mean()) if baseline.height else None
    latest_value = _json_number(latest[metric].mean()) if latest.height else None
    delta = None if baseline_value is None or latest_value is None else latest_value - baseline_value
    pct = _delta_percent(delta, baseline_value)

    trend = "no trend"
    p_value = None
    fit = frame.filter(pl.col("year") >= TRUSTWORTHY_FIT_START).drop_nulls(["year", metric])
    if fit.height >= 3:
        trend_result = mann_kendall(fit["year"].to_numpy(), fit[metric].to_numpy())
        p_value = _json_number(trend_result["p_value"])
        trend = trend_result["trend"] if p_value is not None else "no trend"

    return {
        "latest_year": latest_year,
        "baseline_value": baseline_value,
        "latest_value": latest_value,
        "delta": _json_number(delta),
        "delta_percent": _json_number(pct),
        "trend": trend,
        "p_value": p_value,
    }


def _metric_series(frame: pl.DataFrame, metric: str) -> list[dict[str, float | int | None]]:
    """Return compact year/value pairs for browser-side selected-year deltas."""
    return [
        {"year": int(row["year"]), "value": _json_number(row[metric])}
        for row in frame.select(["year", metric]).sort("year").to_dicts()
    ]


def december_cool_snap_story(muscat_daily: pl.DataFrame) -> dict[str, Any]:
    """Summarize December cool-day loss at Muscat."""
    df = (
        muscat_daily.with_columns(
            [
                pl.col("date").dt.year().alias("year"),
                pl.col("date").dt.month().alias("month"),
            ]
        )
        .filter((pl.col("year") >= TRUSTWORTHY_FIT_START) & (pl.col("month") == 12))
        .group_by("year")
        .agg(
            [
                (pl.col("temp_high") < 25).sum().cast(pl.Int32).alias("december_cool_days"),
                (pl.col("temp_low") > 22).sum().cast(pl.Int32).alias("december_warm_nights"),
                pl.col("date").count().cast(pl.Int32).alias("n_days"),
            ]
        )
        .filter(pl.col("n_days") >= 25)
        .sort("year")
    )
    summary = _window_summary(df, "december_cool_days")
    strength = classify_signal(
        trend=str(summary["trend"]),
        p_value=summary["p_value"],
        delta_percent=summary["delta_percent"],
    )
    return {
        "slug": "december-cool-snap",
        "title": "The death of the December cool snap",
        "station_slugs": ["muscat"],
        "summary": "December cool days at Muscat compared with the 1980s baseline.",
        "signal_strength": strength,
        "primary_metric": "december_cool_days",
        "latest_value": summary["latest_value"],
        "baseline_value": summary["baseline_value"],
        "delta": summary["delta"],
        "delta_percent": summary["delta_percent"],
        "series": _metric_series(df, "december_cool_days"),
        "trend": summary["trend"],
        "p_value": summary["p_value"],
        "method_note": "Uses Muscat daily station parquet; December cool day means temp_high < 25 deg C.",
    }


def khareef_stress_story(salalah_daily: pl.DataFrame) -> dict[str, Any]:
    """Summarize Jun-Sep humid-heat exposure at Salalah."""
    df = (
        salalah_daily.with_columns(
            [
                pl.col("date").dt.year().alias("year"),
                pl.col("date").dt.month().alias("month"),
            ]
        )
        .filter((pl.col("year") >= TRUSTWORTHY_FIT_START) & (pl.col("month").is_between(6, 9)))
        .group_by("year")
        .agg(
            [
                pl.col("temp_mean").mean().alias("khareef_temp_mean"),
                pl.col("hours_wetbulb_above_28").sum().cast(pl.Int32).alias("khareef_wetbulb_hours"),
                (pl.col("temp_low") > 28).sum().cast(pl.Int32).alias("khareef_hot_nights"),
                pl.col("date").count().cast(pl.Int32).alias("n_days"),
            ]
        )
        .filter(pl.col("n_days") >= 90)
        .sort("year")
    )
    summary = _window_summary(df, "khareef_wetbulb_hours")
    strength = classify_signal(
        trend=str(summary["trend"]),
        p_value=summary["p_value"],
        delta_percent=summary["delta_percent"],
    )
    return {
        "slug": "khareef-under-stress",
        "title": "Khareef under stress in Salalah",
        "station_slugs": ["salalah"],
        "summary": "Jun-Sep wet-bulb heat exposure in Salalah compared with the 1980s baseline.",
        "signal_strength": strength,
        "primary_metric": "khareef_wetbulb_hours",
        "latest_value": summary["latest_value"],
        "baseline_value": summary["baseline_value"],
        "delta": summary["delta"],
        "delta_percent": summary["delta_percent"],
        "series": _metric_series(df, "khareef_wetbulb_hours"),
        "trend": summary["trend"],
        "p_value": summary["p_value"],
        "method_note": "Uses Salalah daily station parquet; khareef window is June 1 through September 30.",
    }


def mountain_refuge_story(annual: pl.DataFrame) -> dict[str, Any]:
    """Compare Saiq 30°C nights with coastal Muscat and Sohar."""
    full = annual.filter(
        (pl.col("n_days") >= MIN_DAYS_FOR_TREND) & (pl.col("year") >= TRUSTWORTHY_FIT_START)
    )
    coastal = (
        full.filter(pl.col("station_slug").is_in(["muscat", "sohar"]))
        .group_by("year")
        .agg(pl.col("days_overnight_low_above_30").mean().alias("coastal_tropical_nights"))
    )
    saiq = full.filter(pl.col("station_slug") == "saiq").select(
        ["year", pl.col("days_overnight_low_above_30").alias("saiq_tropical_nights")]
    )
    comparison = (
        coastal.join(saiq, on="year", how="inner")
        .with_columns(
            (pl.col("coastal_tropical_nights") - pl.col("saiq_tropical_nights")).alias(
                "coastal_minus_saiq_tropical_nights"
            )
        )
        .sort("year")
    )
    summary = _window_summary(comparison, "coastal_minus_saiq_tropical_nights")
    strength = classify_signal(
        trend=str(summary["trend"]),
        p_value=summary["p_value"],
        delta_percent=summary["delta_percent"],
    )
    return {
        "slug": "mountain-refuge",
        "title": "The mountains: Oman's last cool refuge?",
        "station_slugs": ["saiq", "muscat", "sohar"],
        "summary": "Saiq 30°C nights compared with coastal Muscat and Sohar.",
        "signal_strength": strength,
        "primary_metric": "coastal_minus_saiq_tropical_nights",
        "latest_value": summary["latest_value"],
        "baseline_value": summary["baseline_value"],
        "delta": summary["delta"],
        "delta_percent": summary["delta_percent"],
        "series": _metric_series(comparison, "coastal_minus_saiq_tropical_nights"),
        "trend": summary["trend"],
        "p_value": summary["p_value"],
        "method_note": "Saiq is a mountain/refuge comparator, not a controlled rural twin for Muscat.",
    }


def _story_sort_key(story: dict[str, Any]) -> tuple[int, float]:
    strength = SIGNAL_ORDER[story["signal_strength"]]
    pct = story["delta_percent"]
    magnitude = -abs(float(pct)) if pct is not None else 0.0
    return strength, magnitude


def build_story_metrics_payload(
    *,
    annual: pl.DataFrame,
    muscat_daily: pl.DataFrame,
    salalah_daily: pl.DataFrame,
) -> dict[str, Any]:
    """Build sorted story signal cards for the static site."""
    stories = [
        december_cool_snap_story(muscat_daily),
        khareef_stress_story(salalah_daily),
        mountain_refuge_story(annual),
    ]
    full = annual.filter(pl.col("n_days") >= MIN_DAYS_FOR_TREND)
    latest_year = int(full["year"].max()) if not full.is_empty() else None
    return {
        "fit_start_year": TRUSTWORTHY_FIT_START,
        "latest_year": latest_year,
        "stories": sorted(stories, key=_story_sort_key),
    }
