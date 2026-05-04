"""CLI wiring for the GHCN source."""

from __future__ import annotations

import gzip
from argparse import Namespace
from pathlib import Path

import polars as pl

from pipeline.process.common_schema import COMMON_ANNUAL_COLUMNS


def _write_station_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "MUM00041256,20200101,TAVG,255,,,S,2400",
        "MUM00041256,20200101,TMAX,301,,,S,2400",
        "MUM00041256,20200101,TMIN,208,,,S,2400",
        "MUM00041256,20200102,TAVG,265,,,S,2400",
        "MUM00041256,20200102,TMAX,311,,,S,2400",
        "MUM00041256,20200102,TMIN,218,,,S,2400",
    ]
    with gzip.open(path, "wt", newline="") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")
    return path


def test_cmd_fetch_ghcn_calls_station_fetcher(monkeypatch, tmp_path: Path):
    from pipeline import cli

    called = {}

    def fake_fetch_station(*, data_dir, station_id, force):
        called["data_dir"] = data_dir
        called["station_id"] = station_id
        called["force"] = force
        return data_dir / f"{station_id}.csv.gz"

    monkeypatch.setattr(cli, "fetch_ghcn_station", fake_fetch_station)

    code = cli.cmd_fetch_ghcn(
        Namespace(data_dir=tmp_path, station_id="OMM00041256", force=True)
    )

    assert code == 0
    assert called == {
        "data_dir": tmp_path,
        "station_id": "OMM00041256",
        "force": True,
    }


def test_cmd_process_ghcn_writes_daily_and_common_annual(tmp_path: Path):
    from pipeline.cli import cmd_process_ghcn

    raw = _write_station_csv(tmp_path / "raw" / "MUM00041256.csv.gz")
    out_dir = tmp_path / "processed"

    code = cmd_process_ghcn(Namespace(raw=raw, out_dir=out_dir))

    assert code == 0
    assert (out_dir / "muscat_ghcn_daily.parquet").exists()
    annual_path = out_dir / "muscat_ghcn_annual.parquet"
    assert annual_path.exists()

    annual = pl.read_parquet(annual_path)
    assert annual.columns == COMMON_ANNUAL_COLUMNS
    assert annual.row(0, named=True)["temp_mean_mean"] == 26.0
