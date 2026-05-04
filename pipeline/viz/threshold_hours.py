"""Chart 1 — hours per year above 35 °C, 40 °C, and wet-bulb 28 °C.

Source: ``data/processed/muscat_annual.parquet``. Rows with ``n_days < 360``
are dropped (partial years). Three series with OLS trend bands; UHI caveat.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from pipeline.viz._common import TRUSTWORTHY_FIT_START, load_full_years
from pipeline.viz.style import PALETTE, apply_rcparams, data_stamp, uhi_caveat
from pipeline.viz.trend import plot_with_trend


def render(annual_parquet: Path, out_path: Path) -> None:
    apply_rcparams()
    full = load_full_years(annual_parquet)
    years = full["year"].to_numpy()

    fig, ax = plt.subplots(figsize=(10, 5))
    plot_with_trend(
        ax, years, full["hours_above_35_sum"].to_numpy(),
        label="hours > 35 °C", color=PALETTE["above_35"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )
    plot_with_trend(
        ax, years, full["hours_above_40_sum"].to_numpy(),
        label="hours > 40 °C", color=PALETTE["above_40"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )
    plot_with_trend(
        ax, years, full["hours_wetbulb_above_28_sum"].to_numpy(),
        label="hours wet-bulb > 28 °C", color=PALETTE["wetbulb_above_28"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )

    ax.set_title("Muscat — hours per year above heat thresholds")
    ax.set_xlabel("year")
    ax.set_ylabel("hours")
    ax.legend(loc="upper left", fontsize=9)
    ax.axvline(TRUSTWORTHY_FIT_START, color="#999", linewidth=0.6, linestyle=":", alpha=0.7)

    fig.subplots_adjust(bottom=0.18)
    uhi_caveat(fig)
    data_stamp(fig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
