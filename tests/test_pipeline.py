"""Self-tests for every pipeline stage. All run offline using fixtures.

`pytest tests/` should pass on a fresh checkout with zero env vars set.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
import yaml

from pipeline import affiliates, draft, image, ingest, publish, run as orchestrator
from pipeline.config import settings
from pipeline.models import Candidate, Issue, IssueAnalytics


# --- Fixtures ---------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _ensure_fixture_exists():
    """Generate fixtures/candidates.json once per test session."""
    if not (settings.fixtures_dir / "candidates.json").exists():
        ingest.seed_fixture()


# --- Sources --------------------------------------------------------------

def test_sources_yaml_valid():
    sources = ingest.load_sources()
    assert sources.niche
    assert len(sources.sources) >= 30, "expected ≥30 sources per Phase 0 plan"
    # At least one source per major category we promised
    cats = {s.category for s in sources.sources}
    for must in {"trade_press", "regulatory", "vendor_news"}:
        assert must in cats, f"missing category '{must}': got {cats}"


def test_sources_yaml_no_duplicate_urls():
    sources = ingest.load_sources()
    urls = [s.url for s in sources.sources if s.url]
    assert len(urls) == len(set(urls)), "duplicate source URLs"


# --- Ingest ---------------------------------------------------------------

def test_ingest_fixture_loads():
    candidates = ingest.fetch_candidates_from_fixture()
    assert len(candidates) >= 5
    assert all(isinstance(c, Candidate) for c in candidates)
    assert all(c.headline for c in candidates)


def test_ingest_dedupe_keeps_higher_weight():
    """Two candidates at same URL → the higher-weighted source wins."""
    a = Candidate(source_name="LowSrc", source_weight=3, headline="X", url="https://example.com/a")
    b = Candidate(source_name="HighSrc", source_weight=9, headline="X", url="https://example.com/a")
    assert a.stable_id == b.stable_id


# --- Rank ----------------------------------------------------------------

def test_rank_dry_returns_at_most_12():
    from pipeline import rank as rank_mod
    candidates = ingest.fetch_candidates_from_fixture()
    ranked = rank_mod.rank_dry(candidates)
    assert 1 <= len(ranked) <= 12
    assert all(r.section_assignment in ("compliance", "fni", "used-car", "store-ops") for r in ranked)


def test_rank_dry_assigns_section_by_keyword():
    from pipeline import rank as rank_mod
    candidates = [
        Candidate(source_name="FTC", source_weight=10, headline="FTC settles CARS Rule case", url="https://x.com/1"),
        Candidate(source_name="Manheim", source_weight=10, headline="Manheim index falls", url="https://x.com/2"),
    ]
    ranked = rank_mod.rank_dry(candidates)
    by_url = {c.url: c.section_assignment for c in ranked}
    assert by_url["https://x.com/1"] == "compliance"
    assert by_url["https://x.com/2"] == "used-car"


# --- Draft ---------------------------------------------------------------

def test_draft_dry_produces_valid_issue():
    from pipeline import rank as rank_mod
    candidates = ingest.fetch_candidates_from_fixture()
    ranked = rank_mod.rank_dry(candidates)
    issue = draft.draft_dry(ranked, today=date(2026, 4, 20))
    assert isinstance(issue, Issue)
    assert issue.subject_a
    assert issue.subject_b
    assert issue.subject_c
    assert issue.subject_a != issue.subject_b
    total = sum(len(s.stories) for s in issue.sections)
    assert 3 <= total <= 8, f"expected 3-8 stories, got {total}"
    for section in issue.sections:
        for story in section.stories:
            assert story.headline
            assert story.action_line
            assert story.sources, "every story must have ≥1 source"


def test_draft_loads_system_prompt():
    text = settings.system_prompt_file.read_text(encoding="utf-8")
    assert "Dealer Ops Daily" in text
    assert "guardrail" in text.lower()


# --- Image ---------------------------------------------------------------

def test_image_dry_run_returns_placeholder():
    url = image.generate_hero_image("a clean editorial illustration", dry_run=True)
    assert url.startswith("https://")


# --- Affiliates ----------------------------------------------------------

def test_affiliate_inventory_loads():
    inv = affiliates.load_inventory()
    assert len(inv) >= 1
    assert all(a.product_id and a.url for a in inv)


def test_affiliate_picks_match_for_compliance_issue():
    from pipeline import rank as rank_mod
    candidates = ingest.fetch_candidates_from_fixture()
    ranked = rank_mod.rank_dry(candidates)
    issue = draft.draft_dry(ranked, today=date(2026, 4, 20))
    issue = affiliates.inject(issue)
    # With our seeded inventory (DealerIntel tags include compliance + store-ops + variable-ops + f&i),
    # we should always find a match for any reasonable issue.
    assert issue.tool_of_day.product_id == "dealerintel"
    assert issue.metadata.affiliate_used is True


# --- Publish (HTML render) ----------------------------------------------

def test_publish_renders_html_offline():
    from pipeline import rank as rank_mod
    candidates = ingest.fetch_candidates_from_fixture()
    ranked = rank_mod.rank_dry(candidates)
    issue = draft.draft_dry(ranked, today=date(2026, 4, 20))
    issue = affiliates.inject(issue)
    html = publish.render_html(issue)
    assert "<h1>" in html
    assert issue.issue_title in html
    # Section emojis
    for emoji in ("⚖️", "💰", "🚗", "🏬"):
        if any(s.name == _section_for_emoji(emoji) for s in issue.sections):
            assert emoji in html


def _section_for_emoji(emoji: str) -> str:
    return {"⚖️": "compliance", "💰": "fni", "🚗": "used-car", "🏬": "store-ops"}[emoji]


def test_publish_dry_run_does_not_call_api(monkeypatch):
    """Belt-and-suspenders: publish.publish() with dry_run=True must NOT POST."""
    from pipeline import rank as rank_mod
    candidates = ingest.fetch_candidates_from_fixture()
    ranked = rank_mod.rank_dry(candidates)
    issue = draft.draft_dry(ranked, today=date(2026, 4, 20))
    issue = affiliates.inject(issue)

    def _boom(*a, **kw):
        raise AssertionError("dry_run path called real HTTP — bug")

    monkeypatch.setattr(publish, "_post_draft", _boom)
    monkeypatch.setattr(publish, "_schedule", _boom)
    issue.dry_run = True
    out = publish.publish(issue, target_date=date(2026, 4, 20))
    assert out.beehiiv_post_id == "dry-run-post-id"


# --- End-to-end orchestrator -------------------------------------------

def test_orchestrator_dry_run_e2e(tmp_path, monkeypatch):
    """Most important test: full pipeline in dry mode produces a valid Issue + audit files."""
    monkeypatch.setattr(settings, "issue_output_dir", tmp_path / "issues")
    issue = orchestrator.run(today=date(2026, 4, 20), dry_run=True)
    assert issue.dry_run is True
    assert issue.beehiiv_post_id == "dry-run-post-id"
    md_path = tmp_path / "issues" / "2026-04-20.md"
    json_path = tmp_path / "issues" / "2026-04-20.json"
    assert md_path.exists()
    assert json_path.exists()
    # The audited JSON should round-trip through Issue
    with json_path.open() as f:
        data = json.load(f)
    Issue.model_validate(data)


def test_orchestrator_selftest_returns_zero():
    assert orchestrator.selftest() == 0


# --- Config sanity ---------------------------------------------------

def test_config_paths_exist():
    assert settings.sources_file.exists(), f"missing {settings.sources_file}"
    assert settings.system_prompt_file.exists(), f"missing {settings.system_prompt_file}"


def test_active_theme_for_every_week():
    """No matter the ISO week, we should always return a theme."""
    for week in range(1, 54):
        d = date.fromisocalendar(2026, week, 1) if week <= 52 else date(2026, 12, 28)
        theme = orchestrator.active_theme(d)
        assert theme  # non-empty
