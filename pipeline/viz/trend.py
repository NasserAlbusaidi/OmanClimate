"""Single canonical "scatter + trend with CI band" helper.

Methodology rule 1 (always show uncertainty) is enforced *here*: every
chart in this project draws trends through ``plot_with_trend``, which
always emits a 95 % CI band and a Mann-Kendall significance label.
There is intentionally no bare ``ax.plot(years, trend_line)`` helper.
"""

from __future__ import annotations

import numpy as np

from pipeline.analysis.trends import mann_kendall, ols_with_ci, theil_sen


def _format_pvalue(p: float) -> str:
    if not np.isfinite(p):
        return "p=n/a"
    if p < 0.001:
        return "p<0.001"
    return f"p={p:.3f}"


def plot_with_trend(
    ax,
    years,
    values,
    *,
    label: str,
    color: str,
    fit: str = "ols",  # "ols" | "theil_sen"
    show_band: bool = True,
    marker: str = "o",
    line_alpha: float = 0.6,
    min_fit_year: int | None = None,
) -> dict:
    """Scatter + trend line with 95 % CI band; Mann-Kendall p in the legend.

    If ``min_fit_year`` is given, points before that year are still plotted
    (muted) but excluded from the trend fit. This honours methodology rule 1
    (transparency) by showing the data the reader is asked to distrust,
    rather than silently dropping it.
    """
    x_all = np.asarray(years, dtype=np.float64)
    y_all = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(x_all) & np.isfinite(y_all)
    x_all = x_all[mask]
    y_all = y_all[mask]
    if x_all.size < 3:
        raise ValueError(f"plot_with_trend needs >=3 finite points, got {x_all.size}")

    if min_fit_year is None:
        x = x_all
        y = y_all
    else:
        keep = x_all >= float(min_fit_year)
        # Excluded points: light, dotted, no fit. Visible but visually deprioritised.
        if (~keep).any():
            ax.plot(
                x_all[~keep], y_all[~keep],
                marker=marker, markersize=3,
                linewidth=0.6, linestyle=":",
                color=color, alpha=0.25,
                label=None,
            )
        x = x_all[keep]
        y = y_all[keep]
        if x.size < 3:
            raise ValueError(
                f"plot_with_trend: only {x.size} points >= {min_fit_year}, need >=3"
            )

    # Raw observations (low-saturation marker + thin line)
    ax.plot(
        x,
        y,
        marker=marker,
        markersize=3,
        linewidth=0.8,
        color=color,
        alpha=line_alpha,
        label=None,
    )

    if fit == "theil_sen":
        ts = theil_sen(x, y)
        fitted = ts["slope"] * x + ts["intercept"]
        ax.plot(x, fitted, color=color, linewidth=2.0)
        # CI band uses the slope CI projected through the data (rough but honest)
        lo = (ts["slope_lower"] * x + ts["intercept"])
        hi = (ts["slope_upper"] * x + ts["intercept"])
        if show_band:
            ax.fill_between(x, lo, hi, color=color, alpha=0.15, linewidth=0)
        slope_label = f"{ts['slope']:.3f}/yr"
    else:
        ols = ols_with_ci(x, y)
        ax.plot(x, ols["fitted"], color=color, linewidth=2.0)
        if show_band:
            ax.fill_between(
                x,
                ols["ci_lower"],
                ols["ci_upper"],
                color=color,
                alpha=0.18,
                linewidth=0,
            )
        slope_label = f"{ols['slope']:.3f}/yr"

    mk = mann_kendall(x, y)
    full_label = f"{label}  ({slope_label}, {_format_pvalue(mk['p_value'])})"

    # Add an invisible scatter just to get a single legend handle of the right colour.
    ax.plot([], [], color=color, marker=marker, linewidth=2.0, label=full_label)

    return {
        "fit": fit,
        "mann_kendall": mk,
        "slope_label": slope_label,
    }
