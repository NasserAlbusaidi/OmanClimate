"""Deployment workflow contracts for the static atlas."""

from __future__ import annotations

from pathlib import Path


def test_github_pages_workflow_publishes_site_directory():
    workflow = Path(".github/workflows/pages.yml")
    text = workflow.read_text(encoding="utf-8")

    assert "actions/checkout@v6" in text
    assert "actions/configure-pages@v5" in text
    assert "actions/upload-pages-artifact@v4" in text
    assert "path: site" in text
    assert "actions/deploy-pages@v4" in text
    assert "pages: write" in text
    assert "id-token: write" in text
    assert "test -f site/index.html" in text
    assert "test -f site/station-map-data.js" in text
    assert "test -f site/personal-climate-data.js" in text
    assert "test -f site/story-metrics-data.js" in text
    assert "test -f site/sst-data.js" in text
