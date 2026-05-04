"""Phase 1 acceptance: load processed parquet and inspect 80+ years.

Run as:
    uv run python notebooks/explore.py

Or paste each cell-block into a Jupyter notebook (`uv run jupyter lab`).
"""

# %% imports
from pathlib import Path
import polars as pl

DATA = Path("data/processed")

# %% load
daily = pl.read_parquet(DATA / "muscat_daily.parquet")
annual = pl.read_parquet(DATA / "muscat_annual.parquet")
print(f"daily: {daily.height} rows  ({daily['date'].min()} → {daily['date'].max()})")
print(f"annual: {annual.height} rows ({annual['year'].min()} → {annual['year'].max()})")

# %% summer length over 80+ years
print("\n=== Summer length (longest run of days with high > 35 °C) ===")
print(
    annual.select(["year", "summer_length", "days_overnight_low_above_30"])
    .sort("year")
)

# %% top-10 hottest summers by days-above-40
print("\n=== Top 10 years by hours above 40 °C ===")
print(
    annual.select(["year", "hours_above_40_sum", "wet_bulb_max_p99"])
    .sort("hours_above_40_sum", descending=True)
    .head(10)
)

# %% Phase 1 deliverable — annual mean temperature in Muscat, 1940-present
try:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4))
    full = annual.filter(pl.col("n_days") >= 360)  # drop partial years (e.g. 2026)
    ax.plot(full["year"], full["temp_mean_mean"], linewidth=1.5)
    ax.set_xlabel("year")
    ax.set_ylabel("mean temperature (°C)")
    ax.set_title("Muscat — annual mean temperature, 1940-present (Open-Meteo / ERA5)")
    ax.grid(alpha=0.3)
    out = Path("notebooks/annual_mean_temp.png")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    print(f"\nphase 1 chart written: {out}")

    # Phase 2 preview: summer length over time
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(full["year"], full["summer_length"], marker="o", linewidth=1)
    ax.set_xlabel("year")
    ax.set_ylabel("summer length (days)")
    ax.set_title("Muscat — longest consecutive run of days >35 °C")
    ax.grid(alpha=0.3)
    out = Path("notebooks/summer_length.png")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    print(f"phase 2 preview chart written: {out}")
except ImportError:
    print("matplotlib not installed; skipping plot")
