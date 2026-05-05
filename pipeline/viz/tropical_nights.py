"""Chart 2 — days per year where overnight low > 30 °C.

Overnight is when bodies recover from daytime heat; when nights stop
cooling, that's when heat kills people. This chart makes that legible.
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

    fig, ax = plt.subplots(figsize=(10, 5))
    plot_with_trend(
        ax,
        full["year"].to_numpy(),
        full["days_overnight_low_above_30"].to_numpy(),
        label="30 °C nights",
        color=PALETTE["tropical_nights"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )

    ax.set_title("Muscat — 30 °C nights per year (overnight low > 30 °C)")
    ax.set_xlabel("year")
    ax.set_ylabel("days")
    ax.legend(loc="upper left", fontsize=9)
    ax.axvline(TRUSTWORTHY_FIT_START, color="#999", linewidth=0.6, linestyle=":", alpha=0.7)

    fig.subplots_adjust(bottom=0.18)
    uhi_caveat(fig)
    data_stamp(fig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
