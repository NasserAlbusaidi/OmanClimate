"""Daily + annual aggregates: hand-computed against synthetic inputs."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import polars as pl
import pytest

from pipeline.process.aggregates import (
    build_annual,
    build_daily,
    hourly_from_open_meteo,
)


def _hour(h: int, day_utc: date = date(2024, 6, 1)) -> datetime:
    """Synthetic hour. Note: Muscat is UTC+4 with no DST."""
    return datetime(day_utc.year, day_utc.month, day_utc.day, h, 0)


def _synthetic_payload(temps, dewpoints, rhs, start: datetime):
    times = [
        (start.replace(hour=0) + pl.duration(hours=i)) if False else None
        for i in range(len(temps))
    ]
    # Build the time strings the same way the API formats them.
    iso_times = []
    cur = start
    for _ in temps:
        iso_times.append(cur.strftime("%Y-%m-%dT%H:%M"))
        # advance by one hour
        h = cur.hour + 1
        d = cur
        if h == 24:
            d = d.replace(hour=0)
            d = d.fromordinal(d.toordinal() + 1)
            d = d.replace(hour=0)
        else:
            d = d.replace(hour=h)
        cur = d
    return {
        "hourly": {
            "time": iso_times,
            "temperature_2m": temps,
            "dewpoint_2m": dewpoints,
            "relativehumidity_2m": rhs,
        }
    }


# `_longest_run` was removed in Phase 2 — superseded by
# pipeline.analysis.seasons.longest_above_threshold (which is date-aware
# and tested in tests/test_analysis_seasons.py).


def test_build_daily_one_full_local_day():
    """Construct 24h of UTC data covering one full Asia/Muscat local day.

    Muscat day 2024-06-01 (local 00:00 → 23:59) is 2024-05-31T20:00 UTC
    through 2024-06-01T19:00 UTC. 24 hourly rows in that window.
    """
    # 24 hourly rows, every entry has known temperature/RH/dewpoint.
    # Profile: hot afternoon peak.
    temps = [
        # local hours 00..23
        28, 27, 26, 26, 27, 28, 30, 32, 35, 36, 38, 40,
        41, 42, 41, 39, 36, 33, 31, 30, 29, 29, 28, 28,
    ]
    rhs = [60.0] * 24
    dewpoints = [22.0] * 24

    iso_times = []
    cur = datetime(2024, 5, 31, 20, 0)  # UTC start, = local 2024-06-01 00:00
    for _ in range(24):
        iso_times.append(cur.strftime("%Y-%m-%dT%H:%M"))
        # advance 1h
        if cur.hour == 23:
            cur = datetime(cur.year, cur.month, cur.day, 0, 0).fromordinal(
                cur.toordinal() + 1
            ).replace(hour=0)
        else:
            cur = cur.replace(hour=cur.hour + 1)

    payload = {
        "hourly": {
            "time": iso_times,
            "temperature_2m": temps,
            "dewpoint_2m": dewpoints,
            "relativehumidity_2m": rhs,
        }
    }

    hourly = hourly_from_open_meteo(payload)
    daily = build_daily(hourly)

    # All rows fall in local date 2024-06-01.
    assert daily.height == 1
    row = daily.row(0, named=True)
    assert row["date"] == date(2024, 6, 1)
    assert row["temp_high"] == 42
    assert row["temp_low"] == 26
    assert row["temp_mean"] == pytest.approx(sum(temps) / 24)
    assert row["dewpoint_mean"] == 22.0
    # >30: hours 6..23 minus those that are <=30. Count hand:
    #   28,27,26,26,27,28,30,32,35,36,38,40,41,42,41,39,36,33,31,30,29,29,28,28
    #   strictly >30 → 32,35,36,38,40,41,42,41,39,36,33,31  = 12
    assert row["hours_above_30"] == 12
    # >35 → 36,38,40,41,42,41,39,36 = 8
    assert row["hours_above_35"] == 8
    # >40 → 41,42,41 = 3
    assert row["hours_above_40"] == 3
    assert row["n_hours"] == 24


def test_build_annual_summer_length_and_overnight_lows():
    """Synthetic daily frame to verify summer_length + days_overnight_low_above_30."""
    # Year 2020: a 5-day hot streak then 2 days break then a 3-day streak.
    # Year 2021: one 4-day streak.
    rows = []

    def add(d, high, low):
        rows.append(
            {
                "date": d,
                "temp_high": float(high),
                "temp_low": float(low),
                "temp_mean": (high + low) / 2.0,
                "dewpoint_mean": 20.0,
                "wet_bulb_max": 25.0,
                "hours_above_30": 0,
                "hours_above_35": 0,
                "hours_above_40": 0,
                "hours_wetbulb_above_28": 0,
                "n_hours": 24,
            }
        )

    # 2020
    for i, (h, lo) in enumerate(
        [
            (38, 31),  # streak
            (37, 31),
            (36, 32),
            (40, 33),
            (39, 30),  # 5-day streak >35; low>30 days: 4 (lows 31,31,32,33)
            (33, 28),  # break
            (34, 27),  # break
            (38, 29),  # streak start
            (37, 30),  # not >30
            (36, 31),  # streak end (3 days)
        ]
    ):
        add(date(2020, 6, 1 + i), h, lo)

    # 2021
    for i, (h, lo) in enumerate(
        [
            (36, 31),
            (37, 32),
            (38, 33),
            (37, 31),  # 4-day streak; lows>30: all 4
            (32, 28),
        ]
    ):
        add(date(2021, 7, 1 + i), h, lo)

    daily = pl.DataFrame(rows)
    annual = build_annual(daily)

    out = {r["year"]: r for r in annual.iter_rows(named=True)}
    assert out[2020]["summer_length"] == 5
    assert out[2021]["summer_length"] == 4
    # 2020 lows>30: 31,31,32,33 (in 5-streak) + 31 (in 3-streak) = 5
    assert out[2020]["days_overnight_low_above_30"] == 5
    # 2021 lows>30: 31,32,33,31 = 4
    assert out[2021]["days_overnight_low_above_30"] == 4
    assert out[2020]["n_days"] == 10
    assert out[2021]["n_days"] == 5


def test_build_annual_run_does_not_span_year_boundary():
    """A run of hot days that crosses Dec 31 → Jan 1 must NOT be merged."""
    rows = []
    for i, (d, h) in enumerate(
        [
            (date(2020, 12, 30), 36),
            (date(2020, 12, 31), 37),
            (date(2021, 1, 1), 38),
            (date(2021, 1, 2), 38),
            (date(2021, 1, 3), 30),
        ]
    ):
        rows.append(
            {
                "date": d,
                "temp_high": float(h),
                "temp_low": 28.0,
                "temp_mean": 32.0,
                "dewpoint_mean": 20.0,
                "wet_bulb_max": 25.0,
                "hours_above_30": 0,
                "hours_above_35": 0,
                "hours_above_40": 0,
                "hours_wetbulb_above_28": 0,
                "n_hours": 24,
            }
        )

    annual = build_annual(pl.DataFrame(rows))
    out = {r["year"]: r for r in annual.iter_rows(named=True)}
    assert out[2020]["summer_length"] == 2  # only Dec 30, 31
    assert out[2021]["summer_length"] == 2  # only Jan 1, 2


def test_build_annual_phase2_columns():
    """Phase 2 schema: summer_start/end + heatwave counts."""
    rows = []

    def add(d, high):
        rows.append(
            {
                "date": d,
                "temp_high": float(high),
                "temp_low": 28.0,
                "temp_mean": 32.0,
                "dewpoint_mean": 20.0,
                "wet_bulb_max": 25.0,
                "hours_above_30": 0,
                "hours_above_35": 0,
                "hours_above_40": 0,
                "hours_wetbulb_above_28": 0,
                "n_hours": 24,
            }
        )

    # 2020: 5-day mild streak (>35), then break, then 3-day mild streak.
    #       No 5-day streak above 40 → severe count = 0.
    for i, h in enumerate([38, 37, 36, 40, 39, 33, 34, 38, 37, 36]):
        add(date(2020, 6, 1 + i), h)

    # 2021: a 5-day streak above 40 (severe). Mild count: same streak counts as 1.
    for i, h in enumerate([41, 42, 41, 41, 42, 30, 30]):
        add(date(2021, 7, 1 + i), h)

    annual = build_annual(pl.DataFrame(rows))
    out = {r["year"]: r for r in annual.iter_rows(named=True)}

    # 2020 longest run >35 is days 0-4 (June 1 → June 5)
    assert out[2020]["summer_start"] == date(2020, 6, 1)
    assert out[2020]["summer_end"] == date(2020, 6, 5)
    assert out[2020]["summer_length"] == 5
    # Two mild runs (5-day and 3-day) → count 2; no severe runs.
    assert out[2020]["heatwaves_3day_above_35"] == 2
    assert out[2020]["heatwaves_5day_above_40"] == 0

    # 2021 longest run >35 is the same 5-day stretch (>40 implies >35).
    assert out[2021]["summer_start"] == date(2021, 7, 1)
    assert out[2021]["summer_end"] == date(2021, 7, 5)
    assert out[2021]["summer_length"] == 5
    assert out[2021]["heatwaves_3day_above_35"] == 1
    assert out[2021]["heatwaves_5day_above_40"] == 1


def test_build_annual_summer_dates_null_when_no_qualifying_days():
    rows = [
        {
            "date": date(2020, 1, 1) + timedelta(days=i),
            "temp_high": 20.0,  # never crosses 35
            "temp_low": 10.0,
            "temp_mean": 15.0,
            "dewpoint_mean": 5.0,
            "wet_bulb_max": 12.0,
            "hours_above_30": 0,
            "hours_above_35": 0,
            "hours_above_40": 0,
            "hours_wetbulb_above_28": 0,
            "n_hours": 24,
        }
        for i in range(5)
    ]

    annual = build_annual(pl.DataFrame(rows))
    out = annual.row(0, named=True)
    assert out["summer_length"] == 0
    assert out["summer_start"] is None
    assert out["summer_end"] is None
    assert out["heatwaves_3day_above_35"] == 0
    assert out["heatwaves_5day_above_40"] == 0
