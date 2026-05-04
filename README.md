# Oman Climate Atlas

A reproducible climate atlas for Oman, built from public weather and sea-surface
temperature data. The project starts with Muscat/Seeb and expands across a small
station catalog covering coastal, interior, mountain, and khareef-influenced
locations.

The public site is a static atlas generated into `site/`, with no application
server required:

https://nasseralbusaidi.github.io/OmanClimate/

## What This Shows

- Long-term heat, tropical-night, heatwave, summer-length, and wet-bulb trends.
- A station comparison across Muscat, Salalah, Sohar, Sur, Nizwa, and Saiq.
- Personal climate comparisons from a selected birth year to the latest full
  year.
- Story-signal summaries for December cool snaps, Salalah khareef stress, and
  Saiq as a mountain-refuge comparator.
- Sea of Oman SST context from NOAA OISST, including associations with coastal
  humid-heat metrics.

The project is designed to be legible rather than overconfident. Published trend
fits use the trusted `year >= 1980` window and drop incomplete years with
`n_days < 360`. Pre-1980 ERA5/Open-Meteo points remain useful context, but they
are not used for the public trend lines because diagnostic tests found unstable
early-reanalysis behavior in this region.

## Data Sources

| Source | Use | Output |
|---|---|---|
| Open-Meteo Archive API | ERA5-backed hourly temperature, humidity, and dewpoint for Oman stations | `data/raw/open-meteo/`, `data/processed/*.parquet` |
| NOAA NCEI GHCN-Daily | Seeb International station observation cross-check | `data/raw/ghcn/`, `data/processed/muscat_ghcn_*.parquet` |
| NOAA OISST v2.1 via NOAA PSL THREDDS | Sea of Oman monthly sea-surface temperature context | `data/raw/noaa-oisst/`, `data/processed/sea_of_oman_sst_*.parquet` |

Raw and processed data files are ignored because they are regenerated from the
public sources. The committed `site/` directory contains the compact static
payload used for GitHub Pages.

## Repository Layout

```text
pipeline/              Fetching, processing, analysis, diagnostics, and charting
tests/                 Pytest coverage for data processing, analysis, CLI, and site outputs
docs/methodology.md    Detailed methodology, caveats, thresholds, and changelog
site/                  Static atlas artifact published by GitHub Pages
notebooks/             Exploratory source-comparison scripts
data/                  Local regenerated caches and parquet outputs
charts/                Local regenerated chart working directory
```

## Quick Start

Install the project with `uv`:

```bash
make install
```

Run the complete local data pipeline:

```bash
make fetch
make fetch-ghcn
make fetch-stations
make fetch-sst
make process
make process-ghcn
make process-stations
make process-sst
make site
```

Open the static atlas locally:

```bash
open site/index.html
```

Run the test suite:

```bash
make test
```

## Common Commands

```bash
make charts                 # Muscat chart set
make phase3-charts          # Multi-station charts
make station-map-data       # Static station-map payload
make personal-climate-data  # Static personal-comparison payload
make story-metrics-data     # Static story-signal payload
make sst-data               # Static Sea of Oman SST payload
make diagnostics            # Window, step-change, and rural-comparator diagnostics
make clean                  # Remove regenerated local data/chart/site artifacts
```

## Methodology

The detailed methodology lives in `docs/methodology.md`. It documents:

- timezone conversion before daily aggregation,
- wet-bulb calculation and thresholds,
- trend statistics and uncertainty bands,
- the trusted 1980-present trend window,
- station roles and urban-heat-island caveats,
- GHCN and OISST source handling,
- current limitations and future cross-checks.

## Deployment

The repository includes `.github/workflows/pages.yml`. On pushes to `main`, the
workflow uploads the committed `site/` directory to GitHub Pages. It does not run
the Python pipeline in CI; regenerate and commit `site/` whenever the published
atlas data changes.

## License

No license has been selected yet. Until a license is added, the code and content
are publicly visible but not explicitly licensed for reuse.
