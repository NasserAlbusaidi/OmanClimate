"""Render the static social preview image for the public atlas."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle

from pipeline.stations import STATIONS
from pipeline.viz.oman_outline import OMAN_OUTLINE_RINGS, outline_bounds


WIDTH_PX = 1200
HEIGHT_PX = 630
DPI = 100


def _project(
    longitude: float,
    latitude: float,
    *,
    bounds: dict[str, float],
    box: tuple[float, float, float, float],
) -> tuple[float, float]:
    x0, y0, x1, y1 = box
    x = x0 + (
        (longitude - bounds["longitude_min"])
        / (bounds["longitude_max"] - bounds["longitude_min"])
    ) * (x1 - x0)
    y = y0 + (
        1
        - (
            (latitude - bounds["latitude_min"])
            / (bounds["latitude_max"] - bounds["latitude_min"])
        )
    ) * (y1 - y0)
    return x, y


def render_social_preview(out_path: Path) -> Path:
    """Render a 1200x630 PNG social card for Open Graph/Twitter previews."""
    paper = "#f4f1ea"
    panel = "#fffdf8"
    ink = "#171817"
    muted = "#66706d"
    line = "#cbc7ba"
    sea = "#d9edf0"
    land = "#eadfc8"
    red = "#b84a35"
    blue = "#294f73"
    teal = "#0f766e"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(WIDTH_PX / DPI, HEIGHT_PX / DPI), dpi=DPI, facecolor=paper)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=paper, edgecolor="none"))
    for x in [index / 24 for index in range(25)]:
        ax.plot([x, x], [0, 1], color="#e0dbcf", linewidth=0.8, alpha=0.65)
    for y in [index / 14 for index in range(15)]:
        ax.plot([0, 1], [y, y], color="#e0dbcf", linewidth=0.8, alpha=0.65)

    ax.plot([0.055, 0.945], [0.90, 0.90], color=ink, linewidth=2.2)
    ax.plot([0.055, 0.945], [0.12, 0.12], color=ink, linewidth=2.2)
    ax.text(
        0.06,
        0.93,
        "PUBLIC REANALYSIS ATLAS / OMAN STATION CATALOG",
        color=red,
        fontsize=13,
        fontweight="bold",
        family="DejaVu Sans",
        va="center",
    )
    ax.text(
        0.06,
        0.72,
        "Oman\nClimate\nAtlas",
        color=ink,
        fontsize=74,
        fontweight="bold",
        family="DejaVu Serif",
        va="center",
        linespacing=0.82,
    )
    ax.text(
        0.06,
        0.31,
        "What changed since 1980?",
        color=ink,
        fontsize=29,
        fontweight="bold",
        family="DejaVu Sans",
        va="center",
    )
    ax.text(
        0.06,
        0.245,
        "ERA5-backed hourly climate signals, GHCN station validation,\n"
        "and Sea of Oman SST context in a static public atlas.",
        color=muted,
        fontsize=18,
        family="DejaVu Sans",
        va="top",
        linespacing=1.35,
    )

    meta = [
        ("FIT WINDOW", "1980-present"),
        ("STATIONS", "6 Oman grid cells"),
        ("OUTPUT", "static GitHub Pages"),
    ]
    for index, (label, value) in enumerate(meta):
        x = 0.06 + index * 0.155
        ax.text(x, 0.155, label, color=muted, fontsize=9.5, fontweight="bold", family="DejaVu Sans")
        ax.text(x, 0.125, value, color=ink, fontsize=14, family="DejaVu Sans")

    map_box = (0.565, 0.14, 0.94, 0.86)
    ax.add_patch(
        Rectangle(
            (map_box[0], map_box[1]),
            map_box[2] - map_box[0],
            map_box[3] - map_box[1],
            facecolor=sea,
            edgecolor=line,
            linewidth=1.2,
        )
    )
    bounds = outline_bounds()
    for ring in OMAN_OUTLINE_RINGS:
        points = [_project(lon, lat, bounds=bounds, box=map_box) for lon, lat in ring]
        ax.add_patch(Polygon(points, closed=True, facecolor=land, edgecolor="#918b7a", linewidth=1.3))

    station_colors = {
        "muscat": red,
        "salalah": teal,
        "sohar": blue,
        "sur": "#a8731d",
        "nizwa": "#637247",
        "saiq": "#6f5b9a",
    }
    for station in STATIONS:
        x, y = _project(station.longitude, station.latitude, bounds=bounds, box=map_box)
        color = station_colors.get(station.slug, ink)
        ax.add_patch(Circle((x, y), 0.0105, facecolor=color, edgecolor=panel, linewidth=2.2))

    ax.text(
        0.585,
        0.805,
        "Station atlas",
        color=ink,
        fontsize=20,
        fontweight="bold",
        family="DejaVu Sans",
    )
    ax.text(
        0.585,
        0.765,
        "Muscat / Salalah / Sohar / Sur / Nizwa / Saiq",
        color=muted,
        fontsize=12.5,
        family="DejaVu Sans",
    )
    ax.text(
        0.585,
        0.185,
        "nasseralbusaidi.github.io/OmanClimate",
        color=ink,
        fontsize=15,
        fontweight="bold",
        family="DejaVu Sans",
    )

    fig.savefig(out_path, dpi=DPI, facecolor=paper)
    plt.close(fig)
    return out_path
