"""Command-line entry point: ``python -m pipeline.cli {fetch,process}``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from pipeline.fetch.ghcn import (
    DEFAULT_DATA_DIR as DEFAULT_GHCN_RAW,
    SEEB_STATION_ID,
    fetch_station as fetch_ghcn_station,
)
from pipeline.fetch.open_meteo import HISTORICAL_START, cached_files, fetch_range
from pipeline.fetch.open_meteo import fetch_all_stations
from pipeline.fetch.sst import DEFAULT_DATA_DIR as DEFAULT_SST_RAW
from pipeline.fetch.sst import DEFAULT_FETCH_START as DEFAULT_SST_FETCH_START
from pipeline.fetch.sst import fetch_sst_range
from pipeline.process.aggregates import (
    build_annual,
    build_daily,
    hourly_from_files,
    write_parquet_atomic,
)
from pipeline.process.era5 import annual_to_common_schema
from pipeline.process.ghcn import annual_from_ghcn_daily, daily_from_ghcn_csv
from pipeline.process.sst import process_sst
from pipeline.process.stations import process_stations
from pipeline.stations import STATIONS
from pipeline.viz.personal_climate import write_personal_climate_data
from pipeline.viz.sst import write_sst_data
from pipeline.viz.station_map import write_station_map_data
from pipeline.viz.stations import render_all as render_all_station_charts
from pipeline.viz.story_metrics import write_story_metrics_data

DEFAULT_RAW = Path("data/raw/open-meteo")
DEFAULT_PROCESSED = Path("data/processed")
DEFAULT_CHARTS = Path("charts")
DEFAULT_GHCN_RAW_FILE = DEFAULT_GHCN_RAW / f"{SEEB_STATION_ID}.csv.gz"
DEFAULT_STATION_ANNUAL = DEFAULT_PROCESSED / "oman_stations_annual.parquet"
DEFAULT_SST_ANNUAL = DEFAULT_PROCESSED / "sea_of_oman_sst_annual.parquet"
DEFAULT_MUSCAT_STATION_DAILY = DEFAULT_PROCESSED / "stations" / "muscat_daily.parquet"
DEFAULT_SALALAH_STATION_DAILY = DEFAULT_PROCESSED / "stations" / "salalah_daily.parquet"

CHART_RENDERERS = {
    "threshold_hours": "pipeline.viz.threshold_hours",
    "tropical_nights": "pipeline.viz.tropical_nights",
    "summer_season": "pipeline.viz.summer_season",
    "heatwave_counts": "pipeline.viz.heatwave_counts",
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Download Open-Meteo year chunks")
    f.add_argument("--start", type=date.fromisoformat, default=HISTORICAL_START)
    f.add_argument("--end", type=date.fromisoformat, default=None)
    f.add_argument("--data-dir", type=Path, default=DEFAULT_RAW)

    fs = sub.add_parser("fetch-stations", help="Download Open-Meteo chunks for Phase 3 stations")
    fs.add_argument("--start", type=date.fromisoformat, default=HISTORICAL_START)
    fs.add_argument("--end", type=date.fromisoformat, default=None)
    fs.add_argument("--data-dir", type=Path, default=DEFAULT_RAW)

    fg = sub.add_parser("fetch-ghcn", help="Download NOAA GHCN-Daily Seeb station CSV")
    fg.add_argument("--data-dir", type=Path, default=DEFAULT_GHCN_RAW)
    fg.add_argument("--station-id", default=SEEB_STATION_ID)
    fg.add_argument("--force", action="store_true")

    pr = sub.add_parser("process", help="Build daily + annual parquet from cached JSON")
    pr.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    pr.add_argument("--out-dir", type=Path, default=DEFAULT_PROCESSED)

    ps = sub.add_parser("process-stations", help="Build Phase 3 station parquet outputs")
    ps.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    ps.add_argument("--out-dir", type=Path, default=DEFAULT_PROCESSED)

    pg = sub.add_parser("process-ghcn", help="Build GHCN daily + annual parquet")
    pg.add_argument("--raw", type=Path, default=DEFAULT_GHCN_RAW_FILE)
    pg.add_argument("--out-dir", type=Path, default=DEFAULT_PROCESSED)

    ch = sub.add_parser("chart", help="Render Phase 2 PNG charts from annual parquet")
    ch.add_argument("--annual", type=Path, default=DEFAULT_PROCESSED / "muscat_annual.parquet")
    ch.add_argument("--out", type=Path, default=DEFAULT_CHARTS)
    ch.add_argument(
        "--only",
        choices=sorted(CHART_RENDERERS),
        default=None,
        help="Render a single chart by name (default: all)",
    )

    cs = sub.add_parser("chart-stations", help="Render Phase 3 station PNG charts")
    cs.add_argument(
        "--annual",
        type=Path,
        default=DEFAULT_PROCESSED / "oman_stations_annual.parquet",
    )
    cs.add_argument("--out", type=Path, default=DEFAULT_CHARTS / "stations")

    sm = sub.add_parser(
        "station-map-data",
        help="Write Phase 3 station summary data for the static site map",
    )
    sm.add_argument(
        "--annual",
        type=Path,
        default=DEFAULT_STATION_ANNUAL,
    )
    sm.add_argument("--out", type=Path, default=Path("site/station-map-data.js"))

    pc = sub.add_parser(
        "personal-climate-data",
        help="Write Phase 4 personal climate data for the static site",
    )
    pc.add_argument("--annual", type=Path, default=DEFAULT_STATION_ANNUAL)
    pc.add_argument("--out", type=Path, default=Path("site/personal-climate-data.js"))

    smt = sub.add_parser(
        "story-metrics-data",
        help="Write Phase 5 story signal data for the static site",
    )
    smt.add_argument("--annual", type=Path, default=DEFAULT_STATION_ANNUAL)
    smt.add_argument("--muscat-daily", type=Path, default=DEFAULT_MUSCAT_STATION_DAILY)
    smt.add_argument("--salalah-daily", type=Path, default=DEFAULT_SALALAH_STATION_DAILY)
    smt.add_argument("--out", type=Path, default=Path("site/story-metrics-data.js"))

    fsst = sub.add_parser("fetch-sst", help="Download NOAA OISST Sea of Oman monthly-mean subset")
    fsst.add_argument("--start", type=date.fromisoformat, default=DEFAULT_SST_FETCH_START)
    fsst.add_argument("--end", type=date.fromisoformat, default=None)
    fsst.add_argument("--data-dir", type=Path, default=DEFAULT_SST_RAW)

    psst = sub.add_parser("process-sst", help="Build Sea of Oman SST monthly + annual parquet")
    psst.add_argument("--raw-dir", type=Path, default=DEFAULT_SST_RAW)
    psst.add_argument("--out-dir", type=Path, default=DEFAULT_PROCESSED)

    sstd = sub.add_parser("sst-data", help="Write Phase 6 SST data for the static site")
    sstd.add_argument("--sst-annual", type=Path, default=DEFAULT_SST_ANNUAL)
    sstd.add_argument("--station-annual", type=Path, default=DEFAULT_STATION_ANNUAL)
    sstd.add_argument("--salalah-daily", type=Path, default=DEFAULT_SALALAH_STATION_DAILY)
    sstd.add_argument("--out", type=Path, default=Path("site/sst-data.js"))

    dg = sub.add_parser(
        "diagnose",
        help="Run data-quality diagnostics: window comparison, step-change scan, urban/rural",
    )
    dg.add_argument("--annual", type=Path, default=DEFAULT_PROCESSED / "muscat_annual.parquet")
    dg.add_argument("--out", type=Path, default=DEFAULT_CHARTS / "diagnostics")
    dg.add_argument(
        "--with-rural",
        action="store_true",
        help="Fetch + process Adam (rural Oman) and render urban/rural comparison",
    )

    return p.parse_args(argv)


def cmd_fetch(args: argparse.Namespace) -> int:
    paths = fetch_range(start=args.start, end=args.end, data_dir=args.data_dir)
    log = logging.getLogger("pipeline")
    log.info("fetch complete: %d files in %s", len(paths), args.data_dir)
    return 0


def cmd_fetch_stations(args: argparse.Namespace) -> int:
    paths = fetch_all_stations(
        start=args.start,
        end=args.end,
        raw_root=args.data_dir,
        stations=STATIONS,
    )
    log = logging.getLogger("pipeline")
    log.info("station fetch complete: %d files in %s", len(paths), args.data_dir)
    return 0


def cmd_fetch_ghcn(args: argparse.Namespace) -> int:
    path = fetch_ghcn_station(
        data_dir=args.data_dir,
        station_id=args.station_id,
        force=args.force,
    )
    log = logging.getLogger("pipeline")
    log.info("GHCN fetch complete: %s", path)
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    files = list(cached_files(args.raw_dir))
    if not files:
        log.error("no cached JSON files in %s — run `make fetch` first", args.raw_dir)
        return 2

    log.info("loading %d raw files", len(files))
    hourly = hourly_from_files(files)
    log.info("hourly rows: %d", hourly.height)

    daily = build_daily(hourly)
    log.info("daily rows: %d", daily.height)

    annual = build_annual(daily)
    log.info("annual rows: %d", annual.height)

    write_parquet_atomic(daily, args.out_dir / "muscat_daily.parquet")
    write_parquet_atomic(annual, args.out_dir / "muscat_annual.parquet")
    write_parquet_atomic(daily, args.out_dir / "muscat_era5_daily.parquet")
    write_parquet_atomic(
        annual_to_common_schema(annual),
        args.out_dir / "muscat_era5_annual.parquet",
    )
    log.info("wrote parquet files to %s", args.out_dir)
    return 0


def cmd_process_stations(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    try:
        combined = process_stations(
            raw_root=args.raw_dir,
            out_dir=args.out_dir,
            stations=STATIONS,
        )
    except FileNotFoundError as exc:
        log.error("%s — run `python -m pipeline.cli fetch-stations` first", exc)
        return 2

    log.info("combined station annual rows: %d", combined.height)
    log.info("wrote station parquet files to %s", args.out_dir)
    return 0


def cmd_process_ghcn(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    if not args.raw.exists():
        log.error(
            "GHCN raw file not found at %s — run `python -m pipeline.cli fetch-ghcn`",
            args.raw,
        )
        return 2

    daily = daily_from_ghcn_csv(args.raw)
    log.info("GHCN daily rows: %d", daily.height)
    if daily.is_empty():
        log.error("GHCN daily frame is empty after quality filtering: %s", args.raw)
        return 2

    annual = annual_from_ghcn_daily(daily)
    log.info("GHCN annual rows: %d", annual.height)

    write_parquet_atomic(daily, args.out_dir / "muscat_ghcn_daily.parquet")
    write_parquet_atomic(annual, args.out_dir / "muscat_ghcn_annual.parquet")
    log.info("wrote GHCN parquet files to %s", args.out_dir)
    return 0


def cmd_chart(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    if not args.annual.exists():
        log.error("annual parquet not found at %s — run `make process`", args.annual)
        return 2

    import importlib

    names = [args.only] if args.only else sorted(CHART_RENDERERS)
    args.out.mkdir(parents=True, exist_ok=True)
    for name in names:
        mod = importlib.import_module(CHART_RENDERERS[name])
        out = args.out / f"{name}.png"
        log.info("rendering %s -> %s", name, out)
        mod.render(args.annual, out)
    log.info("rendered %d chart(s) to %s", len(names), args.out)
    return 0


def cmd_chart_stations(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    if not args.annual.exists():
        log.error(
            "station annual parquet not found at %s — run `make process-stations`",
            args.annual,
        )
        return 2

    paths = render_all_station_charts(args.annual, args.out)
    log.info("rendered %d station chart(s) to %s", len(paths), args.out)
    return 0


def cmd_station_map_data(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    if not args.annual.exists():
        log.error(
            "station annual parquet not found at %s — run `make process-stations`",
            args.annual,
        )
        return 2

    path = write_station_map_data(args.annual, args.out)
    log.info("wrote station map data to %s", path)
    return 0


def cmd_personal_climate_data(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    if not args.annual.exists():
        log.error(
            "station annual parquet not found at %s — run `make process-stations`",
            args.annual,
        )
        return 2

    path = write_personal_climate_data(args.annual, args.out)
    log.info("wrote personal climate data to %s", path)
    return 0


def cmd_story_metrics_data(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    required = [
        (args.annual, "make process-stations"),
        (args.muscat_daily, "make process-stations"),
        (args.salalah_daily, "make process-stations"),
    ]
    for path, command in required:
        if not path.exists():
            log.error("required parquet not found at %s — run `%s`", path, command)
            return 2

    path = write_story_metrics_data(
        args.annual,
        args.muscat_daily,
        args.salalah_daily,
        args.out,
    )
    log.info("wrote story metrics data to %s", path)
    return 0


def cmd_fetch_sst(args: argparse.Namespace) -> int:
    paths = fetch_sst_range(start=args.start, end=args.end, data_dir=args.data_dir)
    log = logging.getLogger("pipeline")
    log.info("SST fetch complete: %d files in %s", len(paths), args.data_dir)
    return 0


def cmd_process_sst(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    try:
        outputs = process_sst(args.raw_dir, args.out_dir)
    except FileNotFoundError as exc:
        log.error("%s - run `make fetch-sst`", exc)
        return 2

    log.info("SST monthly rows: %d", outputs.monthly.height)
    log.info("SST annual rows: %d", outputs.annual.height)
    log.info("wrote SST parquet files to %s", args.out_dir)
    return 0


def cmd_sst_data(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    required = [
        (args.sst_annual, "make fetch-sst && make process-sst"),
        (args.station_annual, "make process-stations"),
        (args.salalah_daily, "make process-stations"),
    ]
    for path, command in required:
        if not path.exists():
            log.error("required parquet not found at %s - run `%s`", path, command)
            return 2

    path = write_sst_data(args.sst_annual, args.station_annual, args.salalah_daily, args.out)
    log.info("wrote SST data to %s", path)
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    log = logging.getLogger("pipeline")
    if not args.annual.exists():
        log.error("annual parquet not found at %s — run `make process`", args.annual)
        return 2

    from pipeline.diagnostics.step_changes import scan_boundaries
    from pipeline.diagnostics.windows import (
        compare_windows,
        find_window_dependent_metrics,
    )
    from pipeline.viz.diagnostics import (
        render_first_differences,
        render_urban_rural_compare,
        render_window_comparison,
    )

    args.out.mkdir(parents=True, exist_ok=True)

    log.info("=== window comparison ===")
    table = compare_windows(args.annual)
    print(table)
    flagged = find_window_dependent_metrics(table)
    log.info("window-dependent metrics: %d", len(flagged))
    for f in flagged:
        log.info("  %s — sign_flips=%s sig_crosses=%s",
                 f["metric"], f["sign_flips"], f["significance_crosses"])

    log.info("=== step-change probe (annual mean temperature) ===")
    print(scan_boundaries(args.annual, metric="temp_mean_mean"))

    log.info("=== diagnostic charts ===")
    render_window_comparison(args.annual, args.out / "window_comparison.png")
    render_first_differences(args.annual, args.out / "first_differences.png")
    log.info("wrote 2 diagnostic charts to %s", args.out)

    if args.with_rural:
        log.info("=== fetching Adam (rural Oman) ===")
        from pipeline.diagnostics.rural import build_adam_annual, fetch_adam
        fetch_adam()
        adam_annual = build_adam_annual()
        log.info("Adam annual rows: %d", adam_annual.height)
        render_urban_rural_compare(
            args.annual, adam_annual, args.out / "urban_rural_compare.png"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "fetch":
        return cmd_fetch(args)
    if args.cmd == "fetch-stations":
        return cmd_fetch_stations(args)
    if args.cmd == "fetch-ghcn":
        return cmd_fetch_ghcn(args)
    if args.cmd == "process":
        return cmd_process(args)
    if args.cmd == "process-stations":
        return cmd_process_stations(args)
    if args.cmd == "process-ghcn":
        return cmd_process_ghcn(args)
    if args.cmd == "chart":
        return cmd_chart(args)
    if args.cmd == "chart-stations":
        return cmd_chart_stations(args)
    if args.cmd == "station-map-data":
        return cmd_station_map_data(args)
    if args.cmd == "personal-climate-data":
        return cmd_personal_climate_data(args)
    if args.cmd == "story-metrics-data":
        return cmd_story_metrics_data(args)
    if args.cmd == "fetch-sst":
        return cmd_fetch_sst(args)
    if args.cmd == "process-sst":
        return cmd_process_sst(args)
    if args.cmd == "sst-data":
        return cmd_sst_data(args)
    if args.cmd == "diagnose":
        return cmd_diagnose(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
