"""Static-site wiring for Phase 4/5 generated data."""

from __future__ import annotations

from pathlib import Path


def test_static_site_wires_phase4_and_phase5_data():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'src="personal-climate-data.js"' in html
    assert 'src="story-metrics-data.js"' in html
    assert 'src="sst-data.js"' in html
    assert 'id="personal-climate"' in html
    assert 'id="story-signals"' in html
    assert 'id="sea-of-oman-sst"' in html
    assert "OMAN_PERSONAL_CLIMATE_DATA" in html
    assert "OMAN_STORY_METRICS_DATA" in html
    assert "OMAN_SST_DATA" in html
