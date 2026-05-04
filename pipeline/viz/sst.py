"""Static-site data export for Sea of Oman SST analytics."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from pipeline.analysis.sst import build_sst_payload


def build_sst_data(
    sst_annual_parquet: Path,
    station_annual_parquet: Path,
    salalah_daily_parquet: Path,
) -> dict:
    """Read parquet inputs and build the SST payload."""
    return build_sst_payload(
        pl.read_parquet(sst_annual_parquet),
        pl.read_parquet(station_annual_parquet),
        pl.read_parquet(salalah_daily_parquet),
    )


def write_sst_data(
    sst_annual_parquet: Path,
    station_annual_parquet: Path,
    salalah_daily_parquet: Path,
    out_path: Path,
) -> Path:
    """Write SST data as JSON or local-file-friendly JavaScript."""
    data = build_sst_data(
        sst_annual_parquet,
        station_annual_parquet,
        salalah_daily_parquet,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True, allow_nan=False)
    if out_path.suffix == ".js":
        out_path.write_text(f"window.OMAN_SST_DATA = {payload};\n", encoding="utf-8")
    else:
        out_path.write_text(f"{payload}\n", encoding="utf-8")
    return out_path
