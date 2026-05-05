"""Diagnostic charts for the data-quality investigation.

These visualise the artifacts directly so the methodology page can
point to evidence: U-shape contour from ERA5 reanalysis instability,
boundary-discontinuity probes, and urban/rural difference plots.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from pipeline.analysis.trends import mann_kendall, ols_with_ci
from pipeline.diagnostics.step_changes import BOUNDARIES, first_differences
from pipeline.diagnostics.windows import WINDOWS
from pipeline.viz.style import PALETTE, apply_rcparams, data_stamp, uhi_caveat


def render_window_comparison(annual_parquet: Path, out_path: Path) -> None:
    """For four key metrics, overlay the OLS fits from each window."""
    apply_rcparams()
    df = pl.read_parquet(annual_parquet).filter(pl.col("n_days") >= 360).sort("year")
    years_full = df["year"].to_numpy().astype(float)

    metrics = [
        ("hours_above_35_sum", "hours > 35 °C", PALETTE["above_35"]),
        ("hours_wetbulb_above_28_sum", "hours wet-bulb > 28 °C", PALETTE["wetbulb_above_28"]),
        ("days_overnight_low_above_30", "30 °C nights", PALETTE["tropical_nights"]),
        ("heatwaves_5day_above_40", "severe heatwaves (≥5d > 40 °C)", PALETTE["heatwave_severe"]),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)

    window_styles = [
        ("full (1940-)", None, "#999999", "--"),
        ("post-1950", 1950, "#666666", "-."),
        ("post-1979 (sat era)", 1979, "#333333", "-"),
        ("post-2000", 2000, "#000000", ":"),
    ]

    for ax, (col, label, color) in zip(axes.flat, metrics):
        values = df[col].to_numpy().astype(float)
        ax.plot(
            years_full, values,
            marker="o", markersize=2.5, linewidth=0.6, color=color, alpha=0.5,
        )

        for win_label, cutoff, line_color, ls in window_styles:
            mask = years_full >= cutoff if cutoff else np.ones_like(years_full, dtype=bool)
            x = years_full[mask]
            y = values[mask]
            if x.size < 3:
                continue
            ols = ols_with_ci(x, y)
            mk = mann_kendall(x, y)
            p_str = "<0.001" if mk["p_value"] < 0.001 else f"{mk['p_value']:.2f}"
            ax.plot(
                x, ols["fitted"],
                color=line_color, linestyle=ls, linewidth=1.5,
                label=f"{win_label}: {ols['slope']:+.3f}/yr (p={p_str})",
            )

        ax.set_title(label)
        ax.legend(fontsize=7, loc="upper left")
        ax.grid(alpha=0.25)

    fig.suptitle(
        "Window-stress test — does the trend survive a window cut?\n"
        "(if the slope flips sign or significance changes, the fit is window-dependent)",
        fontsize=12, y=0.995,
    )
    for ax in axes[-1, :]:
        ax.set_xlabel("year")

    fig.subplots_adjust(bottom=0.10)
    uhi_caveat(fig)
    data_stamp(fig)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def render_first_differences(annual_parquet: Path, out_path: Path) -> None:
    """Year-over-year differences for temperature with reanalysis-boundary markers."""
    apply_rcparams()
    df = pl.read_parquet(annual_parquet).filter(pl.col("n_days") >= 360).sort("year")
    years = df["year"].to_numpy().astype(float)

    metrics = [
        ("temp_mean_mean", "Δ annual mean temp"),
        ("hours_above_35_sum", "Δ hours > 35 °C"),
        ("days_overnight_low_above_30", "Δ 30 °C nights"),
        ("hours_wetbulb_above_28_sum", "Δ hours wet-bulb > 28"),
    ]

    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
    for ax, (col, ylabel) in zip(axes, metrics):
        values = df[col].to_numpy().astype(float)
        x_diff, dy = first_differences(years, values)
        ax.bar(x_diff, dy, color="#444", width=0.7, alpha=0.7)
        ax.axhline(0, color="#000", linewidth=0.8)
        for boundary, _ in BOUNDARIES:
            ax.axvline(boundary, color="#c4452f", linewidth=1.2, alpha=0.6, linestyle="--")
            ax.text(
                boundary, ax.get_ylim()[1] * 0.92, str(boundary),
                color="#c4452f", fontsize=8, ha="center", va="top",
                bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=1),
            )
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(alpha=0.25)

    axes[-1].set_xlabel("year")
    fig.suptitle(
        "Year-over-year differences — looking for discontinuities at 1950 / 1979 / 2015\n"
        "(a sustained excursion around a vertical line is evidence of a non-climatic break)",
        fontsize=12, y=0.995,
    )

    fig.subplots_adjust(bottom=0.07)
    uhi_caveat(fig)
    data_stamp(fig)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def render_urban_rural_compare(
    muscat_annual_parquet: Path,
    adam_annual: pl.DataFrame,
    out_path: Path,
) -> None:
    """Overlay Muscat (urban) and Adam (rural) for the same four metrics."""
    apply_rcparams()
    muscat = (
        pl.read_parquet(muscat_annual_parquet)
        .filter(pl.col("n_days") >= 360)
        .sort("year")
    )
    adam = adam_annual.filter(pl.col("n_days") >= 360).sort("year")

    metrics = [
        ("temp_mean_mean", "annual mean temperature (°C)"),
        ("hours_above_35_sum", "hours > 35 °C"),
        ("days_overnight_low_above_30", "30 °C nights (low > 30 °C)"),
        ("hours_wetbulb_above_28_sum", "hours wet-bulb > 28 °C"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)

    for ax, (col, label) in zip(axes.flat, metrics):
        muscat_vals = muscat[col].to_numpy().astype(float)
        adam_vals = adam[col].to_numpy().astype(float)
        ax.plot(
            muscat["year"].to_numpy(), muscat_vals,
            marker="o", markersize=2.5, linewidth=1.0,
            color="#c4452f", alpha=0.7, label="Muscat (urban, Seeb grid cell)",
        )
        ax.plot(
            adam["year"].to_numpy(), adam_vals,
            marker="o", markersize=2.5, linewidth=1.0,
            color="#3d6e8c", alpha=0.7, label="Adam (rural, ~170 km inland)",
        )
        ax.set_title(label)
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(alpha=0.25)

    fig.suptitle(
        "Urban vs rural — Muscat (Seeb) vs Adam (interior desert)\n"
        "agreement = real climate signal · gap that grows over time = urban heat island",
        fontsize=12, y=0.995,
    )
    for ax in axes[-1, :]:
        ax.set_xlabel("year")

    fig.subplots_adjust(bottom=0.10)
    data_stamp(fig)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
