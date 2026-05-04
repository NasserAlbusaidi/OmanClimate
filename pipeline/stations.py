"""Canonical Phase 3 Oman station catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Station:
    slug: str
    label: str
    latitude: float
    longitude: float
    category: str
    source_note: str


STATIONS: tuple[Station, ...] = (
    Station(
        slug="muscat",
        label="Muscat / Seeb",
        latitude=23.5859,
        longitude=58.4059,
        category="coastal urban airport",
        source_note="Existing Open-Meteo ERA5 grid cell used for Phase 1-2 validation.",
    ),
    Station(
        slug="salalah",
        label="Salalah",
        latitude=17.01505,
        longitude=54.09237,
        category="southern coastal monsoon city",
        source_note="Public latitude/longitude reference for Salalah, Dhofar.",
    ),
    Station(
        slug="sohar",
        label="Sohar",
        latitude=24.34745,
        longitude=56.70937,
        category="northern coastal city",
        source_note="Public latitude/longitude reference for Sohar, Al Batinah North.",
    ),
    Station(
        slug="sur",
        label="Sur",
        latitude=22.56667,
        longitude=59.52889,
        category="eastern coastal city",
        source_note="Public latitude/longitude reference for Sur, Ash Sharqiyah South.",
    ),
    Station(
        slug="nizwa",
        label="Nizwa",
        latitude=22.93333,
        longitude=57.53333,
        category="interior foothills city",
        source_note="Public latitude/longitude reference for Nizwa, Ad Dakhiliyah.",
    ),
    Station(
        slug="saiq",
        label="Saiq",
        latitude=23.0670,
        longitude=57.6330,
        category="mountain refuge comparator",
        source_note="Station/weather metadata cross-check for Saiq, Jabal Akhdar.",
    ),
)

_STATIONS_BY_SLUG = {station.slug: station for station in STATIONS}


def station_by_slug(slug: str) -> Station:
    """Return a configured station by slug."""
    try:
        return _STATIONS_BY_SLUG[slug]
    except KeyError as exc:
        known = ", ".join(sorted(_STATIONS_BY_SLUG))
        raise KeyError(f"Unknown station slug {slug!r}; expected one of: {known}") from exc
