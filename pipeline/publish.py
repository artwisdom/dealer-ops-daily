"""beehiiv API client.

Renders an Issue to HTML, POSTs to /v2/publications/{id}/posts as a draft, then
schedules the send for 06:00 ET (10:00 UTC, 11:00 UTC during DST — beehiiv handles TZ).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timezone
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .models import Issue

log = logging.getLogger(__name__)

BEEHIIV_BASE = "https://api.beehiiv.com/v2"


def render_html(issue: Issue) -> str:
    """Render Issue to publishable HTML.

    Kept intentionally simple — beehiiv's editor accepts HTML and applies the
    publication's email template (header, footer, AI disclosure) on top.
    """
    parts: list[str] = []

    if issue.hero_image_url:
        parts.append(f'<p><img src="{issue.hero_image_url}" alt="{_escape(issue.issue_title)}" style="width:100%;max-width:100%;height:auto;" /></p>')

    parts.append(f"<h1>{_escape(issue.issue_title)}</h1>")
    parts.append(f"<p><em>{_escape(issue.cold_open)}</em></p>")
    parts.append("<hr/>")

    section_emoji = {"compliance": "⚖️", "fni": "💰", "used-car": "🚗", "store-ops": "🏬"}
    section_titles = {
        "compliance": "Compliance",
        "fni": "F&amp;I",
        "used-car": "Used-car desking",
        "store-ops": "Store ops",
    }
    for section in issue.sections:
        emoji = section_emoji.get(section.name, "•")
        title = section_titles.get(section.name, section.name.title())
        parts.append(f"<h2>{emoji} {title}</h2>")
        for story in section.stories:
            parts.append(f"<p><strong>{_escape(story.headline)}</strong></p>")
            parts.append(f"<p>{_escape(story.body)}</p>")
            parts.append(f"<p><strong>What to do today:</strong> {_escape(story.action_line)}</p>")
            src_links = " · ".join(f'<a href="{s.url}">{_escape(s.outlet)}</a>' for s in story.sources)
            parts.append(f"<p><em>Sources: {src_links}</em></p>")

    if issue.tool_of_day.product_id:
        tag = issue.tool_of_day.disclosure_tag
        parts.append(f"<h2>🛠️ Tool of the day <small>({tag})</small></h2>")
        parts.append(f"<p>{_escape(issue.tool_of_day.rationale)}</p>")

    parts.append("<hr/>")
    parts.append(f"<p><small>{_escape(issue.soft_footer)}</small></p>")

    return "\n".join(parts)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _scheduled_at(target_date: date, hour_et: int = 6) -> datetime:
    """6:00 AM Eastern Time → UTC. Naive — assumes EST/EDT auto-resolved by beehiiv."""
    # We pass UTC; beehiiv stores in UTC. 6 AM EDT = 10 UTC; 6 AM EST = 11 UTC.
    # Conservative: schedule for 11 UTC year-round (max 1hr early during DST is acceptable).
    return datetime.combine(target_date, time(11, 0), tzinfo=timezone.utc)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def _post_draft(html: str, issue: Issue) -> dict:
    url = f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}/posts"
    payload = {
        "title": issue.issue_title,
        "subtitle": issue.preheader,
        "body_content": html,
        "subject_line": issue.subject_a,  # beehiiv selects winner from subject_a/b/c at send if A/B is on
        "preview_text": issue.preheader,
        "status": "draft",
        "thumbnail_url": issue.hero_image_url,
        "subject_line_variants": [issue.subject_a, issue.subject_b, issue.subject_c],
    }
    headers = {
        "Authorization": f"Bearer {settings.beehiiv_api_key}",
        "Content-Type": "application/json",
    }
    r = httpx.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def _schedule(post_id: str, when: datetime) -> dict:
    url = f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}/posts/{post_id}"
    payload = {"status": "confirmed", "scheduled_at": when.isoformat()}
    headers = {
        "Authorization": f"Bearer {settings.beehiiv_api_key}",
        "Content-Type": "application/json",
    }
    r = httpx.patch(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def publish(issue: Issue, target_date: Optional[date] = None) -> Issue:
    """Post + schedule. Mutates issue with beehiiv_post_id and scheduled_send_at."""
    if issue.dry_run:
        log.info("DRY RUN: would publish issue '%s' (%d stories)", issue.issue_title, sum(len(s.stories) for s in issue.sections))
        issue.beehiiv_post_id = "dry-run-post-id"
        issue.scheduled_send_at = _scheduled_at(target_date or date.today())
        return issue

    if not (settings.beehiiv_api_key and settings.beehiiv_publication_id):
        raise RuntimeError("BEEHIIV_API_KEY and BEEHIIV_PUBLICATION_ID required for publish")

    html = render_html(issue)
    draft = _post_draft(html, issue)
    post_id = draft.get("data", {}).get("id") or draft.get("id")
    if not post_id:
        raise RuntimeError(f"beehiiv response missing post id: {draft}")

    when = _scheduled_at(target_date or date.today())
    _schedule(post_id, when)

    issue.beehiiv_post_id = post_id
    issue.scheduled_send_at = when
    log.info("Published post %s, scheduled for %s", post_id, when.isoformat())
    return issue


def save_audit(issue: Issue, target_date: date) -> None:
    """Write a permanent record of the issue to issues/YYYY-MM-DD.{md,json}."""
    settings.issue_output_dir.mkdir(parents=True, exist_ok=True)
    md_path = settings.issue_output_dir / f"{target_date:%Y-%m-%d}.md"
    json_path = settings.issue_output_dir / f"{target_date:%Y-%m-%d}.json"
    md_path.write_text(render_html(issue), encoding="utf-8")
    json_path.write_text(issue.model_dump_json(indent=2), encoding="utf-8")
    log.info("Wrote audit: %s and %s", md_path, json_path)
