"""Tests for heatwave run counting."""

from __future__ import annotations

import pytest

from pipeline.analysis.heatwaves import count_runs


def test_single_qualifying_run():
    assert count_runs([36, 36, 36, 30, 38, 38], threshold=35, min_length=3) == 1


def test_one_long_run_counts_once():
    """A 6-day run of >35 counts as ONE heatwave, not two."""
    assert count_runs([36] * 6, threshold=35, min_length=3) == 1


def test_min_length_filters_short_runs():
    """A 3-day run does not qualify as a 4-day heatwave."""
    assert count_runs([36, 36, 36, 30, 36, 36, 36], threshold=35, min_length=4) == 0


def test_two_separated_qualifying_runs():
    vals = [36, 36, 36, 30, 36, 36, 36, 36]
    assert count_runs(vals, threshold=35, min_length=3) == 2


def test_zero_runs_when_all_below():
    assert count_runs([20, 21, 22], threshold=35, min_length=3) == 0


def test_strict_greater_than():
    """Equality to threshold does NOT qualify (rule shared with seasons)."""
    assert count_runs([35, 35, 35, 35], threshold=35, min_length=3) == 0


def test_run_at_end_of_series_counts():
    """Trailing run must be counted even without a closing non-qualifying value."""
    assert count_runs([20, 36, 36, 36], threshold=35, min_length=3) == 1


def test_min_length_must_be_positive():
    with pytest.raises(ValueError):
        count_runs([36, 36], threshold=35, min_length=0)


def test_none_breaks_the_run():
    assert count_runs([36, 36, None, 36, 36], threshold=35, min_length=3) == 0
    assert count_runs([36, 36, 36, None, 36, 36, 36], threshold=35, min_length=3) == 2
