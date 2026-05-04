"""Static-site data export for Phase 5 story signals."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from pipeline.analysis.story_metrics import build_story_metrics_payload


def build_story_metrics_data(
    annual_parquet: Path,
    muscat_daily_parquet: Path,
    salalah_daily_parquet: Path,
) -> dict:
    """Read story input parquet files and build the story metrics payload."""
    return build_story_metrics_payload(
        annual=pl.read_parquet(annual_parquet),
        muscat_daily=pl.read_parquet(muscat_daily_parquet),
        salalah_daily=pl.read_parquet(salalah_daily_parquet),
    )


def write_story_metrics_data(
    annual_parquet: Path,
    muscat_daily_parquet: Path,
    salalah_daily_parquet: Path,
    out_path: Path,
) -> Path:
    """Write story metrics as JSON or local-file-friendly JavaScript."""
    data = build_story_metrics_data(
        annual_parquet,
        muscat_daily_parquet,
        salalah_daily_parquet,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True, allow_nan=False)
    if out_path.suffix == ".js":
        out_path.write_text(
            f"window.OMAN_STORY_METRICS_DATA = {payload};\n",
            encoding="utf-8",
        )
    else:
        out_path.write_text(f"{payload}\n", encoding="utf-8")
    return out_path
