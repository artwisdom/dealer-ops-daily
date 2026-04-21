"""Phase 3 self-tests. All offline."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipeline import analytics
from pipeline.config import settings
from pipeline.growth import ad_network, boosts, outreach, sparkloop, sponsors
from pipeline.models import Affiliate, IssueAnalytics


# --- Ad Network -----------------------------------------------------------

def test_ad_network_dry_run_not_eligible_with_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(ad_network, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    elig = ad_network.check_eligibility(dry_run=True)
    assert not elig.eligible
    assert elig.subscribers == 0


def test_ad_network_eligible_with_threshold_data(tmp_path, monkeypatch):
    monkeypatch.setattr(ad_network, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(analytics, "LOCAL_STATE", tmp_path / "analytics.json")
    # Seed analytics so dry-run reads >= threshold
    records = []
    for i in range(7):
        records.append(IssueAnalytics(
            issue_date=(date.today() - timedelta(days=i)).isoformat(),
            beehiiv_post_id=f"p{i}",
            sent_at=datetime.now(timezone.utc),
            recipients=1500, opens=500, open_rate=0.30, clicks=80, click_rate=0.05,
        ).model_dump(mode="json"))
    (tmp_path / "analytics.json").write_text(json.dumps(records, default=str))
    elig = ad_network.check_eligibility(dry_run=True)
    assert elig.eligible, elig.blocking_reasons


def test_ad_network_state_prevents_resubmission(tmp_path, monkeypatch):
    monkeypatch.setattr(ad_network, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    (tmp_path / "state.json").write_text(json.dumps({ad_network.STATE_KEY: "2026-04-01T00:00:00Z"}))
    msg = ad_network.maybe_submit(dry_run=True)
    assert "Already submitted" in msg


# --- Boosts ------------------------------------------------------------

def test_boost_picker_vetoes_crypto():
    offers = boosts.fetch_marketplace_fixture()
    crypto = next(o for o in offers if "crypto" in o["name"].lower())
    assert boosts._veto(crypto) is True


def test_boost_picker_chooses_on_niche_offer():
    offers = boosts.fetch_marketplace_fixture()
    decision = boosts.pick_dry(offers, recent_ids=[])
    assert decision["picked_id"] is not None
    picked = next(o for o in offers if o["id"] == decision["picked_id"])
    assert "crypto" not in picked["name"].lower()


def test_boost_picker_avoids_recently_used(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    offers = boosts.fetch_marketplace_fixture()
    # Recent_ids excludes the would-be top pick
    top = boosts.pick_dry(offers, recent_ids=[]).get("picked_id")
    decision = boosts.pick_dry(offers, recent_ids=[top])
    assert decision["picked_id"] != top


def test_boost_rotate_writes_history(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    out = boosts.rotate(dry_run=True)
    assert out["picked_id"] is not None
    history_path = tmp_path / "boost_history.json"
    assert history_path.exists()
    history = json.loads(history_path.read_text())
    assert len(history) == 1


# --- SparkLoop -----------------------------------------------------------

def test_sparkloop_recommendation_keep_on_high_ratio(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(sparkloop, "estimate_ltv_per_sub", lambda: 9.00)
    report = sparkloop.evaluate(dry_run=True)
    # cost is 1.80 in dry-run; 9.00 / 1.80 = 5.0x → keep_on
    assert report.recommendation == "keep_on"


def test_sparkloop_recommendation_pause_low_ratio(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(sparkloop, "estimate_ltv_per_sub", lambda: 1.00)
    report = sparkloop.evaluate(dry_run=True)
    # 1.00 / 1.80 = 0.55x → pause
    assert report.recommendation == "pause"


def test_sparkloop_act_on_pause_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(sparkloop, "estimate_ltv_per_sub", lambda: 1.00)
    report = sparkloop.evaluate(dry_run=True)
    msg = sparkloop.act_on(report, dry_run=True)
    assert msg and "DRY RUN" in msg


# --- Sponsors ----------------------------------------------------------

def test_sponsors_dry_run_writes_file(tmp_path, monkeypatch):
    drafts_dir = tmp_path / "drafts"
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    out = sponsors.generate(dry_run=True, subscriber_count=2000)
    assert "prospects" in out
    assert len(out["prospects"]) >= 5
    files = list(drafts_dir.glob("sponsor-prospects-*.json"))
    assert len(files) == 1


def test_sponsors_excludes_vetoed_categories():
    """The seeded prospect list must not contain crypto / payday / cannabis / partisan."""
    seeds = sponsors._seed_prospects()
    for p in seeds:
        text = (p["company"] + p["category"] + p["fit_reason"]).lower()
        for veto in ("crypto", "payday", "cannabis", "partisan"):
            assert veto not in text, f"Seeded prospect contains '{veto}': {p}"


# --- Outreach ----------------------------------------------------------

def test_outreach_dry_run_drafts_one(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    sponsors.generate(dry_run=True, subscriber_count=1500)
    paths = outreach.draft_all(dry_run=True)
    assert len(paths) >= 5
    # Check first draft has required frontmatter + body
    body = paths[0].read_text(encoding="utf-8")
    assert "to_company:" in body
    assert "subject:" in body
    assert "status: needs_review" in body
    assert "happy to share our media kit" in body  # required closer


def test_outreach_never_promises_editorial_in_dry_template():
    prospect = {"company": "TestCo", "category": "test", "pitch_angle": "test", "cpm_low": 30, "cpm_high": 60, "warmth": "cold"}
    draft = outreach._draft_dry(prospect, 1000)
    body = draft["body_md"].lower()
    # These would be editorial-violation phrases — verify our template doesn't include them
    for forbidden in ("guaranteed coverage", "editorial mention", "we'll feature you", "endorsement"):
        assert forbidden not in body, f"outreach template promises editorial: contains '{forbidden}'"
