"""Phase 3 multi-station charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl

from pipeline.stations import STATIONS
from pipeline.viz._common import MIN_DAYS_FOR_TREND, TRUSTWORTHY_FIT_START
from pipeline.viz.style import PALETTE, apply_rcparams, data_stamp
from pipeline.viz.trend import plot_with_trend

STATION_CHARTS: tuple[str, ...] = (
    "annual_mean_temp_by_station.png",
    "tropical_nights_by_station.png",
    "wetbulb_hours_by_station.png",
    "muscat_saiq_comparison.png",
)


def _load_station_years(annual_parquet: Path) -> pl.DataFrame:
    return (
        pl.read_parquet(annual_parquet)
        .filter(pl.col("n_days") >= MIN_DAYS_FOR_TREND)
        .sort(["station_slug", "year"])
    )


def _small_multiple_metric(
    annual_parquet: Path,
    out_path: Path,
    *,
    metric: str,
    label: str,
    title: str,
    ylabel: str,
    color: str,
) -> None:
    apply_rcparams()
    df = _load_station_years(annual_parquet)

    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True)
    flat_axes = axes.ravel()
    for ax, station in zip(flat_axes, STATIONS):
        station_df = df.filter(pl.col("station_slug") == station.slug)
        ax.set_title(station.label, fontsize=11)
        if station_df.height >= 3:
            plot_with_trend(
                ax,
                station_df["year"].to_numpy(),
                station_df[metric].to_numpy(),
                label=label,
                color=color,
                min_fit_year=TRUSTWORTHY_FIT_START,
            )
            ax.legend(loc="upper left", fontsize=7)
        else:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color="#777")
        ax.axvline(
            TRUSTWORTHY_FIT_START,
            color="#999",
            linewidth=0.6,
            linestyle=":",
            alpha=0.7,
        )
        ax.set_ylabel(ylabel)

    for ax in flat_axes[3:]:
        ax.set_xlabel("year")

    fig.suptitle(title, fontsize=15, fontweight="bold", y=0.98)
    fig.subplots_adjust(bottom=0.12, top=0.90, hspace=0.35, wspace=0.25)
    data_stamp(fig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def render_annual_mean_temperature(annual_parquet: Path, out_path: Path) -> None:
    _small_multiple_metric(
        annual_parquet,
        out_path,
        metric="temp_mean_mean",
        label="annual mean temp",
        title="Oman ERA5 stations - annual mean temperature",
        ylabel="deg C",
        color=PALETTE["above_40"],
    )


def render_tropical_nights(annual_parquet: Path, out_path: Path) -> None:
    _small_multiple_metric(
        annual_parquet,
        out_path,
        metric="days_overnight_low_above_30",
        label="30 deg C nights",
        title="Oman ERA5 stations - 30 deg C nights",
        ylabel="days",
        color=PALETTE["tropical_nights"],
    )


def render_wetbulb_hours(annual_parquet: Path, out_path: Path) -> None:
    _small_multiple_metric(
        annual_parquet,
        out_path,
        metric="hours_wetbulb_above_28_sum",
        label="wet-bulb hours > 28 deg C",
        title="Oman ERA5 stations - humid heat hours",
        ylabel="hours",
        color=PALETTE["wetbulb_above_28"],
    )


def render_muscat_saiq_comparison(annual_parquet: Path, out_path: Path) -> None:
    apply_rcparams()
    df = _load_station_years(annual_parquet)

    metrics = [
        ("temp_mean_mean", "annual mean temp", "deg C"),
        ("days_overnight_low_above_30", "30 deg C nights", "days"),
        ("hours_wetbulb_above_28_sum", "wet-bulb hours > 28 deg C", "hours"),
    ]
    colors = {"muscat": PALETTE["above_40"], "saiq": PALETTE["summer_start"]}

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    for ax, (metric, label, ylabel) in zip(axes, metrics):
        for slug in ("muscat", "saiq"):
            station_df = df.filter(pl.col("station_slug") == slug)
            if station_df.height < 3:
                continue
            station_label = station_df["station_label"][0]
            plot_with_trend(
                ax,
                station_df["year"].to_numpy(),
                station_df[metric].to_numpy(),
                label=f"{station_label} - {label}",
                color=colors[slug],
                min_fit_year=TRUSTWORTHY_FIT_START,
            )
        ax.set_ylabel(ylabel)
        ax.legend(loc="upper left", fontsize=8)
        ax.axvline(
            TRUSTWORTHY_FIT_START,
            color="#999",
            linewidth=0.6,
            linestyle=":",
            alpha=0.7,
        )

    axes[-1].set_xlabel("year")
    axes[0].set_title(
        "Muscat / Seeb vs Saiq - coastal urban heat and mountain refuge contrast"
    )
    fig.subplots_adjust(bottom=0.13, hspace=0.28)
    fig.text(
        0.01,
        0.01,
        "ERA5 grid-cell comparison: Saiq is a mountain/refuge comparator, not a "
        "controlled rural twin for Muscat. Differences mix elevation, coast, and urban context.",
        ha="left",
        va="bottom",
        fontsize=8,
        style="italic",
        color="#666",
        wrap=True,
    )
    data_stamp(fig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def render_all(annual_parquet: Path, out_dir: Path) -> list[Path]:
    renderers = {
        "annual_mean_temp_by_station.png": render_annual_mean_temperature,
        "tropical_nights_by_station.png": render_tropical_nights,
        "wetbulb_hours_by_station.png": render_wetbulb_hours,
        "muscat_saiq_comparison.png": render_muscat_saiq_comparison,
    }
    paths: list[Path] = []
    for filename in STATION_CHARTS:
        renderer = renderers[filename]
        path = out_dir / filename
        renderer(annual_parquet, path)
        paths.append(path)
    return paths
