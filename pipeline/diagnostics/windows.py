"""Compare trend fits across multiple time windows.

A linear regression through a U-shaped series produces a "significant"
slope that is a mathematical artifact of fitting a straight line to a
curve. This module fits each metric over (full, post-1950, post-1979,
post-2000) windows and reports slope + p-value + n for each.

If a metric's slope flips sign or its p-value crosses 0.05 between
windows, the underlying fit is window-dependent — i.e., the signal you
think you're seeing isn't robust to data-quality assumptions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from pipeline.analysis.trends import mann_kendall, ols_with_ci

# Windows to compare. ``None`` means "use the full series".
WINDOWS: list[tuple[str, int | None]] = [
    ("full (1940→)", None),
    ("post-1950", 1950),
    ("post-1979 (satellite era)", 1979),
    ("post-2000", 2000),
]

# Metrics worth window-stress-testing. Wet-bulb hours is here so we can
# *confirm* its post-1980 trend survives the cut (we expect it to).
METRICS = [
    "temp_mean_mean",
    "temp_high_mean",
    "temp_low_mean",
    "hours_above_35_sum",
    "hours_above_40_sum",
    "hours_wetbulb_above_28_sum",
    "days_overnight_low_above_30",
    "summer_length",
    "heatwaves_3day_above_35",
    "heatwaves_5day_above_40",
]


def compare_windows(annual_parquet: Path) -> pl.DataFrame:
    """For each metric × window, fit OLS + Mann-Kendall and return one row."""
    df = pl.read_parquet(annual_parquet).filter(pl.col("n_days") >= 360)

    rows = []
    for metric in METRICS:
        for label, cutoff in WINDOWS:
            sub = df if cutoff is None else df.filter(pl.col("year") >= cutoff)
            x = sub["year"].to_numpy().astype(float)
            y = sub[metric].to_numpy().astype(float)
            mask = np.isfinite(x) & np.isfinite(y)
            x, y = x[mask], y[mask]
            if x.size < 3:
                continue
            ols = ols_with_ci(x, y)
            mk = mann_kendall(x, y)
            rows.append(
                {
                    "metric": metric,
                    "window": label,
                    "n": int(x.size),
                    "slope_per_yr": round(ols["slope"], 4),
                    "p_value": round(mk["p_value"], 4),
                    "trend": mk["trend"],
                    "r2": round(ols["r2"], 3),
                }
            )

    return pl.DataFrame(rows)


def find_window_dependent_metrics(table: pl.DataFrame) -> list[dict]:
    """Flag metrics where slope sign flips or p crosses 0.05 across windows."""
    flagged = []
    for metric in table["metric"].unique().to_list():
        sub = table.filter(pl.col("metric") == metric)
        slopes = sub["slope_per_yr"].to_list()
        ps = sub["p_value"].to_list()
        signs = {1 if s > 0 else (-1 if s < 0 else 0) for s in slopes}
        sig_changes = any(p < 0.05 for p in ps) and any(p >= 0.05 for p in ps)
        if len(signs - {0}) > 1 or sig_changes:
            flagged.append(
                {
                    "metric": metric,
                    "sign_flips": len(signs - {0}) > 1,
                    "significance_crosses": sig_changes,
                }
            )
    return flagged
