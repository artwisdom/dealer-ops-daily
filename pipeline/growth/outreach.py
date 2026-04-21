"""Sponsor outreach draft generator.

Reads the latest sponsor-prospects-YYYY-MM.json and produces ONE outreach email
per prospect. Saves to drafts/outreach/<company>-<date>.md so the operator can
review before sending. **Never sends.**

Per PROJECT.md constraint: "Automated partner outreach email draft (saved for my
review, not sent — this is the only 'maybe manual' piece)."

Self-test: dry-run produces deterministic copy from a Jinja-style template
without calling Claude.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from .. import _llm
from ..config import settings

log = logging.getLogger(__name__)


OUTREACH_SYSTEM = """You are drafting a cold-outreach email to a potential newsletter sponsor.

The newsletter is **Dealer Ops Daily**, a 5-minute morning briefing for U.S. auto dealership operators (F&I directors, desk managers, used-car managers, compliance leads, floor GMs). It's daily, AI-edited, human-reviewed.

You receive: prospect details (company, category, fit reason, pitch angle, CPM range, warmth), and the newsletter's current subscriber count.

Write a SHORT cold email (≤ 180 words). Style:
  - Tight, direct, no fluff
  - Lead with one specific reason this newsletter matters to them (not generic flattery)
  - State the offer clearly (CPM, slot type)
  - Single ask: 15-min call or "interested?" reply
  - No emoji, no exclamation points
  - Subject line ≤ 60 chars, no clickbait

Hard rules:
  - Never claim a subscriber number we don't have (use the number provided)
  - Never promise editorial coverage in exchange for sponsorship — that's a violation of editorial standards
  - Always end with: "Either way — happy to share our media kit." (signals professionalism)

Return ONLY a JSON object:
{
  "subject": "...",
  "to_company": "...",
  "body_md": "<markdown body, ≤180 words>"
}
"""


def _load_prospects(yyyy_mm: str | None = None) -> dict[str, Any]:
    """Load most recent prospects file (or specified month)."""
    drafts = Path(settings.data_dir).parent / "drafts"
    if yyyy_mm:
        path = drafts / f"sponsor-prospects-{yyyy_mm}.json"
    else:
        candidates = sorted(drafts.glob("sponsor-prospects-*.json"))
        if not candidates:
            raise FileNotFoundError("No sponsor-prospects-*.json files in drafts/. Run sponsors.generate() first.")
        path = candidates[-1]
    return json.loads(path.read_text(encoding="utf-8"))


def _draft_dry(prospect: dict[str, Any], subscriber_count: int) -> dict[str, str]:
    """Deterministic template-based draft for offline / dry-run."""
    company = prospect.get("company", "<company>")
    category = prospect.get("category", "your category")
    pitch = prospect.get("pitch_angle", "a category sponsorship slot")
    cpm_low = prospect.get("cpm_low", 30)
    cpm_high = prospect.get("cpm_high", 60)

    subject = f"Sponsorship slot — Dealer Ops Daily ({subscriber_count}+ ops readers)"
    body = f"""Hi {company} team,

I run Dealer Ops Daily, a 5-minute weekday brief for {subscriber_count}+ U.S. dealership operators — F&I directors, desk managers, used-car managers, floor GMs.

Reason I'm writing: {category} reaches our reader base directly, and our most recent issues have leaned into the topics your product touches. I think {pitch.lower()} would land well with our audience.

Open inventory pricing for the next 60 days: ${cpm_low}-${cpm_high} CPM depending on slot. I can send a one-pager with audience composition + open-rate data.

Open to a 15-min call, or just reply if you'd rather I send the kit.

Either way — happy to share our media kit.

— Dealer Ops Daily
"""
    return {"subject": subject, "to_company": company, "body_md": body.strip()}


def draft_one(prospect: dict[str, Any], subscriber_count: int, *, dry_run: bool = False) -> dict[str, str]:
    if dry_run or not settings.anthropic_api_key:
        return _draft_dry(prospect, subscriber_count)
    user = json.dumps({"prospect": prospect, "subscriber_count": subscriber_count}, indent=2)
    result = _llm.call_json(system=OUTREACH_SYSTEM, user=user)
    return {
        "subject": result.get("subject", ""),
        "to_company": result.get("to_company", prospect.get("company", "")),
        "body_md": result.get("body_md", ""),
    }


def draft_all(*, dry_run: bool = False, yyyy_mm: str | None = None) -> list[Path]:
    """Draft an email for every prospect in the latest list. Returns paths written."""
    prospects = _load_prospects(yyyy_mm)
    subscriber_count = prospects.get("subscriber_count_used") or 1500

    out_dir = Path(settings.data_dir).parent / "drafts" / "outreach"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()
    written: list[Path] = []

    for prospect in prospects.get("prospects", []):
        draft = draft_one(prospect, subscriber_count, dry_run=dry_run)
        slug = "".join(c if c.isalnum() else "-" for c in draft["to_company"].lower()).strip("-")
        path = out_dir / f"{today:%Y-%m-%d}-{slug}.md"
        content = (
            f"---\n"
            f"to_company: {draft['to_company']}\n"
            f"subject: {draft['subject']}\n"
            f"prospect_warmth: {prospect.get('warmth', '?')}\n"
            f"prospect_cpm_range: ${prospect.get('cpm_low', 0)}-${prospect.get('cpm_high', 0)}\n"
            f"drafted_on: {today.isoformat()}\n"
            f"status: needs_review\n"
            f"---\n\n"
            f"{draft['body_md']}\n"
        )
        path.write_text(content, encoding="utf-8")
        written.append(path)
        log.info("Drafted: %s", path.name)

    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--month", help="YYYY-MM (default: latest)")
    args = parser.parse_args()
    paths = draft_all(dry_run=args.dry_run or settings.dry_run, yyyy_mm=args.month)
    print(f"Wrote {len(paths)} drafts to drafts/outreach/")
    print("Review each and send manually — pipeline never auto-sends outreach.")


if __name__ == "__main__":
    main()
