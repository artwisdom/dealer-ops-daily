"""Monthly sponsor prospect list generator.

Once a month, Claude reviews:
  - The auto-vendor categories most relevant to our reader
  - Our last 30 days of issues (which topics performed best)
  - Existing affiliate relationships (don't double-pitch)
  - Public list of beehiiv-friendly direct-sponsor verticals

Output: a ranked list of sponsor prospects, persisted to drafts/sponsor-prospects-YYYY-MM.json,
with a brief rationale per candidate. The outreach module turns this into actual
draft emails.

Self-test: dry-run produces a deterministic list from a curated seed.
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


SPONSOR_GENERATOR_SYSTEM = """You are generating a monthly sponsor prospect list for Dealer Ops Daily, an AI-edited daily newsletter for U.S. auto dealership operators (F&I directors, desk managers, used-car managers, compliance leads, floor GMs).

You receive:
  - Our reader profile and current subscriber count
  - Top-performing topics from the last 30 days
  - Our existing affiliate / sponsor relationships (do NOT re-pitch these)
  - The size of our subscriber list (use this to size the pitch — small lists pitch with persona quality, not raw reach)

Generate a ranked list of 8-12 prospect categories AND specific company names within each. For each prospect:
  - company / product name
  - category (e.g. "DMS vendor", "F&I product manufacturer", "compliance attorney", "BDC software")
  - why they fit (1 sentence — what about our audience matters to them)
  - suggested pitch angle (1 sentence — what we'd offer, e.g. "dedicated weekly slot", "Tool of the Day rotation", "category-exclusive sponsorship")
  - estimated CPM range we should ask for ($25-$100)
  - cold/warm/hot rating (warm = vendor with public dealer-tech newsletter spend; cold = haven't sponsored newsletters before)

Hard rules:
  - Don't suggest competitors of the operator's own SaaS (DealerIntel — auto-dealer SaaS)
  - Don't suggest companies in the editorial veto list: payday, crypto, MLM, cannabis, partisan
  - Don't suggest media buyers / agencies — only direct sponsors
  - Cap CPM suggestions at $100 (we're not enterprise yet)

Return ONLY a JSON object:
{
  "generated_at": "<ISO date>",
  "subscriber_count_used": <int>,
  "prospects": [
    {
      "company": "...",
      "category": "...",
      "fit_reason": "...",
      "pitch_angle": "...",
      "cpm_low": 25,
      "cpm_high": 50,
      "warmth": "cold|warm|hot"
    },
    ...
  ]
}
"""


def _seed_prospects() -> list[dict[str, Any]]:
    """Deterministic dry-run prospects — covers the major auto-vendor categories."""
    return [
        {"company": "Tekion", "category": "Modern DMS", "fit_reason": "Replacing CDK/Reynolds at the operator level.", "pitch_angle": "Tool of the Day rotation tied to DMS-migration weeks.", "cpm_low": 40, "cpm_high": 80, "warmth": "warm"},
        {"company": "RouteOne", "category": "F&I e-contracting", "fit_reason": "Active in F&I director audience.", "pitch_angle": "Dedicated F&I week sponsorship.", "cpm_low": 35, "cpm_high": 70, "warmth": "warm"},
        {"company": "Hudson Cook", "category": "Dealer compliance attorneys", "fit_reason": "CARS Rule + Holder Rule news drives compliance pulls.", "pitch_angle": "Quarterly compliance digest sponsorship.", "cpm_low": 30, "cpm_high": 60, "warmth": "cold"},
        {"company": "Dealertrack", "category": "F&I tech", "fit_reason": "Long-tail F&I director attention.", "pitch_angle": "Attach-rate benchmarking content cosponsorship.", "cpm_low": 35, "cpm_high": 65, "warmth": "cold"},
        {"company": "vAuto", "category": "Used-car desking", "fit_reason": "Used-car manager mind-share is our 4th-largest section.", "pitch_angle": "Used-car desking week sponsorship.", "cpm_low": 40, "cpm_high": 80, "warmth": "hot"},
        {"company": "ASOTU", "category": "Industry community", "fit_reason": "Cross-promotional fit; not a sponsor but a co-marketing partner.", "pitch_angle": "Trade — they promote us to their list, we feature them in a profile.", "cpm_low": 0, "cpm_high": 0, "warmth": "warm"},
        {"company": "Manheim", "category": "Wholesale market", "fit_reason": "Used-car valuation moves are a recurring beat.", "pitch_angle": "Monthly used-vehicle index sponsored block.", "cpm_low": 50, "cpm_high": 100, "warmth": "cold"},
        {"company": "Westlake Financial", "category": "Subprime captive lender", "fit_reason": "Subprime approval rate news touches our F&I subscribers directly.", "pitch_angle": "Subprime week sponsorship.", "cpm_low": 30, "cpm_high": 60, "warmth": "cold"},
    ]


def generate(*, dry_run: bool = False, subscriber_count: int = 1500) -> dict[str, Any]:
    """Produce this month's prospect list. Returns the parsed JSON.

    Persists to drafts/sponsor-prospects-YYYY-MM.json so outreach.py can consume it.
    """
    if dry_run or not settings.anthropic_api_key:
        result = {
            "generated_at": date.today().isoformat(),
            "subscriber_count_used": subscriber_count,
            "prospects": _seed_prospects(),
            "dry_run": True,
        }
    else:
        from .. import affiliates
        existing = [a.product_name for a in affiliates.load_inventory()]
        # Read top topics from this month's analytics if present (Phase 4 adds this)
        user = json.dumps({
            "subscriber_count": subscriber_count,
            "existing_affiliates": existing,
            "top_topics_30d": [],  # Phase 4 source-quality module fills this
        }, indent=2)
        result = _llm.call_json(system=SPONSOR_GENERATOR_SYSTEM, user=user)

    out_dir = Path(settings.data_dir).parent / "drafts"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"sponsor-prospects-{date.today():%Y-%m}.json"
    fname.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log.info("Wrote %s prospects to %s", len(result.get("prospects", [])), fname)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--subs", type=int, default=1500)
    args = parser.parse_args()
    out = generate(dry_run=args.dry_run or settings.dry_run, subscriber_count=args.subs)
    print(f"Generated {len(out.get('prospects', []))} prospects")
    for p in out.get("prospects", []):
        print(f"  [{p.get('warmth', '?')}] {p.get('company')}  ({p.get('category')})  ${p.get('cpm_low', 0)}-${p.get('cpm_high', 0)}")


if __name__ == "__main__":
    main()
