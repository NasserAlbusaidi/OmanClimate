"""Chart 3 — summer length, start, and end day-of-year over time.

Three vertically-stacked panels. Years where ``summer_length == 0`` are
dropped from the start/end panels.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from pipeline.viz._common import TRUSTWORTHY_FIT_START, load_full_years
from pipeline.viz.style import PALETTE, apply_rcparams, data_stamp, uhi_caveat
from pipeline.viz.trend import plot_with_trend


def render(annual_parquet: Path, out_path: Path) -> None:
    apply_rcparams()
    full = load_full_years(annual_parquet)

    # Drop years with no qualifying summer for start/end panels.
    has_summer = full.filter(pl.col("summer_length") > 0)
    start_doy = np.array(
        [d.timetuple().tm_yday for d in has_summer["summer_start"].to_list()],
        dtype=float,
    )
    end_doy = np.array(
        [d.timetuple().tm_yday for d in has_summer["summer_end"].to_list()],
        dtype=float,
    )

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    plot_with_trend(
        axes[0], full["year"].to_numpy(), full["summer_length"].to_numpy(),
        label="summer length", color=PALETTE["summer_length"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )
    axes[0].set_title("Muscat — summer length, start, and end")
    axes[0].set_ylabel("days")
    axes[0].legend(loc="upper left", fontsize=9)

    plot_with_trend(
        axes[1], has_summer["year"].to_numpy(), start_doy,
        label="summer start (day of year)", color=PALETTE["summer_start"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )
    axes[1].set_ylabel("day of year")
    axes[1].legend(loc="upper left", fontsize=9)

    plot_with_trend(
        axes[2], has_summer["year"].to_numpy(), end_doy,
        label="summer end (day of year)", color=PALETTE["summer_end"],
        min_fit_year=TRUSTWORTHY_FIT_START,
    )
    axes[2].set_xlabel("year")
    axes[2].set_ylabel("day of year")
    axes[2].legend(loc="upper left", fontsize=9)
    for ax in axes:
        ax.axvline(TRUSTWORTHY_FIT_START, color="#999", linewidth=0.6, linestyle=":", alpha=0.7)

    fig.subplots_adjust(bottom=0.10)
    uhi_caveat(fig)
    data_stamp(fig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
