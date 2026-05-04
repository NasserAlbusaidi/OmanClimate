"""Process Sea of Oman SST NetCDF subsets into parquet outputs."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable

import pandas as pd
import polars as pl
import xarray as xr

from pipeline.fetch.sst import SEA_OF_OMAN_REGION, SSTRegion
from pipeline.process.aggregates import write_parquet_atomic

SST_ANNUAL_START = 1982
SST_BASELINE_START = 1982
SST_BASELINE_END = 2011
SST_MIN_DAYS_FOR_ANNUAL = 360


@dataclass(frozen=True)
class SSTOutputs:
    monthly: pl.DataFrame
    annual: pl.DataFrame
    monthly_path: Path
    annual_path: Path

    @property
    def daily(self) -> pl.DataFrame:
        """Backward-compatible alias for older CLI logging."""
        return self.monthly

    @property
    def daily_path(self) -> Path:
        """Backward-compatible alias for older callers."""
        return self.monthly_path


def _coord_name(dataset: xr.Dataset, candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in dataset.coords or name in dataset.dims:
            return name
    raise KeyError(f"Dataset does not contain any of: {', '.join(candidates)}")


def _region_slice(dataset: xr.Dataset, coord_name: str, low: float, high: float) -> slice:
    values = dataset[coord_name].values
    if len(values) == 0:
        raise ValueError(f"Coordinate {coord_name} is empty")
    first = float(values[0])
    last = float(values[-1])
    if first <= last:
        return slice(low, high)
    return slice(high, low)


def _sst_from_dataset(
    dataset: xr.Dataset,
    region: SSTRegion,
    *,
    monthly_weights: bool,
) -> pl.DataFrame:
    lat_name = _coord_name(dataset, ("lat", "latitude"))
    lon_name = _coord_name(dataset, ("lon", "longitude"))
    time_name = _coord_name(dataset, ("time",))

    sst = dataset["sst"].sel(
        {
            lat_name: _region_slice(dataset, lat_name, region.south, region.north),
            lon_name: _region_slice(dataset, lon_name, region.west, region.east),
        }
    )
    regional_mean = sst.mean(dim=[lat_name, lon_name], skipna=True)

    pdf = regional_mean.to_dataframe(name="sst_mean").reset_index()
    dates = pd.to_datetime(pdf[time_name]).dt.date.to_list()
    data = {"date": dates, "sst_mean": pdf["sst_mean"].to_list()}
    if monthly_weights:
        data["n_days"] = [monthrange(d.year, d.month)[1] for d in dates]
    return pl.DataFrame(data)


def daily_sst_from_netcdf_files(
    paths: Iterable[Path],
    region: SSTRegion = SEA_OF_OMAN_REGION,
) -> pl.DataFrame:
    """Build daily regional SST means from sorted NetCDF files."""
    frames: list[pl.DataFrame] = []
    for path in sorted(Path(p) for p in paths):
        with xr.open_dataset(path) as dataset:
            frames.append(_sst_from_dataset(dataset, region, monthly_weights=False))

    if not frames:
        raise FileNotFoundError("No SST NetCDF files supplied")

    cleaned = (
        pl.concat(frames)
        .filter(pl.col("date").is_not_null() & pl.col("sst_mean").is_finite())
        .unique(subset=["date"], keep="last")
        .sort("date")
    )
    if cleaned.is_empty():
        raise ValueError("No finite SST values found in OISST files")
    return cleaned


def monthly_sst_from_netcdf_files(
    paths: Iterable[Path],
    region: SSTRegion = SEA_OF_OMAN_REGION,
) -> pl.DataFrame:
    """Build monthly regional SST means from sorted monthly OISST NetCDF files."""
    frames: list[pl.DataFrame] = []
    for path in sorted(Path(p) for p in paths):
        with xr.open_dataset(path) as dataset:
            frames.append(_sst_from_dataset(dataset, region, monthly_weights=True))

    if not frames:
        raise FileNotFoundError("No SST NetCDF files supplied")

    cleaned = (
        pl.concat(frames)
        .filter(
            pl.col("date").is_not_null()
            & pl.col("sst_mean").is_finite()
            & (pl.col("n_days") > 0)
        )
        .unique(subset=["date"], keep="last")
        .sort("date")
    )
    if cleaned.is_empty():
        raise ValueError("No finite SST values found in OISST files")
    return cleaned


def build_sst_annual(daily: pl.DataFrame) -> pl.DataFrame:
    """Aggregate daily Sea of Oman SST into annual means and baseline anomaly."""
    if daily.is_empty():
        raise ValueError("Daily SST frame is empty; cannot build annual aggregates")

    weight_expr = pl.col("n_days") if "n_days" in daily.columns else pl.lit(1)
    df = daily.with_columns(
        [
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month"),
            weight_expr.cast(pl.Float64).alias("_sst_weight"),
        ]
    ).filter(
        (pl.col("year") >= SST_ANNUAL_START)
        & pl.col("date").is_not_null()
        & pl.col("sst_mean").is_finite()
        & (pl.col("_sst_weight") > 0)
    )

    annual = (
        df.group_by("year", maintain_order=True)
        .agg(
            (
                (pl.col("sst_mean") * pl.col("_sst_weight")).sum()
                / pl.col("_sst_weight").sum()
            ).alias("sst_mean"),
            (
                (pl.col("sst_mean").filter(pl.col("month").is_between(6, 9))
                 * pl.col("_sst_weight").filter(pl.col("month").is_between(6, 9))).sum()
                / pl.col("_sst_weight").filter(pl.col("month").is_between(6, 9)).sum()
            ).alias("sst_jun_sep_mean"),
            (
                (pl.col("sst_mean").filter(pl.col("month").is_between(5, 10))
                 * pl.col("_sst_weight").filter(pl.col("month").is_between(5, 10))).sum()
                / pl.col("_sst_weight").filter(pl.col("month").is_between(5, 10)).sum()
            ).alias("sst_may_oct_mean"),
            pl.col("_sst_weight").sum().round(0).cast(pl.Int32).alias("n_days"),
        )
        .with_columns(pl.col("year").cast(pl.Int32))
        .filter(pl.col("n_days") >= SST_MIN_DAYS_FOR_ANNUAL)
        .sort("year")
    )

    baseline_mean = annual.filter(
        pl.col("year").is_between(SST_BASELINE_START, SST_BASELINE_END)
    )["sst_mean"].mean()
    if baseline_mean is None or not math.isfinite(baseline_mean):
        raise ValueError("No finite SST baseline values for 1982-2011")

    return annual.with_columns(
        (pl.col("sst_mean") - baseline_mean).alias("sst_anomaly_vs_1982_2011")
    ).select(
        "year",
        "sst_mean",
        "sst_jun_sep_mean",
        "sst_may_oct_mean",
        "sst_anomaly_vs_1982_2011",
        "n_days",
    )


def write_sst_outputs(monthly: pl.DataFrame, out_dir: Path) -> SSTOutputs:
    """Write monthly and annual SST parquet outputs."""
    annual = build_sst_annual(monthly)
    monthly_path = out_dir / "sea_of_oman_sst_monthly.parquet"
    annual_path = out_dir / "sea_of_oman_sst_annual.parquet"

    write_parquet_atomic(monthly, monthly_path)
    write_parquet_atomic(annual, annual_path)

    return SSTOutputs(
        monthly=monthly,
        annual=annual,
        monthly_path=monthly_path,
        annual_path=annual_path,
    )


def process_sst(raw_dir: Path, out_dir: Path) -> SSTOutputs:
    """Process cached Sea of Oman SST NetCDF files into parquet outputs."""
    paths = sorted(raw_dir.glob("sst.mon.mean.*.sea-of-oman.nc"))
    if paths:
        monthly = monthly_sst_from_netcdf_files(paths)
        return write_sst_outputs(monthly, out_dir)

    paths = sorted(raw_dir.glob("sst.day.mean.*.sea-of-oman.nc"))
    if not paths:
        raise FileNotFoundError(f"No SST NetCDF files found in {raw_dir}")
    daily = daily_sst_from_netcdf_files(paths)
    return write_sst_outputs(daily, out_dir)
