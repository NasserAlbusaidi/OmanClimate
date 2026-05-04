# Methodology

> Living document. Renders as `/methodology` on the site once the frontend lands (Phase 2+). Update with every meaningful change to data, thresholds, or analysis. Last updated: 2026-05-04.

## What this project is and is not

This is a long-term, public-facing climate analysis of Oman, starting with Muscat. It is built by a solo developer using publicly available reanalysis data. It is not a peer-reviewed scientific publication, and it is not a substitute for the work of climate scientists. Its job is to make multi-decade trends *legible* — and to be honest about what is known, what is uncertain, and what is excluded.

If you find an error, please open an issue on the repo.

## Three rules this project commits to

### 1. Always show uncertainty
Climate trends have error bars. When the data shows warming of (e.g.) 1.8 °C ± 0.4 °C over a 45-year window, the chart shows the ±. Trends through noisy data are drawn as bands, not as confident single lines. Where a single line is necessary for clarity, the methodology section under that chart explains the confidence interval and the method used to compute it.

Implementation in this project: linear trends use OLS with 95 % confidence bands; for robustness against outliers we cross-check with Theil–Sen slope estimates; trend significance is reported via Mann–Kendall.

### 2. Document the urban heat island
Muscat in 1980 was a small city. Muscat in 2026 is a sprawling metropolitan area of roughly 1.5 million people. Part of the warming observed at the Seeb airport grid cell is global climate change; part of it is the urban heat island as the city has grown up around the surrounding desert. **A trend at one urban station is not the same thing as a regional climate trend.**

Phase 3 begins that comparison by adding a consistent ERA5/Open-Meteo station catalog across Oman, including Saiq in the Hajar mountains. Saiq is a mountain/refuge comparator, not a controlled rural twin for Muscat, because the contrast also includes elevation and distance from the coast. Muscat-only charts still carry the UHI caveat; station-comparison charts describe the comparator explicitly.

### 3. Methodology page from day one
This document. It exists before any visualization does. It is updated as the project evolves. It is the page nobody reads except other rigorous people, and it is the page that makes the project trustworthy.

## Data sources

| source | role | period | notes |
|---|---|---|---|
| Open-Meteo Archive API | hourly weather for the configured Oman ERA5 station catalog | 1940-01-01 → present | ERA5-backed reanalysis from 1940 to ~5 days ago, blended with the ECMWF IFS forecast for the very recent tail. Free, no auth. Legacy Muscat cache files remain in `data/raw/open-meteo/`; Phase 3 station caches live in `data/raw/open-meteo/{station_slug}/`. |
| NOAA NCEI GHCN-Daily | station daily observations for Seeb International (`MUM00041256`, WMO `41256`) | 1983 → 2025 in the current NOAA inventory for TAVG/TMAX/TMIN | Pulled from NOAA's GHCN-Daily `by_station` archive as `data/raw/ghcn/MUM00041256.csv.gz`. The originally requested `OMM00041256` is treated as an alias; NOAA's station metadata lists Seeb under the FIPS-prefixed GHCN ID `MUM00041256`. Processed to `data/processed/muscat_ghcn_daily.parquet` and `data/processed/muscat_ghcn_annual.parquet`. Used as an observational cross-check against the ERA5-shaped series, not as a drop-in replacement for hourly reanalysis. |
| NOAA OISST v2.1 via NOAA PSL THREDDS NCSS | monthly Sea of Oman sea-surface temperature context | 1982 → present for annual summaries | NOAA's 0.25° daily OISST starts on 1981-09-01; this project uses NOAA's monthly mean OISST file derived from that daily product. It fetches a regional NetCDF subset for north 26.5, south 22.0, west 56.0, east 61.0 and starts annual claims in 1982 because 1981 is incomplete. |

The station catalog is defined once in `pipeline/stations.py`:

| slug | label | coordinates | role |
|---|---|---|---|
| `muscat` | Muscat / Seeb | 23.5859, 58.4059 | coastal urban airport reference |
| `salalah` | Salalah | 17.01505, 54.09237 | southern coastal monsoon city |
| `sohar` | Sohar | 24.34745, 56.70937 | northern coastal city |
| `sur` | Sur | 22.56667, 59.52889 | eastern coastal city |
| `nizwa` | Nizwa | 22.93333, 57.53333 | interior foothills city |
| `saiq` | Saiq | 23.0670, 57.6330 | mountain/refuge comparator |

## Variables fetched (hourly)

- `temperature_2m` — air temperature 2 m above ground, °C
- `dewpoint_2m` — dewpoint at 2 m, °C
- `relativehumidity_2m` — relative humidity, %

## Time-zone and daily-aggregation handling

The Open-Meteo Archive API is queried with `timezone=GMT`. All timestamps are converted to **Asia/Muscat (UTC+04:00, no DST)** *before* any daily bucketing. This matters: a hot afternoon at 14:00 local time is 10:00 UTC; if we bucket by UTC day, late-evening local hours of one day get charged to the previous calendar day, and trends in "daily peak" become subtly wrong. The conversion is implemented in `pipeline/process/timezones.py` and unit-tested.

GHCN-Daily is different. The NOAA station file is already daily: each row is a station date, element, value, flags, source flag, and optional `OBS-TIME`. We do **not** shift GHCN rows into Asia/Muscat hourly buckets because the hourly timestamps are not present. The GHCN date is treated as the archived station observation day. For temperature means, the processor uses unflagged `TAVG` when present; if `TAVG` is absent but unflagged `TMAX` and `TMIN` are present, it falls back to `(TMAX + TMIN) / 2`. Quality-flagged values are excluded.

This difference matters when comparing ERA5 and GHCN. ERA5 annual means here are means of 24 hourly 2 m temperature samples after UTC→Muscat local-day conversion. GHCN annual means are means of station daily summaries whose source and observation-day convention can vary through time. NOAA documents that `TAVG` from source `S` is an average of hourly readings for the period ending at 2400 UTC, while non-`S` daily averages can be computed by other fixed-hour or national-service conventions. The comparison notebook therefore treats the **shape of disagreement** as evidence in its own right; exact year-by-year equality is not expected. The notebook's x-axis starts in 1950 for ERA5, but the GHCN Seeb overlay only appears where NOAA has station temperature data.

## Thresholds and definitions

| term | definition |
|---|---|
| `temp_high` | maximum hourly temperature in the local calendar day |
| `temp_low`  | minimum hourly temperature in the local calendar day (the "overnight low" in colloquial use) |
| `temp_mean` | arithmetic mean of all hourly temperatures in the local day |
| `hours_above_30 / 35 / 40` | count of hourly samples with temperature **strictly greater than** 30 / 35 / 40 °C — equality is excluded |
| `wet_bulb_max` | maximum hourly wet-bulb temperature in the local day, computed via the Stull (2011) empirical formula |
| `hours_wetbulb_above_28` | count of hourly samples with wet-bulb **strictly greater than** 28 °C — a threshold associated with elevated heat-stroke risk for healthy adults during exertion |
| `days_overnight_low_above_30` | per year, count of days where `temp_low` > 30 °C — a proxy for "nights when bodies cannot recover from daytime heat" |
| `summer_length` | per year, the longest consecutive run of days with `temp_high` > 35 °C. Runs do not span calendar-year boundaries. |
| `summer_start` / `summer_end` | first and last calendar dates of the year's longest `temp_high > 35 °C` run. Both null when no day qualifies. Earlier-starting summers are a recognised climate fingerprint, which is why these two columns are exposed even though `summer_length` already captures the duration. |
| `heatwaves_3day_above_35` | per year, count of distinct **maximal** runs of ≥ 3 consecutive days with `temp_high` > 35 °C ("mild" heatwaves). One six-day stretch counts as one heatwave, not two. |
| `heatwaves_5day_above_40` | per year, count of distinct maximal runs of ≥ 5 consecutive days with `temp_high` > 40 °C ("severe" heatwaves). Threshold and minimum-length are placeholders chosen for legibility; both can be revised without breaking the schema. |

## Trend statistics and uncertainty bands

Per project rule 1, every chart that shows a multi-decade trend draws a confidence band, not a confident line. The mechanics:

- **OLS**: `scipy.stats.linregress` for slope and intercept; the 95 % confidence band on the regression line uses the mean-response standard error: `s · √(1/n + (x − x̄)² / Σ(x_j − x̄)²)`, with `s = √(SSE / (n − 2))` and a Student-t critical value at `n − 2` degrees of freedom. This is the band you should read as *uncertainty in the trend itself* — not a prediction interval for individual years.
- **Theil–Sen** (`scipy.stats.theilslopes`): a robust slope cross-check, resistant to outliers like the 1940s ERA5 anomaly. Charts may use either OLS or Theil–Sen as the displayed fit; both are exposed by the same plotting helper.
- **Mann–Kendall significance**: implemented as `scipy.stats.kendalltau(years, values)`, which for an evenly-spaced annual series gives the same statistic and p-value as the classical Mann–Kendall test (within tied-rank handling). Reported as `p<0.001`, `p=0.015`, etc., next to the slope in every chart legend.

Years with `n_days < 360` are dropped from trend fits (this excludes the partial current calendar year and any future stations with sparse early records).

The architectural commitment: there is one chart helper (`pipeline/viz/trend.py:plot_with_trend`) and it always emits a CI band + an MK p-value. There is no second helper that can draw a trend without uncertainty — that is enforced at the code level.

## Wet-bulb computation

Wet-bulb temperature is computed from dry-bulb temperature and relative humidity using the empirical fit from:

> Stull, R., 2011: *Wet-Bulb Temperature from Relative Humidity and Air Temperature*, J. Appl. Meteor. Climatol., 50, 2267–2269. DOI: 10.1175/JAMC-D-11-0143.1.

Validity envelope: air pressures near sea level (~101 kPa), T −20 to +50 °C, RH 5 to 99 %. The formula is accurate to within ~0.3 °C of psychrometric reference values across that envelope, which is sufficient for climate-trend analysis. We do **not** derive wet-bulb from first principles (the iterative psychrometric solution is a rabbit hole that adds no useful precision at this scale). The Python `metpy` library exposes the same formula and can be used as a cross-check.

The Stull formula is implemented from scratch in `pipeline/process/wet_bulb.py` and unit-tested against six reference points within ±0.3 °C.

## Missing-data handling

Current state: Open-Meteo's archive endpoint returns complete hourly series for the Muscat grid cell across the full requested range; we have not observed gaps in 1940–present. The pipeline does, however:

- Deduplicate on `time_utc` when concatenating yearly cache files (boundary hours bleed into the adjacent local day after timezone conversion; the dedup keeps the canonical reading).
- Carry an `n_hours` column on every daily row so that any future incomplete day is visible to downstream code.
- Carry an `n_days` column on every annual row; partial years (the current calendar year, before December has happened) are filtered out of trend-line plots.

If/when gaps appear in any future station, this section will document the gap-filling rule (or the choice to leave gaps as gaps).

For GHCN-Daily, annual aggregates carry `n_days`; comparison notebooks filter to `n_days >= 360` for both sources before overlaying annual mean temperature. GHCN rows with non-blank quality flags are dropped before daily aggregation, so `n_days` represents days with an accepted `TAVG` or a valid `TMAX`/`TMIN` fallback.

## The trustworthy fit window: 1980→present

Phase 2's first-pass charts (full 1940→2025 fits) showed a high–low–high U-shape that does not match the monotonic warming signature of real climate change. We ran four diagnostic checks (`pipeline/diagnostics/`) and concluded that the pre-1980 portion of the ERA5 series is **not trustworthy for trend estimation** at this location. Every published trend chart now fits its line on **points with year ≥ 1980** only. Pre-1980 points are still drawn (in muted style) so readers can see the data the cut excludes.

Evidence for the cut, all reproducible via `make diagnostics`:

1. **Step-change probe at 1950.** Welch's t-test on annual mean temperature, ten years before vs ten years after 1950: Δ = **−1.10 °C, p < 1 × 10⁻⁶**. Climate does not move that fast. This is the smoking gun for ERA5 reanalysis instability when very few weather stations were constraining the model in the Gulf.
2. **Step-change probe at 1979.** Same test at the satellite-era boundary: Δ = +0.22 °C, p = 0.11 — *not* significant. The series is internally consistent across the 1979 boundary, which is exactly what we want from the start of the trustworthy window.
3. **Step-change probe at 2015.** Δ = +0.98 °C, p < 5 × 10⁻⁵ — significant. This is *either* a real climate-acceleration signal in the Gulf *or* an ERA5 / ERA5T handover artifact. We currently treat it as ambiguous and document it; cross-validation against a second data source (NASA POWER) is on the roadmap to disambiguate.
4. **Window-stress test on every metric.** For five of ten tracked metrics, the OLS slope **flips sign** between the full and post-1979 windows; for several, p-values cross 0.05 in the same direction. Cleanest example: `heatwaves_5day_above_40` reads **−0.015/yr (p = 0.20, "no trend")** on the full series and **+0.031/yr (p < 0.001, "increasing")** post-1979 — a complete reversal driven entirely by the 1940s artifact. A trend that depends this much on which decade you start counting from is not a finding; it's a lesson about data hygiene.

We chose 1980 (rather than 1979) for the published cut as a round-number expression of "the satellite era". The exact year doesn't matter much — slopes are stable across 1979 ± 5.

## Urban heat island: what the rural comparator tells us

Adam (22.379 °N, 57.532 °E) is an interior Oman town ≈170 km inland on the gravel desert plain — same regional climate as Muscat, none of the urbanisation. We ran the identical pipeline against Adam (cached in `data/raw/open-meteo-adam/`, processed in-memory by `pipeline/diagnostics/rural.py`) and the results sharpen what is and is not a UHI signal:

- **The pre-1980 U-shape appears in Adam too.** The artifact is regional reanalysis instability, not a Muscat-specific UHI thing. This is the most important confirmation: it tells us the cut at 1980 is justified for *both* coastal and interior Oman, not just for Seeb's grown-up airport.
- **Adam runs hotter than Muscat in mean temperature** (interior vs coastal — the sea moderates Muscat). The UHI question at Seeb is not "is Muscat warmer than rural?" — it isn't — but "has the gap *narrowed* over time as Muscat urbanised?" The post-2000 Muscat–Adam gap in mean temperature is roughly stable, which suggests UHI at Seeb is real but modest at the resolution ERA5 provides; the regional climate signal dominates.
- **Tropical nights:** Muscat sees 25–80 nights/yr where the low never drops below 30 °C; Adam sees ≈0. This is a real coastal-climate fingerprint, not urbanisation — interior desert nights cool reliably even as days are blistering.
- **Wet-bulb hours > 28 °C:** Muscat hits ~600 h in 2024; Adam hits *zero* across the entire record. This is decisive evidence that Muscat's humid-heat trend is a coastal, sea-surface-temperature-driven climate signal, not an artifact and not urbanisation. **It is currently the most defensible single finding in the project.**

## Phase 4 and Phase 5 derived analytics

Personal climate comparisons use only years with `n_days >= 360` and `year >= 1980`. A selected birth year compares that year's value with the latest full year in the station annual parquet. The parent-generation baseline is exactly 30 years earlier. When that baseline would fall before 1980, the comparison is marked unavailable rather than computed from the untrusted early ERA5 window.

The personal panel exposes annual mean temperature, tropical nights, wet-bulb hours above 28 °C, longest summer run, and severe heatwave counts. These all come from `data/processed/oman_stations_annual.parquet`.

Story signal cards are metric summaries, not finished narrative pages. December cool-snap metrics use `data/processed/stations/muscat_daily.parquet`, where a December cool day means `temp_high < 25 °C`. Khareef stress metrics use `data/processed/stations/salalah_daily.parquet` for June through September and prioritize wet-bulb hours above 28 °C. The mountain-refuge metric compares Saiq with coastal Muscat and Sohar using tropical nights and humid-heat exposure.

## Phase 6 Sea of Oman SST context

Sea of Oman SST uses NOAA OISST v2.1 monthly mean 0.25° gridded sea-surface
temperature derived from the daily OISST product. The regional box is north 26.5, south 22.0, west 56.0, east 61.0.
The fetcher uses NOAA PSL THREDDS NetCDF Subset Service so the cache contains
one monthly-mean Sea of Oman subset rather than global source files.

Annual SST summaries begin in 1982. OISST v2.1 starts on 1981-09-01, so 1981
is not a complete annual comparison year. The anomaly baseline is 1982-2011.

The first SST analysis compares `sst_may_oct_mean` with Muscat and Sohar
wet-bulb hours, coastal tropical nights, and Salalah June-September wet-bulb
hours. It reports same-year and one-year-lag Pearson correlations. These are
association tests: they can show whether the shapes move together, but they do
not prove that SST caused the humid-heat trend.

## What this project does not (yet) account for

- **Cross-validation beyond Seeb station observations.** GHCN-Daily now gives one observational cross-check at Seeb International. NASA POWER is still a useful independent gridded cross-check and remains on the roadmap. Sea of Oman SST now provides contextual association tests for coastal humid heat, but it is not an independent air-temperature validation source.
- **The 2015 boundary.** The +0.98 °C step at 2015 (p < 1 × 10⁻⁴) is consistent with both real Gulf climate acceleration and an ERA5 / ERA5T handover discontinuity. Cannot be disambiguated from a single source.
- **Microclimate within Muscat.** Open-Meteo serves a single grid cell per coordinate. Mutrah, Qurum, Bawshar, and Seeb all behave differently in reality. We use the Seeb-area cell as the Muscat reference.
- **Diurnal asymmetry in trends.** Daily mean conceals the fact that nights warm faster than days in many regions. Tropical-nights chart partly captures this; a dedicated diurnal-asymmetry analysis is future work.
- **Controlled rural twin for Muscat.** Saiq is useful because it asks whether a mountain refuge is warming too, but it does not isolate urbanisation by itself. A better UHI-specific design would compare multiple coastal urban and non-urban grid cells with similar elevation and sea exposure.

## Reproducibility

- Code: `https://github.com/NasserAlbusaidi/OmanClimate`.
- Run `make install && make fetch && make process && make test` from a clean checkout for the legacy Muscat pipeline. The fetch step is idempotent — completed cache files are reused; only the current in-progress date chunk is re-fetched.
- Run `make fetch-stations && make process-stations && make phase3-charts` for the Phase 3 station workflow.
- Run `make station-map-data` to regenerate the static site's `site/station-map-data.js` summary used by the interactive station atlas.
- Run `make personal-climate-data && make story-metrics-data` to regenerate the Phase 4/5 site data packages.
- Run `make fetch-sst && make process-sst && make sst-data` to regenerate the Phase 6 Sea of Oman SST cache, parquet outputs, and static-site data package.
- Test suite: `uv run pytest -q`.

## Changelog

- **2026-05-02** — initial methodology page; Phase 1 (Muscat data pipeline) shipped.
- **2026-05-02** — Phase 2 ("feel it" charts) shipped. `annual.parquet` schema extended with `summer_start`, `summer_end`, `heatwaves_3day_above_35`, `heatwaves_5day_above_40`. Four charts rendered to `charts/`: threshold hours, tropical nights, summer season (length / start / end), heatwave counts. Trend bands (OLS 95 % CI), Theil–Sen cross-check, and Mann–Kendall p-values now mandatory on every trend chart via `pipeline/viz/trend.py:plot_with_trend`. Heatwave thresholds (mild ≥3 days > 35 °C, severe ≥5 days > 40 °C) are placeholders documented above and easy to revise.
- **2026-05-02** — Phase 2.5 (data-quality diagnostics). Discovered a U-shape in the 1940→2025 series that is incompatible with monotonic climate warming. Implemented `pipeline/diagnostics/{windows,step_changes,rural}.py` and `pipeline/viz/diagnostics.py`. Step-change tests located the artifact at the 1950 boundary (Δ = −1.10 °C, p < 1e-6) and confirmed cleanliness at 1979 (p = 0.11). Window-stress test showed five of ten metrics flip slope sign between full and post-1979 windows. Adam (rural Oman comparator) shows the same pre-1980 U-shape, confirming the artifact is regional reanalysis instability rather than urbanisation. **Decision:** all published trend charts now fit on `year ≥ 1980` only, with pre-1980 points still drawn in muted style so the cut is visible. Wet-bulb-hours signal at Muscat is unchanged by the cut, *and* is absent in rural Adam — a robust coastal-climate finding.
- **2026-05-03** — Added NOAA NCEI GHCN-Daily as a second source for Seeb International (`MUM00041256`, WMO `41256`; `OMM00041256` accepted as an alias). New source modules: `pipeline/fetch/ghcn.py`, `pipeline/process/ghcn.py`, and common annual overlay schema in `pipeline/process/common_schema.py`. The comparison notebook is `notebooks/compare_era5_ghcn.py`.
- **2026-05-03** — Phase 3 station workflow started. Added the canonical station catalog (`pipeline/stations.py`), station-aware Open-Meteo cache folders, `fetch-stations`, `process-stations`, and `chart-stations` CLI commands, Makefile targets, per-station parquet outputs under `data/processed/stations/`, combined annual output at `data/processed/oman_stations_annual.parquet`, and Phase 3 small-multiple chart renderers.
- **2026-05-03** — Phase 3 station atlas added. `pipeline/viz/station_map.py` now exports latest full-year values plus post-1980 trend summaries for each configured station, `pipeline cli station-map-data` writes the local-site-friendly `site/station-map-data.js`, and `site/index.html` includes an interactive Oman station map with metric switching and station detail readouts.
- **2026-05-03** — Phase 4/5 deep analytics started. Added personal climate comparison data and story-signal summaries for December cool snaps, Salalah khareef stress, and Saiq mountain-refuge comparisons. The static atlas now exposes these as compact panels while full story pages remain deferred until the strongest signals are selected.
- **2026-05-04** — Added GitHub Pages workflow documentation and Phase 6 Sea of Oman SST context from NOAA OISST v2.1. The SST workflow fetches a NOAA PSL THREDDS NCSS regional monthly-mean subset, builds monthly and annual parquet outputs, and exports `site/sst-data.js` for the static atlas.
