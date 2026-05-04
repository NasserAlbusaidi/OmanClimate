"""Shared helpers for chart entry-points."""

from __future__ import annotations

from pathlib import Path

import polars as pl

# Years with fewer than this many observed days are dropped from trend charts
# (current calendar year, very early reanalysis edges). Documented in the
# methodology page.
MIN_DAYS_FOR_TREND = 360

# Trustworthy fit window. Pre-1980 points are still plotted (in muted style)
# so readers can see the artifact, but they do not feed the trend estimate.
#
# Rationale, evidenced in `pipeline/diagnostics/`:
# - Welch's t-test on annual mean temperature shows a -1.1 °C step at 1950
#   with p < 1e-6 — climate doesn't move that fast; this is reanalysis
#   instability when very few observations were constraining the model.
# - The 1979 boundary (start of global satellite data assimilation) shows
#   no significant local discontinuity (p = 0.11), so post-1979 is the
#   first window where the series is internally consistent.
# - Slope of mean temp triples between full and post-1979 windows; flips
#   sign for several threshold metrics. The pre-1980 data is dragging
#   trends with no climatic justification.
TRUSTWORTHY_FIT_START = 1980


def load_full_years(annual_parquet: Path) -> pl.DataFrame:
    annual = pl.read_parquet(annual_parquet)
    return annual.filter(pl.col("n_days") >= MIN_DAYS_FOR_TREND).sort("year")
