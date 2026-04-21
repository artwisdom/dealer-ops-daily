"""Sunday weekly meta-issue generator.

Produces ONE issue per week summarizing the week's biggest stories. Uses Opus 4.6
(more expensive but justified — this issue gets the highest engagement of the week).

Architecture: same shape as daily run.py — gather inputs, call Claude (or use
deterministic dry mode), emit Issue, publish, audit.

Self-test: dry-run produces a valid weekly meta-issue from the past week's audits.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from . import _llm, affiliates, analytics, image, publish
from .config import settings
from .models import (
    GuardrailSelfCheck,
    Issue,
    IssueMetadata,
    IssueSection,
    IssueSource,
    IssueStory,
    ToolOfDay,
)
from .run import WEEKLY_THEMES, active_theme

log = logging.getLogger(__name__)

WEEKLY_PROMPT_FILE = settings.system_prompt_file.parent / "weekly-meta-prompt-v1.md"


def _load_weekly_prompt() -> str:
    return WEEKLY_PROMPT_FILE.read_text(encoding="utf-8")


def _gather_week_input(today: date) -> dict[str, Any]:
    """Build the JSON payload the weekly model receives."""
    week_end = today
    week_start = today - timedelta(days=6)

    issues_published = []
    if settings.issue_output_dir.exists():
        for path in sorted(settings.issue_output_dir.glob("*.json")):
            issue_date_str = path.stem
            try:
                issue_date = date.fromisoformat(issue_date_str)
            except ValueError:
                continue
            if not (week_start <= issue_date <= week_end):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            issues_published.append({
                "issue_date": issue_date_str,
                "title": data.get("issue_title"),
                "cold_open": data.get("cold_open"),
                "story_count": data.get("metadata", {}).get("story_count"),
                "sections": data.get("sections", []),
                "tool_of_day": data.get("tool_of_day", {}).get("product_id"),
            })

    week_records = []
    if (settings.data_dir / "analytics.json").exists():
        try:
            all_records = json.loads((settings.data_dir / "analytics.json").read_text(encoding="utf-8"))
            for r in all_records:
                d = r.get("issue_date", "")
                if week_start.isoformat() <= d <= week_end.isoformat():
                    week_records.append(r)
        except json.JSONDecodeError:
            pass

    week_totals = {
        "issues_sent": len(week_records),
        "total_opens": sum(r.get("opens", 0) for r in week_records),
        "total_clicks": sum(r.get("clicks", 0) for r in week_records),
        "total_unsubscribes": sum(r.get("unsubscribes", 0) for r in week_records),
        "avg_open_rate": (
            sum(r.get("open_rate", 0) for r in week_records) / len(week_records)
            if week_records else 0
        ),
        "avg_click_rate": (
            sum(r.get("click_rate", 0) for r in week_records) / len(week_records)
            if week_records else 0
        ),
    }

    next_theme_idx = today.isocalendar().week % len(WEEKLY_THEMES)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "issues_published": issues_published,
        "week_totals": week_totals,
        "rolling_baseline_30d": analytics.rolling_baseline_30d(),
        "active_theme": active_theme(today),
        "upcoming_theme": WEEKLY_THEMES[next_theme_idx],
        "affiliate_inventory": [a.model_dump(mode="json") for a in affiliates.load_inventory()],
    }


def generate_with_claude(today: date, *, dry_run: bool = False) -> Issue:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY required for weekly meta-issue (no dry path here)")

    payload = _gather_week_input(today)
    raw = _llm.call_json(
        system=_load_weekly_prompt(),
        user=f"This week's input:\n\n```json\n{json.dumps(payload, indent=2, default=str)}\n```",
        model=settings.weekly_model,
        max_tokens=8192,
    )
    if raw.get("error") == "guardrail_violation":
        raise RuntimeError(f"Weekly meta refused: {raw.get('violations')} — {raw.get('suggested_fix')}")
    issue = Issue.model_validate(raw)
    issue.dry_run = dry_run
    return issue


def generate_dry(today: date) -> Issue:
    """Deterministic dry-run weekly issue — pulls top stories from this week's audits.

    Doesn't call Claude. Produces a structurally valid weekly meta-issue with the
    week's top stories arranged into the meta format.
    """
    payload = _gather_week_input(today)
    issues = payload["issues_published"]

    # Top 3 stories: take the first story from each of the top 3 daily issues by date
    top_stories: list[IssueStory] = []
    for daily in issues[:3]:
        sections = daily.get("sections", [])
        if not sections:
            continue
        first_section = sections[0]
        if first_section.get("stories"):
            s = first_section["stories"][0]
            top_stories.append(IssueStory(
                headline=s.get("headline", "(missing)"),
                body=s.get("body", "")[:300],
                action_line=f"Why it matters: This was the dominant story on {daily.get('issue_date')} and continues to develop.",
                sources=[IssueSource(outlet=src["outlet"], url=src["url"]) for src in s.get("sources", [])][:2] or [IssueSource(outlet="(audit)", url="#")],
            ))

    if not top_stories:
        # Fallback: synthesize one placeholder story so the issue is still structurally valid
        top_stories = [IssueStory(
            headline="Week in review",
            body="The pipeline ran but no daily issues are in the audit window.",
            action_line="Confirm the daily-issue workflow is firing this week.",
            sources=[IssueSource(outlet="(internal)", url="#")],
        )]

    week_totals = payload["week_totals"]
    data_recap = IssueStory(
        headline="What the week's data showed",
        body=(
            f"This week we sent {week_totals['issues_sent']} issues with an average "
            f"open rate of {week_totals['avg_open_rate']:.1%} and click rate of "
            f"{week_totals['avg_click_rate']:.1%}. Total clicks: {week_totals['total_clicks']}; "
            f"unsubscribes: {week_totals['total_unsubscribes']}."
        ),
        action_line="Compare to the 30-day baseline below; flag any open-rate drop >15% to Loop 6.",
        sources=[IssueSource(outlet="Internal analytics", url="#")],
    )

    watch_next = IssueStory(
        headline="What to watch next week",
        body=(
            f"Next week's editorial theme: **{payload['upcoming_theme']}**. "
            f"Set source priorities accordingly: regulatory feeds for compliance weeks, "
            f"Manheim/Cox feeds for used-car weeks, vendor newsrooms for tech weeks."
        ),
        action_line="Check the source weights in sources.yaml against the theme.",
        sources=[IssueSource(outlet="Editorial calendar", url="#")],
    )

    inventory = affiliates.load_inventory()
    if inventory:
        tool = ToolOfDay(
            product_id=inventory[0].product_id,
            rationale=f"{inventory[0].product_name}: {inventory[0].one_liner}",
            disclosure_tag=inventory[0].disclosure_type,
        )
    else:
        tool = ToolOfDay(disclosure_tag="None")

    week_start = date.fromisoformat(payload["week_start"])
    return Issue(
        subject_a=f"Sunday digest: this week in dealer ops",
        subject_b=f"5 days, 3 stories that mattered",
        subject_c=f"What to watch next week",
        preheader=f"The week's top stories + what's next.",
        issue_title=f"This week in Dealer Ops Daily — week of {week_start.strftime('%B')} {week_start.day}",
        cold_open=(
            f"Five issues this week, {week_totals.get('total_clicks', 0)} clicks. "
            f"Here's what mattered most and what's on the radar for next week."
        ),
        sections=[
            IssueSection(name="top-stories", stories=top_stories),
            IssueSection(name="data-recap", stories=[data_recap]),
            IssueSection(name="watch-next-week", stories=[watch_next]),
        ],
        tool_of_day=tool,
        soft_footer="Hit reply if a story you wanted to see this week didn't land.",
        hero_image_prompt=(
            "Wide editorial illustration, Sunday morning light through window onto a coffee mug "
            "and open notebook with auto industry charts, no text, no people, slate-blue and amber palette."
        ),
        metadata=IssueMetadata(
            story_count=len(top_stories) + 2,  # 3 top + 1 data + 1 watch
            word_count_estimate=850,
            sources_used=[],
            affiliate_used=tool.product_id is not None,
            guardrail_self_check=GuardrailSelfCheck(
                two_source_min=False,  # dry-run uses 1 source per story by design
                no_financial_advice=True,
                no_political_take=True,
                quotes_under_25_words=True,
                all_numbers_sourced=True,
            ),
        ),
        dry_run=True,
    )


def run(today: Optional[date] = None, *, dry_run: bool = False) -> Issue:
    today = today or date.today()
    log.info("Weekly meta-issue: gathering week ending %s", today)

    if dry_run or not settings.anthropic_api_key:
        issue = generate_dry(today)
    else:
        issue = generate_with_claude(today, dry_run=dry_run)

    log.info("Generated: %s", issue.issue_title)

    issue.hero_image_url = image.generate_hero_image(issue.hero_image_prompt, dry_run=dry_run)
    log.info("Hero image: %s", issue.hero_image_url)

    issue = publish.publish(issue, target_date=today)
    publish.save_audit(issue, target_date=today)
    log.info("Published: %s", issue.beehiiv_post_id)

    return issue


def selftest() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        issue = run(dry_run=True)
        log.info(
            "✅ weekly meta-issue self-test passed: %d sections, %d total stories",
            len(issue.sections),
            sum(len(s.stories) for s in issue.sections),
        )
        return 0
    except Exception:
        log.exception("❌ weekly meta-issue self-test failed")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--date", help="ISO date for the week ending date (default: today)")
    args = parser.parse_args()

    if args.selftest:
        import sys
        sys.exit(selftest())

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    today = date.fromisoformat(args.date) if args.date else date.today()
    run(today, dry_run=args.dry_run or settings.dry_run)


if __name__ == "__main__":
    main()
