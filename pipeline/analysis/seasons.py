"""Per-year longest-run analysis (e.g. summer season start/end/length).

A "season" run is the longest consecutive streak of *list positions*
whose value exceeds a strict threshold. Callers pass the dates and
values together so the boundary dates of the longest run can be
returned. Runs are over consecutive list positions only — gaps in the
``dates`` list (a missing day) terminate the streak.
"""

from __future__ import annotations

from datetime import date


def longest_above_threshold(
    dates: list[date],
    values: list[float],
    threshold: float,
) -> tuple[date | None, date | None, int]:
    """Return (start, end, length) of the longest run where value > threshold.

    Ties are broken by earliest start date. If no value qualifies,
    returns ``(None, None, 0)``.
    """
    if len(dates) != len(values):
        raise ValueError(
            f"dates ({len(dates)}) and values ({len(values)}) must align"
        )

    best_len = 0
    best_start: date | None = None
    best_end: date | None = None

    run_len = 0
    run_start_idx = -1

    for i, v in enumerate(values):
        if v is not None and v > threshold:
            if run_len == 0:
                run_start_idx = i
            run_len += 1
            if run_len > best_len:
                best_len = run_len
                best_start = dates[run_start_idx]
                best_end = dates[i]
        else:
            run_len = 0

    return best_start, best_end, best_len
