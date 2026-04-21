"""Dedupe-aware ranker. Claude scores each candidate on importance + novelty,
assigns a section, and returns the top N for the issue.

In dry-run mode this returns deterministic ranks based on source weight, so the
rest of the pipeline can be exercised without consuming Anthropic credits.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from .config import settings
from .models import Candidate

log = logging.getLogger(__name__)


_RANKER_SYSTEM = """You are a ranking agent for Dealer Ops Daily, a 5-minute morning briefing for U.S. auto dealership operators (F&I directors, desk managers, used-car managers, compliance leads, floor GMs).

You receive a JSON array of candidate stories from yesterday's news cycle. Score each story on:

- importance (0.0-10.0): how operationally relevant to a working dealer's day
- novelty (0.0-10.0): how new/non-obvious the information is (a CFPB rule change is novel; a generic OEM marketing release is not)
- section: one of "compliance", "fni", "used-car", "store-ops" (or "skip" if not relevant)

Then return the TOP candidates the editor should consider, ranked. Aim to return 8-12 stories total, balanced across sections (1-3 per section).

Hard rules:
- Never return more than 12 stories
- Never return a story with importance < 4.0
- Skip duplicates (multiple coverage of the same event) — keep the best-sourced one
- Never return paid content / native ads disguised as news

Return ONLY a JSON object with this exact shape:
{
  "ranked": [
    {"stable_id": "...", "importance": 8.5, "novelty": 7.0, "section": "compliance", "rank": 1, "rationale": "<1 sentence>"},
    ...
  ]
}
"""


def _build_user_prompt(candidates: list[Candidate]) -> str:
    payload = [
        {
            "stable_id": c.stable_id,
            "source_name": c.source_name,
            "source_weight": c.source_weight,
            "headline": c.headline,
            "summary": c.summary,
            "url": c.url,
            "published": c.published.isoformat() if c.published else None,
        }
        for c in candidates
    ]
    return f"Today's candidate pool ({len(candidates)} stories):\n\n```json\n{json.dumps(payload, indent=2)}\n```"


def _parse_response(text: str) -> dict[str, Any]:
    """Extract the JSON payload from Claude's reply.

    Models occasionally wrap JSON in ``` fences or add a sentence of preamble; we strip both.
    """
    stripped = text.strip()
    # Strip code fences
    if stripped.startswith("```"):
        # Drop the first line (``` or ```json) and the last ```
        lines = stripped.splitlines()
        if lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        stripped = "\n".join(lines)
    # Find first { and last } as a last-resort recovery
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1:
        stripped = stripped[first : last + 1]
    return json.loads(stripped)


def rank_with_claude(candidates: list[Candidate]) -> list[Candidate]:
    """Call Claude to rank + assign sections. Returns mutated candidates with scores set."""
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; use rank_dry() for offline runs")

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.daily_model,
        max_tokens=4096,
        system=_RANKER_SYSTEM,
        messages=[{"role": "user", "content": _build_user_prompt(candidates)}],
    )
    text = response.content[0].text  # type: ignore[union-attr]
    parsed = _parse_response(text)

    by_id = {c.stable_id: c for c in candidates}
    out: list[Candidate] = []
    for ranked in parsed.get("ranked", []):
        c = by_id.get(ranked["stable_id"])
        if not c:
            log.warning("Ranker returned unknown stable_id: %s", ranked["stable_id"])
            continue
        c.importance_score = float(ranked.get("importance", 0))
        c.novelty_score = float(ranked.get("novelty", 0))
        c.final_rank = int(ranked.get("rank", 0))
        section = ranked.get("section", "")
        if section in ("compliance", "fni", "used-car", "store-ops"):
            c.section_assignment = section
            out.append(c)
    out.sort(key=lambda c: c.final_rank)
    return out


def rank_dry(candidates: list[Candidate]) -> list[Candidate]:
    """Deterministic dry-run ranker. Uses source weight as a proxy for importance.

    Section assignment uses simple keyword heuristics — good enough for offline testing
    of the orchestrator wiring.
    """
    section_keywords = {
        "compliance": ["ftc", "cfpb", "cars rule", "safeguards", "holder rule", "recall", "nhtsa"],
        "fni": ["f&i", "subprime", "captive", "credit", "lender", "approval"],
        "used-car": ["manheim", "used", "wholesale", "auction", "valuation"],
        "store-ops": ["bdc", "dms", "tekion", "cdk", "reynolds", "appointment", "qualif"],
    }
    out: list[Candidate] = []
    for idx, c in enumerate(sorted(candidates, key=lambda x: x.source_weight, reverse=True)):
        c.importance_score = float(c.source_weight)
        c.novelty_score = 5.0
        c.final_rank = idx + 1
        text = (c.headline + " " + c.summary).lower()
        for section, keywords in section_keywords.items():
            if any(k in text for k in keywords):
                c.section_assignment = section
                break
        else:
            c.section_assignment = "store-ops"  # default catch-all
        out.append(c)
        if len(out) >= 12:
            break
    return out


def main() -> None:
    import argparse

    from .ingest import fetch_candidates_from_fixture

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidates = fetch_candidates_from_fixture()
    if args.dry_run or settings.dry_run or not settings.anthropic_api_key:
        ranked = rank_dry(candidates)
        print("DRY RUN — using deterministic ranker")
    else:
        ranked = rank_with_claude(candidates)

    for c in ranked:
        print(f"  #{c.final_rank:2d} [{c.section_assignment or '?':12s}] imp={c.importance_score:.1f} nov={c.novelty_score:.1f}  {c.headline[:70]}")


if __name__ == "__main__":
    main()
