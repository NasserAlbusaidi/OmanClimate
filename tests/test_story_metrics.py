"""Story-signal analytics for Phase 5."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import polars as pl

from pipeline.analysis.story_metrics import (
    build_story_metrics_payload,
    classify_signal,
    december_cool_snap_story,
    khareef_stress_story,
    mountain_refuge_story,
)
from pipeline.viz.story_metrics import write_story_metrics_data


def _annual_rows() -> pl.DataFrame:
    rows = []
    for slug, label in [
        ("muscat", "Muscat / Seeb"),
        ("sohar", "Sohar"),
        ("saiq", "Saiq"),
    ]:
        for year in range(1980, 1995):
            offset = year - 1980
            tropical = 60 + offset if slug in {"muscat", "sohar"} else 0
            wetbulb = 300 + offset * 20 if slug in {"muscat", "sohar"} else 0
            rows.append(
                {
                    "station_slug": slug,
                    "station_label": label,
                    "latitude": 23.0,
                    "longitude": 58.0,
                    "category": "test",
                    "source_note": "test",
                    "year": year,
                    "temp_high_mean": 34.0,
                    "temp_low_mean": 22.0,
                    "temp_mean_mean": 28.0,
                    "dewpoint_mean_mean": 18.0,
                    "wet_bulb_max_p99": 26.0,
                    "hours_above_30_sum": 1000,
                    "hours_above_35_sum": 500,
                    "hours_above_40_sum": 20,
                    "hours_wetbulb_above_28_sum": wetbulb,
                    "days_overnight_low_above_30": tropical,
                    "n_days": 365,
                    "summer_start": None,
                    "summer_end": None,
                    "summer_length": 60,
                    "heatwaves_3day_above_35": 2,
                    "heatwaves_5day_above_40": 1,
                }
            )
    return pl.DataFrame(rows)


def _daily_rows(station_slug: str) -> pl.DataFrame:
    rows = []
    month_day_counts = {6: 30, 7: 31, 8: 31, 9: 30, 12: 31}
    for year in range(1980, 1995):
        for month, day_count in month_day_counts.items():
            for day in range(1, day_count + 1):
                offset = year - 1980
                is_december = month == 12
                rows.append(
                    {
                        "station_slug": station_slug,
                        "station_label": station_slug.title(),
                        "latitude": 23.0,
                        "longitude": 58.0,
                        "category": "test",
                        "source_note": "test",
                        "date": date(year, month, day),
                        "temp_high": 24.0 + offset * 0.2
                        if is_december
                        else 29.0 + offset * 0.1,
                        "temp_low": 20.0 + offset * 0.25
                        if is_december
                        else 26.0 + offset * 0.1,
                        "temp_mean": 22.0 + offset * 0.2
                        if is_december
                        else 27.0 + offset * 0.1,
                        "dewpoint_mean": 18.0,
                        "wet_bulb_max": 25.0,
                        "hours_above_30": 0,
                        "hours_above_35": 0,
                        "hours_above_40": 0,
                        "hours_wetbulb_above_28": offset
                        if station_slug == "salalah" and month in {6, 7, 8, 9}
                        else 0,
                        "n_hours": 24,
                    }
                )
    return pl.DataFrame(rows)


def test_classify_signal_uses_p_value_and_delta_percent():
    assert classify_signal(trend="increasing", p_value=0.01, delta_percent=30.0) == "strong"
    assert classify_signal(trend="increasing", p_value=0.08, delta_percent=10.0) == "moderate"
    assert classify_signal(trend="no trend", p_value=0.4, delta_percent=4.0) == "watch"
    assert classify_signal(trend="increasing", p_value=0.01, delta_percent=None) == "watch"


def test_december_cool_snap_story_uses_daily_december_metrics():
    story = december_cool_snap_story(_daily_rows("muscat"))

    assert story["slug"] == "december-cool-snap"
    assert story["station_slugs"] == ["muscat"]
    assert story["primary_metric"] == "december_cool_days"
    assert story["latest_value"] < story["baseline_value"]
    assert "daily station parquet" in story["method_note"]


def test_khareef_story_uses_salalah_june_to_september_wetbulb_hours():
    story = khareef_stress_story(_daily_rows("salalah"))

    assert story["slug"] == "khareef-under-stress"
    assert story["station_slugs"] == ["salalah"]
    assert story["primary_metric"] == "khareef_wetbulb_hours"
    assert story["latest_value"] > story["baseline_value"]


def test_mountain_refuge_story_compares_saiq_to_coastal_stations():
    story = mountain_refuge_story(_annual_rows())

    assert story["slug"] == "mountain-refuge"
    assert story["station_slugs"] == ["saiq", "muscat", "sohar"]
    assert story["primary_metric"] == "coastal_minus_saiq_tropical_nights"
    assert story["latest_value"] > 0
    assert "not a controlled rural twin" in story["method_note"]


def test_story_metrics_payload_sorts_stronger_signals_first():
    payload = build_story_metrics_payload(
        annual=_annual_rows(),
        muscat_daily=_daily_rows("muscat"),
        salalah_daily=_daily_rows("salalah"),
    )

    assert payload["fit_start_year"] == 1980
    assert len(payload["stories"]) == 3
    strengths = [story["signal_strength"] for story in payload["stories"]]
    assert strengths == sorted(strengths, key={"strong": 0, "moderate": 1, "watch": 2}.get)


def test_write_story_metrics_data_emits_local_site_js(tmp_path: Path):
    annual_path = tmp_path / "annual.parquet"
    muscat_daily_path = tmp_path / "muscat_daily.parquet"
    salalah_daily_path = tmp_path / "salalah_daily.parquet"
    _annual_rows().write_parquet(annual_path)
    _daily_rows("muscat").write_parquet(muscat_daily_path)
    _daily_rows("salalah").write_parquet(salalah_daily_path)

    out = tmp_path / "story-metrics-data.js"
    result = write_story_metrics_data(
        annual_path,
        muscat_daily_path,
        salalah_daily_path,
        out,
    )

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith("window.OMAN_STORY_METRICS_DATA = ")
    data = json.loads(text.removeprefix("window.OMAN_STORY_METRICS_DATA = ").rstrip(";\n"))
    assert [story["slug"] for story in data["stories"]]
