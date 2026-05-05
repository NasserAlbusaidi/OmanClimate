"""Static-site wiring for Phase 4/5 generated data."""

from __future__ import annotations

from pathlib import Path
import struct


def test_static_site_wires_phase4_and_phase5_data():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert '<header class="site-hero">' in html
    assert 'class="site-eyebrow"' in html
    assert 'class="atlas-nav"' in html
    assert 'class="hero-meta-grid"' in html
    assert "1980-present fit window" in html
    assert "Methodology</a> — data sources" not in html
    assert "link TBD" not in html
    assert "Code in repository (link TBD)" not in html
    assert 'href="https://github.com/"' not in html
    assert 'href="https://github.com/NasserAlbusaidi/OmanClimate"' in html
    assert "By Nasser Albusaidi" in html
    assert "Last updated 2026-05-05" in html
    assert 'property="og:title" content="Oman Climate Atlas"' in html
    assert 'property="og:image" content="https://nasseralbusaidi.github.io/OmanClimate/social-preview.png"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert 'name="twitter:image" content="https://nasseralbusaidi.github.io/OmanClimate/social-preview.png"' in html
    assert 'href="#diagnostics"' in html
    assert 'id="diagnostics"' in html
    assert 'charts/diagnostics/window_comparison.png">See the diagnostic charts below' not in html
    assert 'id="what-changed"' in html
    assert 'id="change-year-range"' in html
    assert 'id="change-station"' in html
    assert 'id="oman-headline-cards"' in html
    assert 'id="station-change-cards"' in html
    assert 'id="change-comparison-chart"' in html
    assert 'id="quality-console"' in html
    assert "initWhatChangedHero" in html
    assert "renderChangeChart" in html
    assert 'src="personal-climate-data.js"' in html
    assert 'src="story-metrics-data.js"' in html
    assert 'src="sst-data.js"' in html
    assert 'id="personal-climate"' in html
    assert 'id="story-signals"' in html
    assert "Story Leads" in html
    assert "Metric summaries, not finished story pages" not in html
    assert "30°C nights" in html
    assert "standard tropical-night threshold is &gt;20 °C" in html
    assert "Tropical nights per year" not in html
    assert "Muscat / Seeb" not in html
    assert "Muscat (Seeb station)" in html
    assert 'id="sea-of-oman-sst"' in html
    assert "OMAN_PERSONAL_CLIMATE_DATA" in html
    assert "OMAN_STORY_METRICS_DATA" in html
    assert "OMAN_SST_DATA" in html


def test_social_preview_image_is_large_card_png():
    image = Path("site/social-preview.png")
    assert image.exists()

    with image.open("rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"
        length = struct.unpack(">I", handle.read(4))[0]
        assert handle.read(4) == b"IHDR"
        width, height = struct.unpack(">II", handle.read(8))

    assert length == 13
    assert (width, height) == (1200, 630)
