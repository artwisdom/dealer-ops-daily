"""Affiliate inventory management.

Two backends:
  1. Supabase (when SUPABASE_URL + SUPABASE_SERVICE_KEY set) — production
  2. Local JSON (data/affiliates.json) — dev / single-affiliate seed

Selection: simple semantic-tag overlap with the day's section list. The Phase 4
ROI rotation loop will replace this with click-through-aware ranking.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from .config import settings
from .models import Affiliate, Issue, IssueSection, ToolOfDay

log = logging.getLogger(__name__)


def _load_local() -> list[Affiliate]:
    path = settings.data_dir / "affiliates.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Affiliate.model_validate(a) for a in raw if a.get("active", True)]


def _load_supabase() -> list[Affiliate]:
    """Fetch active affiliates from Supabase REST API."""
    if not (settings.supabase_url and settings.supabase_service_key):
        return []
    try:
        r = httpx.get(
            f"{settings.supabase_url}/rest/v1/affiliates",
            params={"active": "eq.true", "select": "*"},
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
            },
            timeout=10,
        )
        r.raise_for_status()
        return [Affiliate.model_validate(a) for a in r.json()]
    except Exception as exc:  # noqa: BLE001
        log.warning("Supabase affiliate fetch failed: %s; falling back to local", exc)
        return []


def load_inventory() -> list[Affiliate]:
    if settings.supabase_url and settings.supabase_service_key:
        from_supabase = _load_supabase()
        if from_supabase:
            return from_supabase
    return _load_local()


def _section_keywords(sections: list[IssueSection]) -> set[str]:
    """Distill section names into the same vocabulary used in affiliate semantic_tags."""
    name_map = {
        "compliance": {"compliance", "legal"},
        "fni": {"f&i", "finance", "subprime", "captive"},
        "used-car": {"used-car", "wholesale", "valuation", "manheim"},
        "store-ops": {"store-ops", "bdc", "dms", "crm", "variable-ops", "fixed-ops"},
    }
    out: set[str] = set()
    for s in sections:
        out.update(name_map.get(s.name, set()))
    return out


def pick_tool_of_day(issue: Issue) -> ToolOfDay:
    """Select the affiliate that best matches today's section mix."""
    inventory = load_inventory()
    if not inventory:
        return ToolOfDay(disclosure_tag="None", rationale="No affiliate inventory loaded")

    keywords = _section_keywords(issue.sections)
    scored: list[tuple[int, Affiliate]] = []
    for aff in inventory:
        overlap = len(keywords.intersection(set(t.lower() for t in aff.semantic_tags)))
        scored.append((overlap, aff))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]

    if best_score == 0:
        # No semantic match — skip rather than force a bad fit
        return ToolOfDay(disclosure_tag="None", rationale="No semantic match in inventory for today's sections")

    return ToolOfDay(
        product_id=best.product_id,
        rationale=f"{best.product_name}: {best.one_liner}",
        disclosure_tag=best.disclosure_type,
    )


def inject(issue: Issue) -> Issue:
    """Replace issue.tool_of_day with the picked affiliate. Returns the same Issue."""
    issue.tool_of_day = pick_tool_of_day(issue)
    issue.metadata.affiliate_used = issue.tool_of_day.product_id is not None
    return issue


def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    inv = load_inventory()
    if args.list:
        for a in inv:
            print(f"  [{a.product_id}] {a.product_name} — tags: {a.semantic_tags}")
    print(f"\n{len(inv)} active affiliates loaded.")


if __name__ == "__main__":
    main()
