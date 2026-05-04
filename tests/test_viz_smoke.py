"""Smoke tests for the visualisation layer.

These verify the *contract* of the viz helpers — that the CI band is
drawn, that legends include the Mann-Kendall p-value, and that the UHI
caveat is reachable on every figure — rather than rendering pixel-by-pixel.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless

import matplotlib.pyplot as plt
import numpy as np
import pytest

from pipeline.viz.style import apply_rcparams, data_stamp, uhi_caveat
from pipeline.viz.trend import plot_with_trend


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


def test_plot_with_trend_emits_band_and_p_value():
    apply_rcparams()
    rng = np.random.default_rng(0)
    years = np.arange(1940, 2020, dtype=float)
    values = 25 + 0.04 * (years - 1940) + rng.normal(0, 0.4, size=years.size)

    fig, ax = plt.subplots()
    info = plot_with_trend(ax, years, values, label="mean temp", color="#c4452f")

    # CI band exists (matplotlib renders fill_between as a PolyCollection)
    from matplotlib.collections import PolyCollection
    polys = [c for c in ax.collections if isinstance(c, PolyCollection)]
    assert polys, "CI band missing — uncertainty rule violated"

    # Legend label includes a p-value annotation
    legend_label = ax.get_legend_handles_labels()[1][0]
    assert "p" in legend_label
    assert "/yr" in legend_label

    # Returned info exposes the MK stats
    assert info["mann_kendall"]["trend"] in {"increasing", "decreasing", "no trend"}


def test_plot_with_trend_theil_sen_path():
    apply_rcparams()
    years = np.arange(1940, 2020, dtype=float)
    values = 0.05 * (years - 1940) + 10
    values[5] += 30  # outlier — Theil-Sen should resist
    values[60] -= 30

    fig, ax = plt.subplots()
    plot_with_trend(ax, years, values, label="x", color="#3d6e8c", fit="theil_sen")

    from matplotlib.collections import PolyCollection
    polys = [c for c in ax.collections if isinstance(c, PolyCollection)]
    assert polys


def test_plot_with_trend_rejects_short_input():
    fig, ax = plt.subplots()
    with pytest.raises(ValueError):
        plot_with_trend(ax, [2000, 2001], [1.0, 2.0], label="x", color="#000")


def test_uhi_caveat_marks_figure():
    fig = plt.figure()
    uhi_caveat(fig)
    assert getattr(fig, "_uhi_caveat_applied", False) is True
    # Caveat text is in the figure-level texts.
    caveat_texts = [t.get_text() for t in fig.texts]
    assert any("urbanisation" in t for t in caveat_texts)


def test_data_stamp_writes_source():
    fig = plt.figure()
    data_stamp(fig)
    stamps = [t.get_text() for t in fig.texts]
    assert any("Open-Meteo" in s for s in stamps)
