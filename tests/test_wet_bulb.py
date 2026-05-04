"""Stull 2011 wet-bulb formula — verify against published reference points.

Reference values produced by independently evaluating the Stull formula
(also matches values in the PSU online wet-bulb calculator and the
Climate Toolbox calculator). Tolerance: 0.3 °C (per phase 1 spec).
"""

from __future__ import annotations

import numpy as np
import pytest

from pipeline.process.wet_bulb import stull_wet_bulb

REFERENCE_POINTS = [
    # (T °C, RH %, expected Tw °C) — values produced by Stull's published
    # empirical fit. Tolerance 0.3 °C catches sign / coefficient errors while
    # absorbing rounding in the reference figures.
    (20.0, 50.0, 13.70),
    (20.0, 80.0, 17.49),
    (30.0, 50.0, 22.04),
    (30.0, 70.0, 25.49),
    (40.0, 50.0, 30.89),
    (25.0, 50.0, 17.85),
]
TOLERANCE_C = 0.3


@pytest.mark.parametrize("t,rh,expected", REFERENCE_POINTS)
def test_stull_matches_reference(t, rh, expected):
    got = float(stull_wet_bulb(t, rh))
    assert abs(got - expected) < TOLERANCE_C, (
        f"T={t} RH={rh}: got {got:.3f}, expected {expected:.3f}"
    )


def test_vectorised_matches_scalar():
    ts = np.array([20.0, 30.0, 40.0])
    rhs = np.array([50.0, 50.0, 50.0])
    vec = stull_wet_bulb(ts, rhs)
    for i, (t, rh) in enumerate(zip(ts, rhs)):
        scalar = float(stull_wet_bulb(t, rh))
        assert abs(vec[i] - scalar) < 1e-9


def test_wet_bulb_below_dry_bulb():
    """Physical sanity: wet-bulb must be ≤ dry-bulb at RH<100%."""
    rng = np.random.default_rng(0)
    ts = rng.uniform(-10, 45, size=200)
    rhs = rng.uniform(10, 99, size=200)
    tw = stull_wet_bulb(ts, rhs)
    assert np.all(tw <= ts + 0.05)  # tiny epsilon for empirical-fit slop


def test_nan_propagates():
    assert np.isnan(stull_wet_bulb(np.nan, 50.0))
    assert np.isnan(stull_wet_bulb(20.0, np.nan))
