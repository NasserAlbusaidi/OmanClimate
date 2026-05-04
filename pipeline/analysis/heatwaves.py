"""Per-year heatwave-run counting.

A "heatwave" is a maximal run of >= ``min_length`` consecutive list
positions where the value exceeds (strict ``>``) ``threshold``. Each
maximal qualifying run counts once, regardless of how much it exceeds
``min_length``.
"""

from __future__ import annotations


def count_runs(values: list[float], threshold: float, min_length: int) -> int:
    """Count maximal runs of length >= ``min_length`` where value > threshold."""
    if min_length < 1:
        raise ValueError(f"min_length must be >= 1, got {min_length}")

    count = 0
    run_len = 0
    for v in values:
        if v is not None and v > threshold:
            run_len += 1
        else:
            if run_len >= min_length:
                count += 1
            run_len = 0
    if run_len >= min_length:
        count += 1
    return count
