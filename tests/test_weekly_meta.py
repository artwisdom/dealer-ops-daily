"""Sunday weekly meta-issue tests."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipeline import weekly_meta
from pipeline.config import settings
from pipeline.models import Issue


def _seed_week_of_audits(issue_dir: Path, week_end: date, count: int = 5):
    """Write `count` issue audit JSONs into issue_dir, dated week_end and back."""
    issue_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        d = week_end - timedelta(days=i)
        payload = {
            "issue_title": f"Dealer Ops Daily — Day {i}",
            "cold_open": f"Day {i} cold open",
            "metadata": {"story_count": 5, "word_count_estimate": 700},
            "sections": [
                {"name": "compliance", "stories": [{
                    "headline": f"Story {i} top",
                    "body": f"Day {i} story body",
                    "action_line": f"Do thing {i}",
                    "sources": [{"outlet": "Test", "url": f"https://x.com/{i}"}],
                    "source_ids": [],
                }]}
            ],
            "tool_of_day": {"product_id": "dealerintel"},
        }
        (issue_dir / f"{d.isoformat()}.json").write_text(json.dumps(payload))


def test_weekly_meta_dry_produces_valid_issue(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "issue_output_dir", tmp_path / "issues")
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(weekly_meta.analytics, "LOCAL_STATE", tmp_path / "data" / "analytics.json")
    today = date(2026, 4, 26)
    _seed_week_of_audits(tmp_path / "issues", today, count=5)

    issue = weekly_meta.generate_dry(today)
    assert isinstance(issue, Issue)
    assert issue.dry_run is True
    section_names = [s.name for s in issue.sections]
    assert "top-stories" in section_names
    assert "data-recap" in section_names
    assert "watch-next-week" in section_names

    # Top-stories section should have ≤3 stories pulled from audits
    top = next(s for s in issue.sections if s.name == "top-stories")
    assert 1 <= len(top.stories) <= 3


def test_weekly_meta_dry_handles_empty_week(tmp_path, monkeypatch):
    """If no audits exist, weekly meta still produces a structurally valid placeholder."""
    monkeypatch.setattr(settings, "issue_output_dir", tmp_path / "issues")
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(weekly_meta.analytics, "LOCAL_STATE", tmp_path / "data" / "analytics.json")
    issue = weekly_meta.generate_dry(date(2026, 4, 26))
    assert isinstance(issue, Issue)
    # Placeholder story is still present
    top = next(s for s in issue.sections if s.name == "top-stories")
    assert len(top.stories) == 1


def test_weekly_meta_run_dry_e2e(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "issue_output_dir", tmp_path / "issues")
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(weekly_meta.analytics, "LOCAL_STATE", tmp_path / "data" / "analytics.json")
    today = date(2026, 4, 26)
    _seed_week_of_audits(tmp_path / "issues", today, count=5)
    issue = weekly_meta.run(today, dry_run=True)
    assert issue.beehiiv_post_id == "dry-run-post-id"
    audit_md = tmp_path / "issues" / f"{today.isoformat()}.md"
    assert audit_md.exists()
    # The Sunday hero image in dry-run is the placeholder
    assert issue.hero_image_url and issue.hero_image_url.startswith("https://")


def test_weekly_meta_selftest_returns_zero():
    assert weekly_meta.selftest() == 0


def test_weekly_meta_prompt_file_exists():
    """Belt-and-suspenders — the Opus weekly prompt must be present in the repo."""
    assert weekly_meta.WEEKLY_PROMPT_FILE.exists()
    text = weekly_meta.WEEKLY_PROMPT_FILE.read_text(encoding="utf-8")
    assert "weekly meta-issue" in text.lower() or "sunday meta" in text.lower()
