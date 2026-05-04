"""Tests for trend statistics: OLS+CI, Theil-Sen, Mann-Kendall."""

from __future__ import annotations

import numpy as np
import pytest

from pipeline.analysis.trends import mann_kendall, ols_with_ci, theil_sen


def _synthetic_trend(slope=0.05, intercept=10.0, n=80, noise_sd=0.5, seed=0):
    rng = np.random.default_rng(seed)
    x = np.arange(1940, 1940 + n, dtype=float)
    y = intercept + slope * (x - 1940) + rng.normal(0, noise_sd, size=n)
    return x, y


def test_ols_recovers_known_slope():
    x, y = _synthetic_trend(slope=0.05)
    res = ols_with_ci(x, y)
    assert abs(res["slope"] - 0.05) < 0.005
    assert res["p_value"] < 1e-10
    assert res["r2"] > 0.8  # signal/noise of this fixture sits around 0.85-0.90
    # CI band is non-degenerate
    assert all(lo < up for lo, up in zip(res["ci_lower"], res["ci_upper"]))


def test_ols_ci_widens_at_extremes():
    """Mean-response CI is narrower at x̄ than at the edges of the data."""
    x, y = _synthetic_trend()
    res = ols_with_ci(x, y)
    widths = [u - l for l, u in zip(res["ci_lower"], res["ci_upper"])]
    n = len(widths)
    middle_w = widths[n // 2]
    edge_w = max(widths[0], widths[-1])
    assert edge_w > middle_w


def test_ols_constant_series_zero_slope():
    x = np.arange(1940, 2020, dtype=float)
    y = np.full_like(x, 25.0)
    res = ols_with_ci(x, y)
    assert abs(res["slope"]) < 1e-6
    # p-value undefined for zero variance; scipy returns NaN — accept that.
    assert np.isnan(res["p_value"]) or res["p_value"] > 0.5


def test_ols_rejects_short_input():
    with pytest.raises(ValueError):
        ols_with_ci([2000, 2001], [1.0, 2.0])


def test_theil_sen_recovers_slope_under_outliers():
    """Theil-Sen should be ~0.05 even with a couple of bad outliers."""
    x, y = _synthetic_trend(slope=0.05, n=80, noise_sd=0.3, seed=1)
    y[10] += 50  # injected outlier
    y[40] -= 60
    res = theil_sen(x, y)
    assert abs(res["slope"] - 0.05) < 0.01
    assert res["slope_lower"] < res["slope"] < res["slope_upper"]


def test_mann_kendall_detects_trend():
    x, y = _synthetic_trend(slope=0.05, n=60, noise_sd=0.3, seed=2)
    res = mann_kendall(x, y)
    assert res["trend"] == "increasing"
    assert res["p_value"] < 0.001
    assert res["tau"] > 0


def test_mann_kendall_no_trend_on_white_noise():
    rng = np.random.default_rng(3)
    x = np.arange(1940, 2020)
    y = rng.normal(25, 0.5, size=x.size)
    res = mann_kendall(x, y)
    assert res["trend"] == "no trend"
    assert res["p_value"] > 0.05


def test_mann_kendall_decreasing():
    x, y = _synthetic_trend(slope=-0.04, n=60, noise_sd=0.3, seed=4)
    res = mann_kendall(x, y)
    assert res["trend"] == "decreasing"
    assert res["tau"] < 0
