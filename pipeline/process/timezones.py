"""Timezone conversion utilities.

The pipeline fetches data in UTC from Open-Meteo and converts to
Asia/Muscat (UTC+04:00, no DST) before any daily bucketing. This module
isolates that conversion so the rule is testable and visible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import polars as pl

MUSCAT_TZ = ZoneInfo("Asia/Muscat")
UTC = timezone.utc


def utc_to_muscat(ts: datetime) -> datetime:
    """Convert a single datetime to Asia/Muscat.

    Naive datetimes are assumed to be UTC.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(MUSCAT_TZ)


def add_muscat_local_columns(
    df: pl.DataFrame,
    utc_col: str = "time_utc",
    local_col: str = "time_local",
    date_col: str = "date_local",
) -> pl.DataFrame:
    """Attach Asia/Muscat local time and local-calendar-date columns.

    The Open-Meteo Archive API returns ISO timestamps without zone
    annotation when ``timezone=GMT`` is requested; we treat them as UTC.
    """
    return df.with_columns(
        pl.col(utc_col).dt.replace_time_zone("UTC").alias(utc_col),
    ).with_columns(
        pl.col(utc_col).dt.convert_time_zone("Asia/Muscat").alias(local_col),
    ).with_columns(
        pl.col(local_col).dt.date().alias(date_col),
    )
