"""Public documentation surface checks."""

from __future__ import annotations

from pathlib import Path


def test_docs_directory_only_contains_methodology():
    docs_files = sorted(
        path.relative_to("docs").as_posix()
        for path in Path("docs").rglob("*")
        if path.is_file()
    )

    assert docs_files == ["methodology.md"]


def test_readme_does_not_link_removed_docs():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docs/roadmap.md" not in readme
    assert "docs/superpowers" not in readme
    assert "docs/plans" not in readme
