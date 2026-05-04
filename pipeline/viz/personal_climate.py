"""Static-site data export for Phase 4 personal climate comparisons."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from pipeline.analysis.personal import build_personal_payload


def build_personal_climate_data(annual_parquet: Path) -> dict:
    """Read station annual parquet and build the personal climate payload."""
    return build_personal_payload(pl.read_parquet(annual_parquet))


def write_personal_climate_data(annual_parquet: Path, out_path: Path) -> Path:
    """Write personal climate data as JSON or local-file-friendly JavaScript."""
    data = build_personal_climate_data(annual_parquet)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True, allow_nan=False)
    if out_path.suffix == ".js":
        out_path.write_text(
            f"window.OMAN_PERSONAL_CLIMATE_DATA = {payload};\n",
            encoding="utf-8",
        )
    else:
        out_path.write_text(f"{payload}\n", encoding="utf-8")
    return out_path
