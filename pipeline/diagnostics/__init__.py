"""Phase 2.5 — data-quality diagnostics on the ERA5 reanalysis series.

Surfaces three artifacts hiding inside the multi-decade Muscat record:
1. Pre-1950 reanalysis instability (very few observations to constrain ERA5).
2. Possible step changes at 1979 (satellite era began) and 2015 (ERA5T boundary).
3. Urban-heat-island contribution at Seeb relative to a rural Oman comparator.

These exist as a separate module so the published charts can pull a
*trustworthy window* (currently 1980→) while diagnostic plots keep
showing the full series with caveats.
"""
