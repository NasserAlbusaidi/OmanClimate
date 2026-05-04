"""Tests for the data-quality diagnostic helpers."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from pipeline.diagnostics.step_changes import first_differences, step_test
from pipeline.diagnostics.windows import (
    compare_windows,
    find_window_dependent_metrics,
)


def test_first_differences_shapes():
    years = np.array([2000, 2001, 2002, 2003], dtype=float)
    values = np.array([10.0, 11.0, 13.0, 12.0])
    x_diff, dy = first_differences(years, values)
    assert list(x_diff) == [2001, 2002, 2003]
    assert list(dy) == pytest.approx([1.0, 2.0, -1.0])


def test_step_test_detects_jump():
    # 10 years cool, then 10 years 2 °C warmer → strong significant step.
    years = np.arange(1970, 1990, dtype=float)
    values = np.concatenate([np.full(10, 25.0), np.full(10, 27.0)]) + np.random.RandomState(0).normal(0, 0.05, 20)
    res = step_test(years, values, boundary=1980, window=10)
    assert res["interpretable"] is True
    assert abs(res["delta"] - 2.0) < 0.1
    assert res["p_value"] < 1e-10


def test_step_test_no_jump_on_smooth_data():
    rng = np.random.RandomState(1)
    years = np.arange(1970, 1990, dtype=float)
    values = 25 + 0.01 * (years - 1980) + rng.normal(0, 0.3, size=20)
    res = step_test(years, values, boundary=1980, window=10)
    # Trend is real but no localised jump → p should not be tiny.
    assert res["p_value"] > 0.001


def test_step_test_uninterpretable_at_window_edge():
    years = np.array([2010.0, 2011.0])
    values = np.array([25.0, 26.0])
    res = step_test(years, values, boundary=1980, window=10)
    assert res["interpretable"] is False


def test_compare_windows_table_shape(tmp_path):
    # Tiny synthetic annual frame matching the parquet schema.
    n = 80
    years = np.arange(1940, 1940 + n)
    df = pl.DataFrame(
        {
            "year": years.astype(np.int32),
            "n_days": np.full(n, 365, dtype=np.int32),
            "temp_mean_mean": 27 + 0.02 * (years - 1940),
            "temp_high_mean": np.full(n, 33.0),
            "temp_low_mean": np.full(n, 22.0),
            "hours_above_35_sum": np.full(n, 800, dtype=np.int32),
            "hours_above_40_sum": np.full(n, 100, dtype=np.int32),
            "hours_wetbulb_above_28_sum": np.full(n, 50, dtype=np.int32),
            "days_overnight_low_above_30": np.full(n, 30, dtype=np.int32),
            "summer_length": np.full(n, 60, dtype=np.int32),
            "heatwaves_3day_above_35": np.full(n, 8, dtype=np.int32),
            "heatwaves_5day_above_40": np.full(n, 1, dtype=np.int32),
        }
    )
    p = tmp_path / "tiny.parquet"
    df.write_parquet(p)

    out = compare_windows(p)
    assert {"metric", "window", "n", "slope_per_yr", "p_value"} <= set(out.columns)
    # Each metric appears once per window with at least 3 points.
    assert out.height >= 4 * 3  # 10 metrics × ≥3 windows; some windows may drop short
    # temp_mean_mean's slope should be close to 0.02 across all windows.
    temp_rows = out.filter(pl.col("metric") == "temp_mean_mean")
    for slope in temp_rows["slope_per_yr"].to_list():
        assert abs(slope - 0.02) < 0.01


def test_find_window_dependent_metrics_empty_when_consistent():
    # All-consistent table: same slope sign, same significance.
    table = pl.DataFrame(
        {
            "metric": ["a"] * 4,
            "window": ["full", "post-1950", "post-1979", "post-2000"],
            "n": [80, 70, 50, 25],
            "slope_per_yr": [0.05, 0.05, 0.05, 0.05],
            "p_value": [0.001, 0.001, 0.001, 0.001],
            "trend": ["increasing"] * 4,
            "r2": [0.7] * 4,
        }
    )
    assert find_window_dependent_metrics(table) == []


def test_find_window_dependent_metrics_flags_sign_flip():
    table = pl.DataFrame(
        {
            "metric": ["a"] * 4,
            "window": ["full", "post-1950", "post-1979", "post-2000"],
            "n": [80, 70, 50, 25],
            "slope_per_yr": [-0.02, 0.01, 0.05, 0.06],
            "p_value": [0.5, 0.1, 0.001, 0.001],
            "trend": ["no trend"] * 4,
            "r2": [0.1] * 4,
        }
    )
    flagged = find_window_dependent_metrics(table)
    assert len(flagged) == 1
    assert flagged[0]["sign_flips"] is True
