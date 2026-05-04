"""Project-wide matplotlib style + caveat helpers.

The methodology rules (`docs/methodology.md`) bind every Muscat-only
chart to a UHI caveat and a data-source stamp. ``uhi_caveat`` and
``data_stamp`` exist so those obligations cannot be forgotten: chart
code calls them as the last step before saving.
"""

from __future__ import annotations

from datetime import date

import matplotlib as mpl

# Severity-ordered palette: cool → hot.
PALETTE: dict[str, str] = {
    "above_35": "#e08a3c",
    "above_40": "#c4452f",
    "wetbulb_above_28": "#7a2a6e",
    "tropical_nights": "#2a6f97",
    "summer_length": "#a04030",
    "summer_start": "#3d6e8c",
    "summer_end": "#8c5a3d",
    "heatwave_mild": "#d68c4a",
    "heatwave_severe": "#8a2828",
    "trend_band": "#888888",
}

UHI_CAVEAT_TEXT = (
    "Single grid cell at Seeb / Muscat. Some warming reflects local "
    "urbanisation, not climate alone. See /methodology."
)


def apply_rcparams() -> None:
    """Set matplotlib rcParams for the project. Idempotent."""
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Helvetica Neue",
                "Helvetica",
                "Arial",
                "DejaVu Sans",
            ],
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.5,
            "legend.frameon": False,
            "figure.dpi": 140,
            "savefig.dpi": 140,
            "savefig.bbox": "tight",
        }
    )


def uhi_caveat(fig, location: str = "Seeb / Muscat") -> None:
    """Stamp the urban-heat-island caveat at the bottom of the figure."""
    text = (
        f"Single grid cell at {location}. Some warming reflects local "
        "urbanisation, not climate alone. See /methodology."
    )
    fig.text(
        0.01,
        0.01,
        text,
        ha="left",
        va="bottom",
        fontsize=8,
        style="italic",
        color="#666",
        wrap=True,
    )
    fig._uhi_caveat_applied = True  # smoke tests assert this exists


def data_stamp(fig, retrieved: date | None = None) -> None:
    """Stamp the data source + retrieval date at the bottom-right."""
    when = (retrieved or date.today()).isoformat()
    fig.text(
        0.99,
        0.01,
        f"Source: Open-Meteo Archive (ERA5) · retrieved {when}",
        ha="right",
        va="bottom",
        fontsize=8,
        color="#888",
    )
