"""Detect step changes in the annual series at known reanalysis boundaries.

ERA5 began assimilating satellite data globally in 1979. The reanalysis
back-extension to 1940 (released in 2018) has notably looser constraints
in the Gulf pre-1950, where weather stations were sparse. The handover
between ERA5's main run and its real-time extension (ERA5T) sits around
2015-2017 and is a documented small-discontinuity candidate.

We use a Welch's t-test on the pre/post means around each boundary as a
crude but defensible discontinuity probe. A meaningful step (delta large,
p small) is evidence of a non-climatic break in the series.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats

# Candidate discontinuity boundaries.
BOUNDARIES = [
    (1950, "ERA5 pre-1950 sparse-observation regime ends"),
    (1979, "Satellite-era data assimilation begins"),
    (2015, "ERA5/ERA5T handover (approximate)"),
]


def first_differences(years: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (years[1:], y[n] − y[n−1])."""
    return years[1:], np.diff(values)


def step_test(years: np.ndarray, values: np.ndarray, boundary: int, window: int = 10) -> dict:
    """Welch's t-test on mean(values) before vs after a boundary.

    ``window`` is the number of years on each side included in the test.
    We use a *symmetric local* window rather than the full pre/post halves
    to localise the discontinuity probe and avoid being dominated by long-run
    climate trend.
    """
    mask_before = (years >= boundary - window) & (years < boundary)
    mask_after = (years >= boundary) & (years < boundary + window)
    before = values[mask_before]
    after = values[mask_after]
    if before.size < 3 or after.size < 3:
        return {
            "boundary": boundary,
            "n_before": int(before.size),
            "n_after": int(after.size),
            "delta": float("nan"),
            "p_value": float("nan"),
            "interpretable": False,
        }
    res = stats.ttest_ind(before, after, equal_var=False)
    return {
        "boundary": boundary,
        "n_before": int(before.size),
        "n_after": int(after.size),
        "mean_before": float(before.mean()),
        "mean_after": float(after.mean()),
        "delta": float(after.mean() - before.mean()),
        "p_value": float(res.pvalue),
        "interpretable": True,
    }


def scan_boundaries(annual_parquet: Path, metric: str = "temp_mean_mean") -> pl.DataFrame:
    """Run step-tests for every boundary on a given metric."""
    df = pl.read_parquet(annual_parquet).filter(pl.col("n_days") >= 360).sort("year")
    years = df["year"].to_numpy().astype(float)
    values = df[metric].to_numpy().astype(float)

    rows = []
    for boundary, _label in BOUNDARIES:
        rows.append(step_test(years, values, boundary))
    return pl.DataFrame(rows)
