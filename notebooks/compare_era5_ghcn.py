"""Compare Muscat annual mean temperature from ERA5 and NOAA GHCN-Daily.

Run as:
    uv run python notebooks/compare_era5_ghcn.py

Or open as a Jupyter percent notebook in an editor that supports `# %%` cells.
"""

# %% imports
from pathlib import Path

import polars as pl

from pipeline.process.era5 import annual_to_common_schema

DATA = Path("data/processed")
OUT = Path("notebooks")
START_YEAR = 1950
MIN_DAYS = 360


# %% load common annual aggregates
def _load_era5() -> pl.DataFrame:
    common = DATA / "muscat_era5_annual.parquet"
    if common.exists():
        return pl.read_parquet(common)

    legacy = DATA / "muscat_annual.parquet"
    if legacy.exists():
        return annual_to_common_schema(pl.read_parquet(legacy))

    raise FileNotFoundError(
        "ERA5 annual aggregate not found. Run `make process` first."
    )


def _load_ghcn() -> pl.DataFrame:
    path = DATA / "muscat_ghcn_annual.parquet"
    if path.exists():
        return pl.read_parquet(path)

    raise FileNotFoundError(
        "GHCN annual aggregate not found. Run `make fetch-ghcn && make process-ghcn` first."
    )


era5 = _load_era5()
ghcn = _load_ghcn()


# %% align complete years
def _complete(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter((pl.col("year") >= START_YEAR) & (pl.col("n_days") >= MIN_DAYS))


era5_plot = _complete(era5).select(
    "year",
    pl.col("temp_mean_mean").alias("era5_temp_mean_c"),
    pl.col("n_days").alias("era5_n_days"),
)
ghcn_plot = _complete(ghcn).select(
    "year",
    pl.col("temp_mean_mean").alias("ghcn_temp_mean_c"),
    pl.col("n_days").alias("ghcn_n_days"),
)

paired = (
    era5_plot
    .join(
        ghcn_plot,
        on="year",
        how="inner",
    )
    .with_columns(
        (pl.col("ghcn_temp_mean_c") - pl.col("era5_temp_mean_c")).alias(
            "ghcn_minus_era5_c"
        )
    )
    .sort("year")
)

print(
    f"ERA5 complete years: {era5_plot['year'].min()} -> {era5_plot['year'].max()} "
    f"({era5_plot.height} years)"
)
print(
    f"GHCN complete years: {ghcn_plot['year'].min()} -> {ghcn_plot['year'].max()} "
    f"({ghcn_plot.height} years)"
)
print(
    f"overlap for difference: {paired['year'].min()} -> {paired['year'].max()} "
    f"({paired.height} complete years)"
)
print("\nLargest absolute disagreements:")
print(
    paired.with_columns(pl.col("ghcn_minus_era5_c").abs().alias("abs_diff"))
    .sort("abs_diff", descending=True)
    .select(["year", "era5_temp_mean_c", "ghcn_temp_mean_c", "ghcn_minus_era5_c"])
    .head(10)
)


# %% overlay on the same axes
try:
    import matplotlib.pyplot as plt

    era5_years = era5_plot["year"].to_list()
    ghcn_years = ghcn_plot["year"].to_list()
    overlap_years = paired["year"].to_list()

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(
        era5_years,
        era5_plot["era5_temp_mean_c"].to_list(),
        color="#2f6fbd",
        linewidth=1.8,
        label="ERA5 via Open-Meteo, hourly mean by Muscat local day",
    )
    ax.plot(
        ghcn_years,
        ghcn_plot["ghcn_temp_mean_c"].to_list(),
        color="#b4442a",
        linewidth=1.8,
        label="NOAA GHCN-Daily, Seeb station daily summaries",
    )
    ax.set_title("Muscat annual mean temperature, ERA5 vs GHCN-Daily")
    ax.set_xlabel("year")
    ax.set_ylabel("annual mean temperature (deg C)")
    ax.set_xlim(START_YEAR, max(max(era5_years), max(ghcn_years)))
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    overlay_path = OUT / "era5_ghcn_annual_mean_overlay.png"
    fig.savefig(overlay_path, dpi=150)
    print(f"\noverlay written: {overlay_path}")

    # The shape of disagreement is the finding.
    fig, ax = plt.subplots(figsize=(11, 3.5))
    ax.axhline(0, color="#555555", linewidth=1, alpha=0.7)
    ax.plot(
        overlap_years,
        paired["ghcn_minus_era5_c"].to_list(),
        color="#4d7d57",
        linewidth=1.8,
    )
    ax.set_title("Shape of disagreement: GHCN minus ERA5")
    ax.set_xlabel("year")
    ax.set_ylabel("difference (deg C)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    diff_path = OUT / "era5_ghcn_annual_mean_difference.png"
    fig.savefig(diff_path, dpi=150)
    print(f"difference chart written: {diff_path}")
except ImportError:
    print("matplotlib not installed; skipping plots")


# %% inspect aligned table
paired
