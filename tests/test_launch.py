"""Phase 5 launch tests — preflight, monitor, postmortem."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipeline import launch, analytics
from pipeline.config import settings


# --- Preflight -------------------------------------------------------

def test_preflight_blocks_when_no_keys(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "beehiiv_api_key", "")
    monkeypatch.setattr(settings, "beehiiv_publication_id", "")
    report = launch.preflight(dry_run=True)
    assert report.has_blocker()
    env_check = next(c for c in report.checks if "env vars" in c.name)
    assert not env_check.passed


def test_preflight_passes_when_keys_set_and_self_test_works(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(settings, "beehiiv_api_key", "bh-test")
    monkeypatch.setattr(settings, "beehiiv_publication_id", "pub_test")
    report = launch.preflight(dry_run=True)
    # In dry-run mode the beehiiv API check is skipped
    skipped = [c for c in report.checks if "skipped" in c.name]
    assert skipped, "expected beehiiv API check to be skipped in dry-run"
    env_check = next(c for c in report.checks if "env vars" in c.name)
    assert env_check.passed
    # The pipeline self-test should pass
    selftest = next(c for c in report.checks if "selftest" in c.name)
    assert selftest.passed, selftest.detail


def test_preflight_renders_human_readable():
    report = launch.preflight(dry_run=True)
    rendered = report.render()
    assert "Preflight checks:" in rendered
    assert "✅" in rendered or "❌" in rendered or "⚠️" in rendered


# --- mark-launched + state -----------------------------------------

def test_mark_launched_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    msg1 = launch.mark_launched(date(2026, 5, 1))
    msg2 = launch.mark_launched(date(2026, 5, 2))  # different date — should be ignored
    assert "2026-05-01" in msg1
    assert "Already launched" in msg2
    assert "2026-05-01" in msg2  # idempotent — keeps original


# --- monitor -------------------------------------------------------

def test_monitor_skips_when_no_launch_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    monkeypatch.setattr(launch, "LAUNCH_LOG", tmp_path / "launch_log.json")
    out = launch.monitor(dry_run=True)
    assert out["status"] == "no_launch_yet"


def test_monitor_captures_today_after_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    monkeypatch.setattr(launch, "LAUNCH_LOG", tmp_path / "launch_log.json")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(analytics, "LOCAL_STATE", tmp_path / "analytics.json")

    # Seed launched yesterday
    launch.mark_launched(date.today() - timedelta(days=1))
    # Seed yesterday's analytics record
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    (tmp_path / "analytics.json").write_text(json.dumps([{
        "issue_date": yesterday,
        "beehiiv_post_id": "p1",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "recipients": 250,
        "opens": 90,
        "open_rate": 0.36,
        "clicks": 22,
        "click_rate": 0.088,
        "unsubscribes": 1,
        "bounces": 0,
        "sources_used": [],
    }], default=str))

    out = launch.monitor(dry_run=False)
    assert out["status"] == "captured"
    assert out["day"] == 1
    log_records = json.loads((tmp_path / "launch_log.json").read_text())
    assert len(log_records) == 1
    assert log_records[0]["recipients"] == 250


def test_monitor_idempotent_within_same_day(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    monkeypatch.setattr(launch, "LAUNCH_LOG", tmp_path / "launch_log.json")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(analytics, "LOCAL_STATE", tmp_path / "analytics.json")
    launch.mark_launched(date.today())
    (tmp_path / "analytics.json").write_text(json.dumps([{
        "issue_date": date.today().isoformat(),
        "beehiiv_post_id": "p1",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "recipients": 100, "opens": 30, "open_rate": 0.3,
        "clicks": 5, "click_rate": 0.05, "unsubscribes": 0, "bounces": 0, "sources_used": [],
    }], default=str))
    launch.monitor(dry_run=False)
    launch.monitor(dry_run=False)  # second call should NOT duplicate
    log_records = json.loads((tmp_path / "launch_log.json").read_text())
    assert len(log_records) == 1


def test_monitor_closes_after_14_days(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    monkeypatch.setattr(launch, "LAUNCH_LOG", tmp_path / "launch_log.json")
    launch.mark_launched(date.today() - timedelta(days=20))
    out = launch.monitor(dry_run=True)
    assert out["status"] == "monitoring_window_closed"


# --- postmortem ----------------------------------------------------

def test_postmortem_dry_handles_empty_log(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    monkeypatch.setattr(launch, "LAUNCH_LOG", tmp_path / "launch_log.json")
    launch.mark_launched(date.today() - timedelta(days=7))
    out = launch.postmortem(dry_run=True)
    assert out["status"] == "dry"
    assert "title" in out["result"]


def test_postmortem_dry_with_records_produces_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    monkeypatch.setattr(launch, "LAUNCH_LOG", tmp_path / "launch_log.json")
    launch.mark_launched(date.today() - timedelta(days=7))

    records = []
    for i in range(7):
        d = (date.today() - timedelta(days=7-i)).isoformat()
        records.append({
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "launch_day": i,
            "issue_date": d,
            "recipients": 200 + i*10,
            "open_rate": 0.34,
            "click_rate": 0.05,
            "unsubscribes": 1,
            "bounces": 0,
            "rolling_baseline_30d": {},
        })
    (tmp_path / "launch_log.json").write_text(json.dumps(records, default=str))

    out = launch.postmortem(dry_run=True)
    result = out["result"]
    assert result["verdict"] in ("success", "mixed", "needs intervention")
    assert "body_md" in result
    assert "Verdict" in result["body_md"]
    assert "0.34" in result["body_md"] or "34" in result["body_md"]


def test_postmortem_no_launch_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "LAUNCH_STATE", tmp_path / "launch_state.json")
    monkeypatch.setattr(launch, "LAUNCH_LOG", tmp_path / "launch_log.json")
    out = launch.postmortem(dry_run=True)
    assert out["status"] == "no_launch"
