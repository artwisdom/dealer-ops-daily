"""Phase 4 self-improvement loop tests. All offline."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from pipeline import analytics
from pipeline.config import settings
from pipeline.loops import (
    affiliate_roi,
    format_evolution,
    growth_channels,
    open_rate_drift,
    source_quality,
    subject_lines,
)
from pipeline.models import Affiliate, IssueAnalytics


# --- Loop 1: source quality --------------------------------------------

def test_source_quality_no_op_with_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(source_quality, "ATTRIBUTION_FILE", tmp_path / "source_attribution.jsonl")
    deltas = source_quality.adjust_weights(dry_run=True)
    assert deltas == {}


def test_source_quality_records_attribution(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(source_quality, "ATTRIBUTION_FILE", tmp_path / "source_attribution.jsonl")
    source_quality.record_attribution(date(2026, 4, 1), "story_1", "FTC", click_count=12, recipients=1500)
    rows = json.loads(json.dumps([
        json.loads(line) for line in (tmp_path / "source_attribution.jsonl").read_text().splitlines()
    ]))
    assert len(rows) == 1
    assert rows[0]["source_id"] == "FTC"


def test_source_quality_adjusts_weights_with_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(source_quality, "ATTRIBUTION_FILE", tmp_path / "source_attribution.jsonl")
    # Copy sources.yaml to a writable temp location and point settings at it
    src_yaml = tmp_path / "sources.yaml"
    src_yaml.write_text(yaml.safe_dump({
        "version": 1, "niche": "test", "last_verified": "2026-04-20",
        "sources": [
            {"name": "Star", "category": "test", "url": "x", "rss": None, "weight": 5, "update_frequency": "daily"},
            {"name": "Dud",  "category": "test", "url": "y", "rss": None, "weight": 5, "update_frequency": "daily"},
        ],
    }))
    monkeypatch.setattr(settings, "sources_file", src_yaml)

    today = date.today()
    for i in range(7):
        source_quality.record_attribution(today - timedelta(days=i), f"s{i}", "Star", click_count=20, recipients=1000)
        source_quality.record_attribution(today - timedelta(days=i), f"d{i}", "Dud", click_count=0, recipients=1000)

    deltas = source_quality.adjust_weights(dry_run=False)
    assert deltas.get("Star", 0) == 1
    assert deltas.get("Dud", 0) == -1
    written = yaml.safe_load(src_yaml.read_text())
    by_name = {s["name"]: s["weight"] for s in written["sources"]}
    assert by_name["Star"] == 6
    assert by_name["Dud"] == 4


# --- Loop 2: subject lines ---------------------------------------------

def test_subject_lines_no_data_returns_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(subject_lines, "SUBJECT_HISTORY_FILE", tmp_path / "subject_history.jsonl")
    out = subject_lines.analyze_and_apply(dry_run=True)
    assert out["applied"] is False


def test_subject_lines_dry_analyze_with_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(subject_lines, "SUBJECT_HISTORY_FILE", tmp_path / "subject_history.jsonl")
    today = date.today()
    for i in range(25):
        subject_lines.record_subject_result(
            today - timedelta(days=i),
            "Mon: 5 stories",
            "5 things to do today in F&I",
            "FTC settles three CARS Rule cases",
            winner_idx=i % 3,
            winner_open_rate=0.30 + (i % 5) / 100,
        )
    out = subject_lines.analyze_and_apply(dry_run=True)
    # 25 records is enough for medium confidence
    assert "analysis" in out
    assert out["analysis"].get("rules"), "should produce some rules"


# --- Loop 3: format evolution ----------------------------------------

def test_format_evolution_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "issue_output_dir", tmp_path / "issues")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    out = format_evolution.analyze_and_propose(dry_run=True)
    assert out["proposed"] is False


def test_format_evolution_proposes_when_count_too_high(tmp_path, monkeypatch):
    issue_dir = tmp_path / "issues"
    issue_dir.mkdir()
    monkeypatch.setattr(settings, "issue_output_dir", issue_dir)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "system_prompt_file", tmp_path / "prompts" / "system.md")
    # 12 issues with 8 stories each → exceeds 6.5 threshold → proposal
    for i in range(12):
        d = date(2026, 4, 1) + timedelta(days=i)
        issue_dir.joinpath(f"{d.isoformat()}.json").write_text(json.dumps({
            "issue_title": f"Day {i}", "cold_open": "test",
            "metadata": {"story_count": 8, "word_count_estimate": 1000},
            "sections": [{"name": "store-ops", "stories": []}],
            "tool_of_day": {},
        }))
    out = format_evolution.analyze_and_propose(dry_run=True)
    assert out["proposed"] is True
    assert "Cap story count" in out["proposal"]["proposed_change"]


# --- Loop 4: affiliate ROI -------------------------------------------

def test_affiliate_rotation_keeps_when_no_underperformer(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(affiliate_roi, "INVENTORY_FILE", tmp_path / "affiliates.json")
    monkeypatch.setattr(affiliate_roi, "WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr(affiliate_roi, "CLICKS_FILE", tmp_path / "clicks.jsonl")
    (tmp_path / "affiliates.json").write_text(json.dumps([{
        "product_id": "ok", "product_name": "OK Tool", "one_liner": "x", "url": "x",
        "semantic_tags": [], "disclosure_type": "Affiliate", "active": True,
    }]))
    out = affiliate_roi.rotate(dry_run=True)
    assert out == {"retired": [], "promoted": []}


def test_affiliate_rotation_swaps_underperformer_with_watchlist(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(affiliate_roi, "INVENTORY_FILE", tmp_path / "affiliates.json")
    monkeypatch.setattr(affiliate_roi, "WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr(affiliate_roi, "CLICKS_FILE", tmp_path / "clicks.jsonl")

    # Bad affiliate, 10 placements, 0 clicks
    (tmp_path / "affiliates.json").write_text(json.dumps([{
        "product_id": "bad", "product_name": "Bad", "one_liner": "x", "url": "x",
        "semantic_tags": [], "disclosure_type": "Affiliate", "active": True,
    }]))
    (tmp_path / "watchlist.json").write_text(json.dumps([{
        "product_id": "next", "product_name": "Next", "one_liner": "x", "url": "x",
        "semantic_tags": [], "disclosure_type": "Affiliate", "active": False,
    }]))
    for i in range(10):
        affiliate_roi.record_click("bad", click_count=0, impressions=1000)

    out = affiliate_roi.rotate(dry_run=False)
    assert "bad" in out["retired"]
    assert "next" in out["promoted"]

    inv = json.loads((tmp_path / "affiliates.json").read_text())
    by_id = {a["product_id"]: a for a in inv}
    assert by_id["bad"]["active"] is False
    assert by_id["next"]["active"] is True


# --- Loop 5: growth channels ---------------------------------------

def test_growth_channels_insufficient_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(growth_channels, "SUB_ATTRIBUTION_FILE", tmp_path / "sub_attribution.jsonl")
    out = growth_channels.report(dry_run=True)
    assert out["recommendation"] == "insufficient_data"


def test_growth_channels_recommends_pause_for_underwater_paid(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(growth_channels, "SUB_ATTRIBUTION_FILE", tmp_path / "sub_attribution.jsonl")
    growth_channels.record_subscriber_event("sparkloop", new_subs=100, cost=500.0, revenue_attributed=200.0)
    growth_channels.record_subscriber_event("boost", new_subs=80, cost=80.0, revenue_attributed=320.0)
    out = growth_channels.report(dry_run=True)
    rec = out["recommendation"].lower()
    assert "boost" in rec  # winner mentioned
    assert "sparkloop" in rec  # loser mentioned


# --- Loop 6: open-rate drift ------------------------------------

def test_drift_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(analytics, "LOCAL_STATE", tmp_path / "analytics.json")
    out = open_rate_drift.run(dry_run=True)
    assert out["alerted"] is False


def test_drift_detected_when_recent_drops_significantly(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(analytics, "LOCAL_STATE", tmp_path / "analytics.json")
    monkeypatch.setattr(settings, "issue_output_dir", tmp_path / "issues")
    today = date.today()
    records = []
    # 30-day baseline: 30% open rate
    for i in range(8, 30):
        records.append(IssueAnalytics(
            issue_date=(today - timedelta(days=i)).isoformat(),
            beehiiv_post_id=f"old{i}",
            sent_at=datetime.now(timezone.utc),
            recipients=1500, opens=450, open_rate=0.30, clicks=80, click_rate=0.05,
        ).model_dump(mode="json"))
    # Last 7 days: 20% open rate (33% drop)
    for i in range(0, 7):
        records.append(IssueAnalytics(
            issue_date=(today - timedelta(days=i)).isoformat(),
            beehiiv_post_id=f"new{i}",
            sent_at=datetime.now(timezone.utc),
            recipients=1500, opens=300, open_rate=0.20, clicks=60, click_rate=0.04,
        ).model_dump(mode="json"))
    (tmp_path / "analytics.json").write_text(json.dumps(records, default=str))

    status = open_rate_drift.check()
    assert status.drift_detected
    assert status.relative_drop > 0.15
