"""Asia/Muscat timezone conversion — UTC+04:00, no DST."""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

from pipeline.process.timezones import (
    MUSCAT_TZ,
    add_muscat_local_columns,
    utc_to_muscat,
)


def test_naive_utc_treated_as_utc():
    naive = datetime(2024, 6, 1, 0, 0)
    out = utc_to_muscat(naive)
    assert out.year == 2024
    assert out.month == 6
    assert out.day == 1
    assert out.hour == 4
    assert out.utcoffset().total_seconds() == 4 * 3600


def test_date_rollover_after_8pm_utc():
    """21:00 UTC → 01:00 next day in Muscat — daily bucketing must follow."""
    utc = datetime(2024, 6, 1, 21, 0, tzinfo=timezone.utc)
    out = utc_to_muscat(utc)
    assert out.day == 2
    assert out.hour == 1


def test_no_dst_in_winter():
    """Muscat does not observe DST; offset is +04:00 year-round."""
    summer = utc_to_muscat(datetime(2024, 7, 15, 12, tzinfo=timezone.utc))
    winter = utc_to_muscat(datetime(2024, 1, 15, 12, tzinfo=timezone.utc))
    assert summer.utcoffset() == winter.utcoffset()


def test_add_muscat_local_columns():
    df = pl.DataFrame(
        {
            "time_utc": [
                datetime(2024, 6, 1, 0, 0),   # → 2024-06-01 04:00 local → date 2024-06-01
                datetime(2024, 6, 1, 21, 0),  # → 2024-06-02 01:00 local → date 2024-06-02
                datetime(2024, 6, 2, 19, 0),  # → 2024-06-02 23:00 local → date 2024-06-02
                datetime(2024, 6, 2, 20, 0),  # → 2024-06-03 00:00 local → date 2024-06-03
            ],
        }
    )
    out = add_muscat_local_columns(df)
    dates = out["date_local"].to_list()
    from datetime import date

    assert dates == [
        date(2024, 6, 1),
        date(2024, 6, 2),
        date(2024, 6, 2),
        date(2024, 6, 3),
    ]
    assert str(out["time_local"].dtype) == "Datetime(time_unit='us', time_zone='Asia/Muscat')"
