"""Daily orchestrator. Chains ingest → rank → draft → image → affiliates → publish → audit.

Modes:
  default  — production cron run (fetches live RSS, calls Claude, posts to beehiiv)
  --dry-run — uses fixtures + local stubs everywhere; no external sends, no API costs

The dry-run path is fully self-contained: anyone can run it on a fresh checkout
with `python -m pipeline.run --dry-run` and see a complete issue rendered to
issues/<today>.md without API keys.

Self-test: returns exit code 0 when every step completes; non-zero on any error.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from . import affiliates, analytics, draft, image, ingest, publish
from .config import settings
from .models import Candidate, Issue

log = logging.getLogger(__name__)


# 90-day editorial calendar themes (research/00-summary.md §3)
WEEKLY_THEMES = [
    "CARS Rule readiness — operational checklists",
    "Used-car desking math — gross-per-retail-unit trends",
    "F&I product menu economics — VSC/GAP attach rates",
    "Compliance week — Safeguards Rule, Holder Rule, state-level",
    "DMS migration economics — switching cost",
    "Variable-ops hiring & comp — pay plan benchmarks",
    "Subprime & captive lender update",
    "EV retail playbook",
    "Buy-sell market — multiples and megadealer M&A",
    "AI in the store — practical desking/F&I/BDC use cases",
    "Fixed-ops profit — service/parts margin levers",
    "Quarterly state-of-the-store",
]


def active_theme(target_date: date) -> str:
    """Pick the week's theme by ISO week number mod 12."""
    week = target_date.isocalendar().week
    return WEEKLY_THEMES[(week - 1) % len(WEEKLY_THEMES)]


def _ingest_step(*, dry_run: bool) -> list[Candidate]:
    log.info("STEP 1/6: ingest sources")
    if dry_run:
        candidates = ingest.fetch_candidates_from_fixture()
    else:
        candidates = ingest.fetch_candidates()
    log.info("  %d candidates collected", len(candidates))
    if len(candidates) < 5:
        raise RuntimeError(f"Only {len(candidates)} candidates — likely a feed-fetch failure. Aborting.")
    return candidates


def _rank_step(candidates: list[Candidate], *, dry_run: bool) -> list[Candidate]:
    log.info("STEP 2/6: rank candidates")
    from . import rank as rank_module
    if dry_run or not settings.anthropic_api_key:
        ranked = rank_module.rank_dry(candidates)
        log.info("  used deterministic ranker")
    else:
        ranked = rank_module.rank_with_claude(candidates)
        log.info("  used Claude ranker")
    log.info("  top story: %s", ranked[0].headline if ranked else "(none)")
    return ranked


def _draft_step(ranked: list[Candidate], *, today: date, dry_run: bool) -> Issue:
    log.info("STEP 3/6: draft issue")
    if dry_run or not settings.anthropic_api_key:
        issue = draft.draft_dry(ranked, today=today)
        log.info("  used deterministic drafter")
    else:
        issue = draft.draft_with_claude(
            ranked,
            today=today,
            yesterday_analytics=analytics.yesterday_analytics(),
            rolling_baseline=analytics.rolling_baseline_30d(),
            affiliate_inventory=[a.model_dump(mode="json") for a in affiliates.load_inventory()],
            active_theme=active_theme(today),
            dry_run=dry_run,
        )
    log.info("  title: %s", issue.issue_title)
    return issue


def _image_step(issue: Issue, *, dry_run: bool) -> Issue:
    log.info("STEP 4/6: hero image")
    issue.hero_image_url = image.generate_hero_image(issue.hero_image_prompt, dry_run=dry_run)
    log.info("  image: %s", issue.hero_image_url)
    return issue


def _affiliate_step(issue: Issue) -> Issue:
    log.info("STEP 5/6: affiliate injection")
    issue = affiliates.inject(issue)
    log.info("  tool: %s", issue.tool_of_day.product_id or "(none)")
    return issue


def _publish_step(issue: Issue, *, today: date, dry_run: bool) -> Issue:
    log.info("STEP 6/6: publish + audit")
    issue.dry_run = dry_run
    issue = publish.publish(issue, target_date=today)
    publish.save_audit(issue, target_date=today)
    log.info("  post id: %s; scheduled: %s", issue.beehiiv_post_id, issue.scheduled_send_at)
    return issue


def run(*, today: date, dry_run: bool) -> Issue:
    candidates = _ingest_step(dry_run=dry_run)
    ranked = _rank_step(candidates, dry_run=dry_run)
    issue = _draft_step(ranked, today=today, dry_run=dry_run)
    issue = _image_step(issue, dry_run=dry_run)
    issue = _affiliate_step(issue)
    issue = _publish_step(issue, today=today, dry_run=dry_run)
    return issue


def selftest() -> int:
    """Exit 0 if dry-run completes cleanly, non-zero otherwise. Used by GitHub Actions."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        issue = run(today=date.today(), dry_run=True)
        log.info("✅ self-test passed: %d sections, %d total stories",
                 len(issue.sections), sum(len(s.stories) for s in issue.sections))
        return 0
    except Exception:
        log.exception("❌ self-test failed")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Dealer Ops Daily — daily pipeline")
    parser.add_argument("--dry-run", action="store_true", help="use fixtures + local stubs; no API calls or sends")
    parser.add_argument("--selftest", action="store_true", help="exit 0/non-0; equivalent to dry-run in CI")
    parser.add_argument("--date", help="ISO date to run as (default: today)")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    target = date.fromisoformat(args.date) if args.date else date.today()
    dry_run = args.dry_run or settings.dry_run

    if not dry_run:
        missing = settings.missing_required()
        if missing:
            log.error("Missing required env vars for live run: %s", missing)
            log.error("Use --dry-run to test without keys.")
            sys.exit(2)

    issue = run(today=target, dry_run=dry_run)
    print()
    print(json.dumps({
        "title": issue.issue_title,
        "subject_a": issue.subject_a,
        "story_count": sum(len(s.stories) for s in issue.sections),
        "post_id": issue.beehiiv_post_id,
        "dry_run": issue.dry_run,
    }, indent=2))


if __name__ == "__main__":
    main()
