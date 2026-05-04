"""Chart 4 — heatwave counts per year.

Two series:
- mild: count of distinct runs of >=3 consecutive days with high > 35 °C
- severe: count of distinct runs of >=5 consecutive days with high > 40 °C
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
        ax, years, full["heatwaves_3day_above_35"].to_numpy(),
        label="mild (≥3 days > 35 °C)", color=PALETTE["heatwave_mild"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )
    plot_with_trend(
        ax, years, full["heatwaves_5day_above_40"].to_numpy(),
        label="severe (≥5 days > 40 °C)", color=PALETTE["heatwave_severe"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )

    ax.set_title("Muscat — heatwave counts per year")
    ax.set_xlabel("year")
    ax.set_ylabel("heatwaves")
    ax.legend(loc="upper left", fontsize=9)
    ax.axvline(TRUSTWORTHY_FIT_START, color="#999", linewidth=0.6, linestyle=":", alpha=0.7)

    fig.subplots_adjust(bottom=0.18)
    uhi_caveat(fig)
    data_stamp(fig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
