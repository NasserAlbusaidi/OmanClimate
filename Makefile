.PHONY: install fetch fetch-stations fetch-ghcn fetch-sst process process-stations process-ghcn process-sst process-all charts phase3-charts station-map-data personal-climate-data story-metrics-data sst-data diagnostics site test all clean

install:
	uv sync --all-extras

fetch:
	uv run python -m pipeline.cli fetch

fetch-stations:
	uv run python -m pipeline.cli fetch-stations

fetch-ghcn:
	uv run python -m pipeline.cli fetch-ghcn

fetch-sst:
	uv run python -m pipeline.cli fetch-sst

process:
	uv run python -m pipeline.cli process

process-stations:
	uv run python -m pipeline.cli process-stations

process-ghcn:
	uv run python -m pipeline.cli process-ghcn

process-sst:
	uv run python -m pipeline.cli process-sst

process-all: process process-ghcn

charts:
	uv run python -m pipeline.cli chart --out charts

phase3-charts:
	uv run python -m pipeline.cli chart-stations --out charts/stations

station-map-data:
	uv run python -m pipeline.cli station-map-data --out site/station-map-data.js

personal-climate-data:
	uv run python -m pipeline.cli personal-climate-data --out site/personal-climate-data.js

story-metrics-data:
	uv run python -m pipeline.cli story-metrics-data --out site/story-metrics-data.js

sst-data:
	uv run python -m pipeline.cli sst-data --out site/sst-data.js

diagnostics:
	uv run python -m pipeline.cli diagnose --with-rural --out charts/diagnostics

site: charts phase3-charts station-map-data personal-climate-data story-metrics-data sst-data diagnostics
	mkdir -p site/charts site/charts/diagnostics
	cp charts/*.png site/charts/
	cp charts/diagnostics/*.png site/charts/diagnostics/
	if ls charts/stations/*.png >/dev/null 2>&1; then mkdir -p site/charts/stations; cp charts/stations/*.png site/charts/stations/; fi

test:
	uv run pytest -q

all: fetch fetch-ghcn process-all charts

clean:
	rm -rf data/raw/open-meteo/*.json data/raw/open-meteo/*/*.json data/raw/ghcn/*.csv.gz data/raw/noaa-oisst/*.nc \
		data/processed/*.parquet data/processed/stations/*.parquet data/processed/sea_of_oman_sst_monthly.parquet data/processed/sea_of_oman_sst_annual.parquet \
		charts/*.png charts/diagnostics/*.png charts/stations/*.png \
		site/charts/*.png site/charts/diagnostics/*.png site/charts/stations/*.png \
		site/station-map-data.js site/personal-climate-data.js site/story-metrics-data.js site/sst-data.js
