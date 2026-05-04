"""CLI wiring for Phase 3 station commands."""

from __future__ import annotations

from argparse import Namespace
from datetime import date
from pathlib import Path


def test_cmd_fetch_stations_calls_station_fetcher(monkeypatch, tmp_path: Path):
    from pipeline import cli
    from pipeline.stations import STATIONS

    called = {}

    def fake_fetch_all_stations(*, start, end, raw_root, stations):
        called["start"] = start
        called["end"] = end
        called["raw_root"] = raw_root
        called["stations"] = stations
        return [raw_root / s.slug / f"{s.slug}-2024-01-01_2024-12-31.json" for s in stations]

    monkeypatch.setattr(cli, "fetch_all_stations", fake_fetch_all_stations)

    code = cli.cmd_fetch_stations(
        Namespace(start=date(2024, 1, 1), end=date(2024, 12, 31), data_dir=tmp_path)
    )

    assert code == 0
    assert called == {
        "start": date(2024, 1, 1),
        "end": date(2024, 12, 31),
        "raw_root": tmp_path,
        "stations": STATIONS,
    }


def test_cmd_process_stations_calls_processor(monkeypatch, tmp_path: Path):
    from pipeline import cli
    from pipeline.stations import STATIONS

    called = {}

    def fake_process_stations(*, raw_root, out_dir, stations):
        called["raw_root"] = raw_root
        called["out_dir"] = out_dir
        called["stations"] = stations
        return type("Frame", (), {"height": 12})()

    monkeypatch.setattr(cli, "process_stations", fake_process_stations)

    code = cli.cmd_process_stations(Namespace(raw_dir=tmp_path / "raw", out_dir=tmp_path / "out"))

    assert code == 0
    assert called == {
        "raw_root": tmp_path / "raw",
        "out_dir": tmp_path / "out",
        "stations": STATIONS,
    }


def test_cmd_chart_stations_renders_phase3_outputs(monkeypatch, tmp_path: Path):
    from pipeline import cli

    annual = tmp_path / "oman_stations_annual.parquet"
    annual.write_bytes(b"not-empty")
    out_dir = tmp_path / "charts"
    rendered = []

    def fake_render_all_station_charts(annual_parquet, out):
        rendered.append((annual_parquet, out))
        return [
            out / "annual_mean_temp_by_station.png",
            out / "tropical_nights_by_station.png",
            out / "wetbulb_hours_by_station.png",
            out / "muscat_saiq_comparison.png",
        ]

    monkeypatch.setattr(cli, "render_all_station_charts", fake_render_all_station_charts)

    code = cli.cmd_chart_stations(Namespace(annual=annual, out=out_dir))

    assert code == 0
    assert rendered == [(annual, out_dir)]


def test_cmd_station_map_data_writes_site_data(monkeypatch, tmp_path: Path):
    from pipeline import cli

    annual = tmp_path / "oman_stations_annual.parquet"
    annual.write_bytes(b"not-empty")
    out = tmp_path / "station-map-data.js"
    calls = []

    def fake_write_station_map_data(annual_parquet, out_path):
        calls.append((annual_parquet, out_path))
        return out_path

    monkeypatch.setattr(cli, "write_station_map_data", fake_write_station_map_data)

    code = cli.cmd_station_map_data(Namespace(annual=annual, out=out))

    assert code == 0
    assert calls == [(annual, out)]


def test_cmd_personal_climate_data_writes_site_data(monkeypatch, tmp_path: Path):
    from pipeline import cli

    annual = tmp_path / "oman_stations_annual.parquet"
    annual.write_bytes(b"not-empty")
    out = tmp_path / "personal-climate-data.js"
    calls = []

    def fake_write_personal_climate_data(annual_parquet, out_path):
        calls.append((annual_parquet, out_path))
        return out_path

    monkeypatch.setattr(cli, "write_personal_climate_data", fake_write_personal_climate_data)

    code = cli.cmd_personal_climate_data(Namespace(annual=annual, out=out))

    assert code == 0
    assert calls == [(annual, out)]


def test_cmd_story_metrics_data_writes_site_data(monkeypatch, tmp_path: Path):
    from pipeline import cli

    annual = tmp_path / "oman_stations_annual.parquet"
    muscat_daily = tmp_path / "muscat_daily.parquet"
    salalah_daily = tmp_path / "salalah_daily.parquet"
    for path in (annual, muscat_daily, salalah_daily):
        path.write_bytes(b"not-empty")
    out = tmp_path / "story-metrics-data.js"
    calls = []

    def fake_write_story_metrics_data(
        annual_parquet,
        muscat_daily_parquet,
        salalah_daily_parquet,
        out_path,
    ):
        calls.append(
            (annual_parquet, muscat_daily_parquet, salalah_daily_parquet, out_path)
        )
        return out_path

    monkeypatch.setattr(cli, "write_story_metrics_data", fake_write_story_metrics_data)

    code = cli.cmd_story_metrics_data(
        Namespace(
            annual=annual,
            muscat_daily=muscat_daily,
            salalah_daily=salalah_daily,
            out=out,
        )
    )

    assert code == 0
    assert calls == [(annual, muscat_daily, salalah_daily, out)]


def test_cmd_story_metrics_data_reports_missing_daily_input(tmp_path: Path):
    from pipeline import cli

    annual = tmp_path / "oman_stations_annual.parquet"
    annual.write_bytes(b"not-empty")

    code = cli.cmd_story_metrics_data(
        Namespace(
            annual=annual,
            muscat_daily=tmp_path / "missing-muscat.parquet",
            salalah_daily=tmp_path / "missing-salalah.parquet",
            out=tmp_path / "story-metrics-data.js",
        )
    )

    assert code == 2


def test_cmd_fetch_sst_calls_fetcher(monkeypatch, tmp_path: Path):
    from pipeline import cli

    called = {}

    def fake_fetch_sst_range(*, start, end, data_dir):
        called["start"] = start
        called["end"] = end
        called["data_dir"] = data_dir
        return [data_dir / "oisst-2024.nc"]

    monkeypatch.setattr(cli, "fetch_sst_range", fake_fetch_sst_range)

    code = cli.cmd_fetch_sst(
        Namespace(start=date(2024, 1, 1), end=date(2024, 12, 31), data_dir=tmp_path)
    )

    assert code == 0
    assert called == {
        "start": date(2024, 1, 1),
        "end": date(2024, 12, 31),
        "data_dir": tmp_path,
    }


def test_cmd_process_sst_calls_processor(monkeypatch, tmp_path: Path):
    from pipeline import cli

    called = {}
    outputs = type(
        "SSTOutputs",
        (),
        {
            "monthly": type("Frame", (), {"height": 12})(),
            "annual": type("Frame", (), {"height": 1})(),
        },
    )()

    def fake_process_sst(raw_dir, out_dir):
        called["raw_dir"] = raw_dir
        called["out_dir"] = out_dir
        return outputs

    monkeypatch.setattr(cli, "process_sst", fake_process_sst)

    code = cli.cmd_process_sst(Namespace(raw_dir=tmp_path / "raw", out_dir=tmp_path / "out"))

    assert code == 0
    assert called == {
        "raw_dir": tmp_path / "raw",
        "out_dir": tmp_path / "out",
    }


def test_cmd_process_sst_reports_missing_raw_files(monkeypatch, tmp_path: Path):
    from pipeline import cli

    def fake_process_sst(raw_dir, out_dir):
        raise FileNotFoundError(raw_dir / "missing.nc")

    monkeypatch.setattr(cli, "process_sst", fake_process_sst)

    code = cli.cmd_process_sst(Namespace(raw_dir=tmp_path / "raw", out_dir=tmp_path / "out"))

    assert code == 2


def test_cmd_sst_data_writes_site_data(monkeypatch, tmp_path: Path):
    from pipeline import cli

    sst_annual = tmp_path / "sea_of_oman_sst_annual.parquet"
    station_annual = tmp_path / "oman_stations_annual.parquet"
    salalah_daily = tmp_path / "salalah_daily.parquet"
    for path in (sst_annual, station_annual, salalah_daily):
        path.write_bytes(b"not-empty")
    out = tmp_path / "sst-data.js"
    calls = []

    def fake_write_sst_data(
        sst_annual_parquet,
        station_annual_parquet,
        salalah_daily_parquet,
        out_path,
    ):
        calls.append(
            (
                sst_annual_parquet,
                station_annual_parquet,
                salalah_daily_parquet,
                out_path,
            )
        )
        return out_path

    monkeypatch.setattr(cli, "write_sst_data", fake_write_sst_data)

    code = cli.cmd_sst_data(
        Namespace(
            sst_annual=sst_annual,
            station_annual=station_annual,
            salalah_daily=salalah_daily,
            out=out,
        )
    )

    assert code == 0
    assert calls == [(sst_annual, station_annual, salalah_daily, out)]


def test_cmd_sst_data_reports_missing_required_input(tmp_path: Path):
    from pipeline import cli

    station_annual = tmp_path / "oman_stations_annual.parquet"
    salalah_daily = tmp_path / "salalah_daily.parquet"
    for path in (station_annual, salalah_daily):
        path.write_bytes(b"not-empty")

    code = cli.cmd_sst_data(
        Namespace(
            sst_annual=tmp_path / "missing-sst.parquet",
            station_annual=station_annual,
            salalah_daily=salalah_daily,
            out=tmp_path / "sst-data.js",
        )
    )

    assert code == 2
