"""Phase 5 — launch script.

Three subcommands:

  preflight  — run before first live send. Verifies every component, returns
               non-zero if any blocker is found. Doesn't send anything.

  monitor    — runs daily for 7 days after launch. Captures key metrics into
               data/launch_log.json. Idempotent: re-runs on same day overwrite.

  postmortem — at day 7+, generates a launch post-mortem GitHub Issue using
               Claude (or a deterministic template if no key). Highlights what
               worked, what didn't, what auto-adjusted.

Self-test: each subcommand has a --dry-run path that exercises logic without
external side effects.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from . import _llm, analytics, github_alerts
from .config import settings
from .publish import BEEHIIV_BASE
from .run import run as daily_run

log = logging.getLogger(__name__)


LAUNCH_LOG = settings.data_dir / "launch_log.json"
LAUNCH_STATE = settings.data_dir / "launch_state.json"


# ===== Preflight =====================================================

@dataclass
class PreflightCheck:
    name: str
    passed: bool
    blocker: bool
    detail: str


@dataclass
class PreflightReport:
    checks: list[PreflightCheck] = field(default_factory=list)

    def add(self, name: str, passed: bool, *, blocker: bool, detail: str = "") -> None:
        self.checks.append(PreflightCheck(name, passed, blocker, detail))

    def has_blocker(self) -> bool:
        return any(c.blocker and not c.passed for c in self.checks)

    def render(self) -> str:
        lines = ["Preflight checks:\n"]
        for c in self.checks:
            mark = "✅" if c.passed else ("❌" if c.blocker else "⚠️")
            tag = "" if c.passed else (" — BLOCKER" if c.blocker else " — warning")
            lines.append(f"  {mark} {c.name}{tag}")
            if c.detail:
                lines.append(f"      {c.detail}")
        return "\n".join(lines)


def preflight(*, dry_run: bool = False) -> PreflightReport:
    report = PreflightReport()

    # 1. Required env vars
    missing = settings.missing_required()
    report.add(
        "Required env vars set (ANTHROPIC, BEEHIIV)",
        passed=not missing,
        blocker=True,
        detail=f"Missing: {missing}" if missing else "All present",
    )

    # 2. sources.yaml loads
    try:
        from .ingest import load_sources
        sources = load_sources()
        report.add(
            "sources.yaml loads + has ≥30 sources",
            passed=len(sources.sources) >= 30,
            blocker=True,
            detail=f"{len(sources.sources)} sources",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("sources.yaml loads", passed=False, blocker=True, detail=str(exc))

    # 3. System prompt readable
    try:
        text = settings.system_prompt_file.read_text(encoding="utf-8")
        ok = "Dealer Ops Daily" in text and "guardrail" in text.lower()
        report.add(
            "Daily system prompt present + sane",
            passed=ok,
            blocker=True,
            detail=str(settings.system_prompt_file),
        )
    except Exception as exc:  # noqa: BLE001
        report.add("Daily system prompt readable", passed=False, blocker=True, detail=str(exc))

    # 4. Affiliate inventory
    try:
        from . import affiliates as aff_mod
        inv = aff_mod.load_inventory()
        report.add(
            "Affiliate inventory loaded",
            passed=len(inv) >= 1,
            blocker=False,  # warning only — issue can ship with no affiliate
            detail=f"{len(inv)} active",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("Affiliate inventory loads", passed=False, blocker=False, detail=str(exc))

    # 5. beehiiv settings (live API, optional)
    if settings.beehiiv_api_key and settings.beehiiv_publication_id and not dry_run:
        try:
            r = httpx.get(
                f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}",
                headers={"Authorization": f"Bearer {settings.beehiiv_api_key}"},
                timeout=15,
            )
            r.raise_for_status()
            pub = r.json().get("data", {})
            report.add(
                "beehiiv API reachable + publication ID valid",
                passed=True,
                blocker=True,
                detail=f"Pub: {pub.get('name', '?')}",
            )
            # Sub-checks against publication state
            stats = pub.get("stats") or {}
            report.add(
                "beehiiv: ≥1 active subscriber (sender themselves count)",
                passed=int(stats.get("active_subscriptions") or stats.get("active_subscribers") or 0) >= 1,
                blocker=False,
                detail=f"Active: {stats.get('active_subscriptions') or stats.get('active_subscribers') or 0}",
            )
        except Exception as exc:  # noqa: BLE001
            report.add(
                "beehiiv API reachable",
                passed=False,
                blocker=True,
                detail=str(exc),
            )
    else:
        report.add(
            "beehiiv API check (skipped — no keys or dry-run)",
            passed=True,
            blocker=False,
            detail="Will run on live preflight",
        )

    # 6. Self-tests pass
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pipeline.run", "--selftest"],
            capture_output=True, text=True, timeout=120,
        )
        report.add(
            "pipeline.run --selftest passes",
            passed=result.returncode == 0,
            blocker=True,
            detail=result.stderr[-300:] if result.returncode else "ok",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("Self-test runs", passed=False, blocker=True, detail=str(exc))

    # 7. Output dir writable
    try:
        settings.issue_output_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.issue_output_dir / ".probe"
        probe.write_text("ok")
        probe.unlink()
        report.add("Issue output dir writable", passed=True, blocker=True, detail=str(settings.issue_output_dir))
    except Exception as exc:  # noqa: BLE001
        report.add("Issue output dir writable", passed=False, blocker=True, detail=str(exc))

    return report


# ===== Monitor =====================================================

def _load_launch_state() -> dict:
    if not LAUNCH_STATE.exists():
        return {}
    return json.loads(LAUNCH_STATE.read_text(encoding="utf-8"))


def _save_launch_state(state: dict) -> None:
    LAUNCH_STATE.parent.mkdir(parents=True, exist_ok=True)
    LAUNCH_STATE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _load_launch_log() -> list[dict]:
    if not LAUNCH_LOG.exists():
        return []
    return json.loads(LAUNCH_LOG.read_text(encoding="utf-8"))


def _save_launch_log(records: list[dict]) -> None:
    LAUNCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    LAUNCH_LOG.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


def mark_launched(launch_date: Optional[date] = None) -> str:
    """Record the official launch date. Idempotent — won't overwrite once set."""
    state = _load_launch_state()
    if state.get("launch_date"):
        return f"Already launched on {state['launch_date']}"
    state["launch_date"] = (launch_date or date.today()).isoformat()
    _save_launch_state(state)
    return f"Marked launch date: {state['launch_date']}"


def monitor(*, dry_run: bool = False) -> dict:
    """Capture today's metrics into the launch log. Run daily after analytics has refreshed."""
    state = _load_launch_state()
    launch = state.get("launch_date")
    if not launch:
        return {"status": "no_launch_yet", "msg": "Run `python -m pipeline.launch mark-launched` first."}

    launch_date = date.fromisoformat(launch)
    days_in = (date.today() - launch_date).days
    if days_in < 0:
        return {"status": "future_launch", "msg": f"Launch date is in the future ({launch_date})"}
    if days_in > 14:
        return {"status": "monitoring_window_closed", "msg": f"Day {days_in} — past 7-day monitor window"}

    yesterday = analytics.yesterday_analytics() or {}
    baseline = analytics.rolling_baseline_30d()

    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "launch_day": days_in,
        "issue_date": yesterday.get("issue_date"),
        "recipients": yesterday.get("recipients"),
        "open_rate": yesterday.get("open_rate"),
        "click_rate": yesterday.get("click_rate"),
        "unsubscribes": yesterday.get("unsubscribes"),
        "bounces": yesterday.get("bounces"),
        "rolling_baseline_30d": baseline,
    }

    log_records = _load_launch_log()
    # Idempotent: replace any existing record for the same launch_day
    log_records = [r for r in log_records if r.get("launch_day") != days_in]
    log_records.append(record)
    log_records.sort(key=lambda r: r.get("launch_day", 0))

    if not dry_run:
        _save_launch_log(log_records)

    log.info("Day %d captured: open=%s click=%s", days_in, record["open_rate"], record["click_rate"])
    return {"status": "captured", "day": days_in, "record": record}


# ===== Postmortem =====================================================

POSTMORTEM_SYSTEM = """You are writing the launch post-mortem for Dealer Ops Daily, a daily AI-edited newsletter for U.S. auto dealership operators.

You receive: 7 days of post-launch metrics, the issues sent, and any GitHub Issues filed by the self-improvement loops during the window.

Write a frank, operator-style post-mortem. NOT corporate. Highlight:

  - What worked (1-3 bullets, citing specific data)
  - What didn't (1-3 bullets, citing specific data)
  - What Claude/the pipeline auto-adjusted during the week (loops 1-6 outputs)
  - Specific recommendations for week 2 (concrete: change X, try Y)
  - Top metric to watch for week 2

Hard rules:
  - No spin. If open rate dropped, say so.
  - Always cite numbers from the data given (don't invent).
  - End with a 1-sentence "verdict" — was the launch a success?

Return ONLY a JSON object:
{
  "title": "Launch post-mortem — week of YYYY-MM-DD",
  "verdict": "success | mixed | needs intervention",
  "what_worked": ["..."],
  "what_didnt": ["..."],
  "auto_adjustments": ["..."],
  "week_2_recommendations": ["..."],
  "top_metric_to_watch": "...",
  "body_md": "<full markdown body for the GitHub Issue, 400-700 words>"
}
"""


def _postmortem_dry(records: list[dict]) -> dict:
    """Deterministic dry post-mortem when there's no API key."""
    if not records:
        return {
            "title": "Launch post-mortem — no data",
            "verdict": "needs intervention",
            "what_worked": ["Pipeline scaffolding"],
            "what_didnt": ["No daily metrics captured"],
            "auto_adjustments": [],
            "week_2_recommendations": ["Confirm daily-issue workflow is firing"],
            "top_metric_to_watch": "any open rate at all",
            "body_md": "No launch monitor records were captured. Re-run `pipeline.launch monitor` daily.",
        }
    avg_open = sum(r.get("open_rate") or 0 for r in records) / len(records)
    avg_click = sum(r.get("click_rate") or 0 for r in records) / len(records)
    avg_subs = sum(r.get("recipients") or 0 for r in records) / len(records)
    verdict = "success" if avg_open >= 0.30 else ("mixed" if avg_open >= 0.20 else "needs intervention")
    body = (
        f"# Launch post-mortem — {records[0].get('issue_date', '?')} → {records[-1].get('issue_date', '?')}\n\n"
        f"**Verdict:** {verdict}\n\n"
        f"## What worked\n"
        f"- Pipeline ran every day for {len(records)} days without manual intervention.\n"
        f"- Average open rate: {avg_open:.1%}.\n\n"
        f"## What didn't\n"
        f"- Recipient count averaged {avg_subs:.0f} — small base limits statistical confidence.\n"
        f"- Click rate averaged {avg_click:.1%}.\n\n"
        f"## Pipeline auto-adjustments\n"
        f"- (Auto-detected from Loop logs — extend this dry template once Loops 1-6 have data)\n\n"
        f"## Week 2 recommendations\n"
        f"- If open rate dropped >15% week-over-week, Loop 6 will have already filed an alert.\n"
        f"- Pull subject-line analysis from Loop 2's weekly run and apply manually if confidence ≥ medium.\n\n"
        f"## Top metric to watch\n"
        f"30-day open rate baseline. Below 20% blocks Ad Network qualification.\n"
    )
    return {
        "title": f"Launch post-mortem — week ending {records[-1].get('issue_date', '?')}",
        "verdict": verdict,
        "what_worked": [f"Pipeline ran {len(records)}/7 days", f"Average open rate {avg_open:.1%}"],
        "what_didnt": [f"Average click rate only {avg_click:.1%}"] if avg_click < 0.04 else [],
        "auto_adjustments": [],
        "week_2_recommendations": ["Apply Loop 2 subject-line learnings", "Watch 30d open-rate baseline"],
        "top_metric_to_watch": "30-day open rate baseline",
        "body_md": body,
    }


def postmortem(*, dry_run: bool = False) -> dict:
    """Generate + file the launch post-mortem GitHub Issue."""
    state = _load_launch_state()
    launch = state.get("launch_date")
    if not launch:
        return {"status": "no_launch", "msg": "Run mark-launched first."}

    records = _load_launch_log()
    if not records:
        log.warning("No launch_log records yet")

    if dry_run or not settings.anthropic_api_key:
        result = _postmortem_dry(records)
    else:
        user = json.dumps({
            "launch_date": launch,
            "records": records,
        }, indent=2, default=str)
        try:
            result = _llm.call_json(system=POSTMORTEM_SYSTEM, user=user, model=settings.weekly_model)
        except Exception as exc:  # noqa: BLE001
            log.warning("Claude post-mortem failed (%s); falling back to deterministic", exc)
            result = _postmortem_dry(records)

    if dry_run:
        log.info("DRY RUN — would file post-mortem:\n%s", result.get("title"))
        return {"status": "dry", "result": result}

    url = github_alerts.open_issue(
        title=result.get("title", "Launch post-mortem"),
        body=result.get("body_md", ""),
        labels=["launch", "post-mortem"],
    )

    if not state.get("postmortem_filed_at"):
        state["postmortem_filed_at"] = datetime.now(timezone.utc).isoformat()
        state["postmortem_url"] = url
        _save_launch_state(state)

    return {"status": "filed", "url": url, "result": result}


# ===== CLI =====================================================

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pre = sub.add_parser("preflight", help="Pre-launch checks")
    p_pre.add_argument("--dry-run", action="store_true")

    p_mark = sub.add_parser("mark-launched", help="Record launch date")
    p_mark.add_argument("--date", help="ISO date (default: today)")

    p_mon = sub.add_parser("monitor", help="Daily metric capture (run via cron)")
    p_mon.add_argument("--dry-run", action="store_true")

    p_post = sub.add_parser("postmortem", help="Generate the week-1 post-mortem")
    p_post.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.cmd == "preflight":
        report = preflight(dry_run=args.dry_run)
        print(report.render())
        sys.exit(1 if report.has_blocker() else 0)

    if args.cmd == "mark-launched":
        d = date.fromisoformat(args.date) if args.date else None
        print(mark_launched(d))
        return

    if args.cmd == "monitor":
        out = monitor(dry_run=args.dry_run)
        print(json.dumps(out, indent=2, default=str))
        return

    if args.cmd == "postmortem":
        out = postmortem(dry_run=args.dry_run)
        print(json.dumps({k: v for k, v in out.items() if k != "result"}, indent=2, default=str))
        if "result" in out:
            print("\n--- Body preview ---\n")
            print(out["result"].get("body_md", "")[:1500])


if __name__ == "__main__":
    main()
