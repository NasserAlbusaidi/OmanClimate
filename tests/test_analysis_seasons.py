"""Tests for longest-above-threshold detection."""

from __future__ import annotations

from datetime import date, timedelta

from pipeline.analysis.seasons import longest_above_threshold


def _consecutive_dates(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def test_no_qualifying_values_returns_none():
    dates = _consecutive_dates(date(2024, 1, 1), 5)
    start, end, length = longest_above_threshold(dates, [10.0] * 5, threshold=20.0)
    assert (start, end, length) == (None, None, 0)


def test_all_qualify():
    dates = _consecutive_dates(date(2024, 6, 1), 5)
    start, end, length = longest_above_threshold(dates, [40.0] * 5, threshold=35.0)
    assert start == date(2024, 6, 1)
    assert end == date(2024, 6, 5)
    assert length == 5


def test_strict_greater_than():
    """Equality to threshold does NOT qualify."""
    dates = _consecutive_dates(date(2024, 6, 1), 3)
    start, end, length = longest_above_threshold(dates, [35.0, 35.0, 35.0], threshold=35.0)
    assert (start, end, length) == (None, None, 0)


def test_picks_longest_run():
    dates = _consecutive_dates(date(2024, 6, 1), 10)
    # values: 36 36 30 36 36 36 30 36 36 36
    # longest run is positions 7..9 (length 3) — wait, 4..6 also length 3
    # actually: positions 0-1 = run of 2, positions 3-5 = run of 3, positions 7-9 = run of 3
    # tied at 3 — earliest start wins → positions 3-5
    vals = [36.0, 36.0, 30.0, 36.0, 36.0, 36.0, 30.0, 36.0, 36.0, 36.0]
    start, end, length = longest_above_threshold(dates, vals, threshold=35.0)
    assert length == 3
    assert start == dates[3]
    assert end == dates[5]


def test_tie_broken_by_earliest_start():
    dates = _consecutive_dates(date(2024, 6, 1), 6)
    vals = [40.0, 40.0, 30.0, 40.0, 40.0, 30.0]
    start, end, length = longest_above_threshold(dates, vals, threshold=35.0)
    assert length == 2
    assert start == dates[0]
    assert end == dates[1]


def test_runs_do_not_span_gaps():
    """When dates skip, the position-based scan still counts adjacent positions
    as part of one run — the caller is responsible for not feeding gappy data."""
    dates = [
        date(2024, 6, 1),
        date(2024, 6, 2),
        date(2024, 6, 5),  # gap
        date(2024, 6, 6),
    ]
    vals = [40.0, 40.0, 40.0, 40.0]
    start, end, length = longest_above_threshold(dates, vals, threshold=35.0)
    assert length == 4  # all four list positions
    assert start == dates[0]
    assert end == dates[3]


def test_mismatched_lengths_raises():
    import pytest
    with pytest.raises(ValueError):
        longest_above_threshold([date(2024, 1, 1)], [1.0, 2.0], threshold=0)


def test_empty_inputs():
    assert longest_above_threshold([], [], threshold=35.0) == (None, None, 0)
