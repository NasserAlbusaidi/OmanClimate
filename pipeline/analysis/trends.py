"""Trend statistics with uncertainty.

Per the project methodology (rule 1 — *always show uncertainty*), every
multi-decade trend reported in this project must carry an explicit
confidence band. This module provides the three building blocks:

- ``ols_with_ci``: ordinary least-squares slope + 95 % CI band on the
  regression line (mean-response interval).
- ``theil_sen``: robust slope estimator via scipy ``theilslopes``.
  Reported alongside OLS as a sanity check against outliers.
- ``mann_kendall``: rank-based monotonic-trend significance test via
  scipy ``kendalltau`` applied to (x, y). For an evenly-spaced annual
  series this is equivalent to the Mann-Kendall test (within tied-rank
  handling).

All three return plain dicts so callers can format them into chart
captions without further unpacking.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np
from scipy import stats


class OLSResult(TypedDict):
    slope: float
    intercept: float
    slope_se: float
    p_value: float
    r2: float
    ci_lower: list[float]   # mean-response lower bound at each input x
    ci_upper: list[float]   # mean-response upper bound at each input x
    fitted: list[float]     # ŷ at each input x


class TheilSenResult(TypedDict):
    slope: float
    intercept: float
    slope_lower: float
    slope_upper: float


class MannKendallResult(TypedDict):
    tau: float
    p_value: float
    trend: str  # "increasing" | "decreasing" | "no trend"


def ols_with_ci(x, y, alpha: float = 0.05) -> OLSResult:
    """Linear regression + mean-response CI band on the fitted line.

    The band at point x_i is t_{n-2,1-α/2} · s · sqrt(1/n + (x_i-x̄)² / Σ(x_j-x̄)²)
    around the fitted ŷ_i. This is the *line* CI (uncertainty in the trend
    itself), not a prediction interval for individual observations.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("x and y must be 1-D arrays of equal length")
    n = x.size
    if n < 3:
        raise ValueError(f"need at least 3 points for OLS+CI, got {n}")

    res = stats.linregress(x, y)
    fitted = res.slope * x + res.intercept
    residuals = y - fitted
    sse = float(np.sum(residuals ** 2))
    s = float(np.sqrt(sse / (n - 2)))

    x_mean = float(np.mean(x))
    sxx = float(np.sum((x - x_mean) ** 2))

    se_fit = s * np.sqrt(1.0 / n + (x - x_mean) ** 2 / sxx)
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=n - 2))
    half_width = t_crit * se_fit

    return OLSResult(
        slope=float(res.slope),
        intercept=float(res.intercept),
        slope_se=float(res.stderr),
        p_value=float(res.pvalue),
        r2=float(res.rvalue ** 2),
        ci_lower=(fitted - half_width).tolist(),
        ci_upper=(fitted + half_width).tolist(),
        fitted=fitted.tolist(),
    )


def theil_sen(x, y, alpha: float = 0.05) -> TheilSenResult:
    """Robust slope estimator. Returns slope, intercept, and slope CI bounds."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("x and y must be 1-D arrays of equal length")
    if x.size < 3:
        raise ValueError(f"need at least 3 points for Theil-Sen, got {x.size}")

    res = stats.theilslopes(y, x, alpha=alpha)
    return TheilSenResult(
        slope=float(res.slope),
        intercept=float(res.intercept),
        slope_lower=float(res.low_slope),
        slope_upper=float(res.high_slope),
    )


def mann_kendall(years, values, alpha: float = 0.05) -> MannKendallResult:
    """Monotonic-trend significance via Kendall's tau on (years, values)."""
    x = np.asarray(years, dtype=np.float64)
    y = np.asarray(values, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("years and values must be 1-D arrays of equal length")

    res = stats.kendalltau(x, y)
    tau = float(res.statistic)
    p = float(res.pvalue)

    if p >= alpha:
        trend = "no trend"
    elif tau > 0:
        trend = "increasing"
    else:
        trend = "decreasing"

    return MannKendallResult(tau=tau, p_value=p, trend=trend)
