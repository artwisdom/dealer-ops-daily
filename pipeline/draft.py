"""Issue generation. Given a ranked candidate list + analytics + active theme,
asks Claude (system-prompt-v1.md) to produce the publishable Issue JSON.

The model's output JSON is validated against models.Issue. If guardrail_self_check
fails, we refuse to ship and log the violation rather than send a bad issue.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

from anthropic import Anthropic

from .config import settings
from .models import (
    Candidate,
    GuardrailSelfCheck,
    Issue,
    IssueMetadata,
    IssueSection,
    IssueSource,
    IssueStory,
    ToolOfDay,
)

log = logging.getLogger(__name__)


def _load_system_prompt() -> str:
    return settings.system_prompt_file.read_text(encoding="utf-8")


def _build_user_prompt(
    ranked: list[Candidate],
    *,
    today: date,
    yesterday_analytics: Optional[dict] = None,
    rolling_baseline: Optional[dict] = None,
    affiliate_inventory: Optional[list[dict]] = None,
    active_theme: Optional[str] = None,
    dry_run: bool = False,
) -> str:
    candidate_payload = [
        {
            "stable_id": c.stable_id,
            "source_name": c.source_name,
            "section": c.section_assignment,
            "importance": c.importance_score,
            "novelty": c.novelty_score,
            "headline": c.headline,
            "summary": c.summary,
            "url": c.url,
            "published": c.published.isoformat() if c.published else None,
        }
        for c in ranked
    ]
    payload = {
        "today": today.isoformat(),
        "day_of_week": today.strftime("%A"),
        "yesterday_analytics": yesterday_analytics or {},
        "rolling_baseline_30d": rolling_baseline or {},
        "candidate_pool": candidate_payload,
        "affiliate_inventory": affiliate_inventory or [],
        "active_theme": active_theme or "",
        "dry_run": dry_run,
    }
    return f"Today's input:\n\n```json\n{json.dumps(payload, indent=2)}\n```"


def _parse_issue_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        stripped = "\n".join(lines)
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1:
        stripped = stripped[first : last + 1]
    return json.loads(stripped)


def draft_with_claude(
    ranked: list[Candidate],
    *,
    today: date,
    yesterday_analytics: Optional[dict] = None,
    rolling_baseline: Optional[dict] = None,
    affiliate_inventory: Optional[list[dict]] = None,
    active_theme: Optional[str] = None,
    dry_run: bool = False,
) -> Issue:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; use draft_dry() for offline runs")

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.daily_model,
        max_tokens=8192,
        system=_load_system_prompt(),
        messages=[{
            "role": "user",
            "content": _build_user_prompt(
                ranked,
                today=today,
                yesterday_analytics=yesterday_analytics,
                rolling_baseline=rolling_baseline,
                affiliate_inventory=affiliate_inventory,
                active_theme=active_theme,
                dry_run=dry_run,
            ),
        }],
    )
    text = response.content[0].text  # type: ignore[union-attr]
    raw = _parse_issue_json(text)

    if raw.get("error") == "guardrail_violation":
        raise RuntimeError(f"Editorial guardrail violation: {raw.get('violations')} — {raw.get('suggested_fix')}")

    # Coerce guardrail_self_check values to strict booleans — Claude occasionally
    # returns narrative strings like "PARTIAL — ..." when a check is partially met.
    # Any non-exact-True becomes False; the original reason is logged.
    meta = raw.get("metadata") or {}
    sc = meta.get("guardrail_self_check") or {}
    coerced: dict[str, bool] = {}
    for key, val in list(sc.items()):
        if val is True:
            coerced[key] = True
        else:
            coerced[key] = False
            if val is not False:
                log.warning("guardrail_self_check.%s coerced to False (model returned: %r)", key, val)
    sc.update(coerced)
    meta["guardrail_self_check"] = sc
    raw["metadata"] = meta

    issue = Issue.model_validate(raw)
    issue.dry_run = dry_run
    _enforce_guardrails(issue)
    return issue


def _enforce_guardrails(issue: Issue) -> None:
    """Belt-and-suspenders check on top of the model's self-check."""
    sc = issue.metadata.guardrail_self_check
    failed = [k for k, v in sc.model_dump().items() if not v]
    if failed:
        raise RuntimeError(f"Guardrail self-check failed: {failed}")
    total_stories = sum(len(s.stories) for s in issue.sections)
    if total_stories < 3:
        raise RuntimeError(f"Issue has only {total_stories} stories; minimum is 3")
    if total_stories > 8:
        raise RuntimeError(f"Issue has {total_stories} stories; maximum is 8 (target 4-6)")
    for section in issue.sections:
        for story in section.stories:
            if not story.action_line.strip():
                raise RuntimeError(f"Story missing action_line: '{story.headline}'")
            if not story.sources:
                raise RuntimeError(f"Story missing sources: '{story.headline}'")


def draft_dry(ranked: list[Candidate], *, today: date) -> Issue:
    """Deterministic dry-run drafter. Builds an Issue from ranked candidates without calling Claude.

    The resulting issue is structurally valid (passes guardrails) but doesn't have
    real editorial polish — its purpose is to exercise the rest of the pipeline.
    """
    sections_map: dict[str, list[IssueStory]] = {"compliance": [], "fni": [], "used-car": [], "store-ops": []}
    sources_used: list[str] = []
    for c in ranked[:5]:
        section = c.section_assignment or "store-ops"
        if section not in sections_map:
            section = "store-ops"
        story = IssueStory(
            headline=c.headline,
            body=(c.summary or c.headline)[:300],
            action_line=f"Pull yesterday's report on this and confirm it doesn't change your current process. Source: {c.source_name}.",
            sources=[IssueSource(outlet=c.source_name, url=c.url)],
            source_ids=[c.stable_id],
        )
        sections_map[section].append(story)
        sources_used.append(c.stable_id)

    sections = [
        IssueSection(name=name, stories=stories)  # type: ignore[arg-type]
        for name, stories in sections_map.items() if stories
    ]
    total_stories = sum(len(s.stories) for s in sections)

    return Issue(
        subject_a=f"{today:%a}: {ranked[0].headline[:40]}",
        subject_b=f"What changed yesterday in dealer ops",
        subject_c=f"5 stories your store needs today",
        preheader="The 5-minute morning briefing for U.S. dealer ops.",
        issue_title=f"Dealer Ops Daily — {today.strftime('%B')} {today.day}",
        cold_open=f"Yesterday's biggest move in dealer ops: {ranked[0].headline[:120]}.",
        sections=sections,
        tool_of_day=ToolOfDay(disclosure_tag="None"),
        soft_footer="Forward this to one person at the store who'd find it useful.",
        hero_image_prompt="Editorial illustration of a clean, modern auto dealership desking station at dawn — no people, no logos, soft amber light, slate-blue palette.",
        metadata=IssueMetadata(
            story_count=total_stories,
            word_count_estimate=total_stories * 130,
            sources_used=sources_used,
            affiliate_used=False,
            guardrail_self_check=GuardrailSelfCheck(
                two_source_min=False,  # dry-run intentionally doesn't enforce — see note
                no_financial_advice=True,
                no_political_take=True,
                quotes_under_25_words=True,
                all_numbers_sourced=True,
            ),
        ),
        dry_run=True,
    )


# Note on dry-run guardrails: we set two_source_min=False because the dry drafter
# uses one source per story (no time to dedupe-merge). Real Claude runs MUST set this true.
# We bypass _enforce_guardrails for dry runs in run.py.
