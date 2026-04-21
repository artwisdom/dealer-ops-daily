"""Daily Boosts cross-promotion rotation.

Pulls today's available Boost offers from beehiiv's marketplace, asks Claude to
pick the best fit (semantic match to our niche, not in the rejected categories,
not duplicate of recent picks), and applies it.

Editorial veto categories (never accept regardless of CPM):
  - payday lending / debt consolidation
  - crypto / NFT / Web3
  - non-auto MLM / direct sales
  - cannabis / THC products
  - politically partisan content

Self-test: dry-run pulls fixture offers and runs the picker locally.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .. import _llm, github_alerts
from ..config import settings
from ..publish import BEEHIIV_BASE

log = logging.getLogger(__name__)


VETO_KEYWORDS = {
    "payday", "debt-consolidation", "debt consolidation",
    "crypto", "cryptocurrency", "nft", "web3", "defi",
    "mlm", "multi-level",
    "cannabis", "thc", "cbd",
    "partisan", "republican", "democrat", "maga",
}

BOOST_PICKER_SYSTEM = """You are choosing today's Boost partner for Dealer Ops Daily, a daily newsletter for U.S. auto dealership operators.

You receive a JSON list of available beehiiv Boost offers. For each, you see: name, tags, description, audience description, payout per subscriber, and minimum quality bar.

Pick the SINGLE best fit. Criteria, in order:

1. Audience overlap with U.S. dealer operators / auto-vendor B2B / sales operators / small-business owners
2. Editorial coherence — would our reader thank us for the recommendation?
3. Payout per subscriber (tiebreaker only)

Hard rules:
- Never pick anything containing veto categories (payday, crypto, MLM, cannabis, partisan content)
- Never pick the same partner picked in the last 14 days (we'll tell you the recent set)
- If no offer scores ≥ 6/10 on overlap, return null — better to skip than force a bad fit

Return ONLY a JSON object:
{
  "picked_id": "<offer id, or null if no good fit>",
  "score": 0-10,
  "reasoning": "<1 sentence>"
}
"""


def _state_path() -> str:
    return str(settings.data_dir / "boost_history.json")


def _load_history() -> list[dict[str, Any]]:
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _save_history(history: list[dict[str, Any]]) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)


def recent_partner_ids(days: int = 14) -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [h["picked_id"] for h in _load_history() if h.get("picked_at", "") >= cutoff and h.get("picked_id")]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def fetch_marketplace() -> list[dict[str, Any]]:
    """Pull available Boost offers from beehiiv. Endpoint shape may evolve."""
    url = f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}/boosts/marketplace"
    r = httpx.get(
        url,
        headers={"Authorization": f"Bearer {settings.beehiiv_api_key}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_marketplace_fixture() -> list[dict[str, Any]]:
    fixture = settings.fixtures_dir / "boost_offers.json"
    if not fixture.exists():
        # Seed a default fixture
        sample = [
            {
                "id": "off_1",
                "name": "DealerSocket Daily Tips",
                "tags": ["automotive", "dealer-ops", "b2b"],
                "description": "Daily 1-tip-1-action newsletter for variable ops managers.",
                "audience": "U.S. franchised dealer GMs and variable ops directors.",
                "payout_per_sub": 4.20,
                "min_quality_bar": "Web Boost",
            },
            {
                "id": "off_2",
                "name": "F&I Profitability Briefing",
                "tags": ["fni", "finance", "compliance"],
                "description": "Weekly F&I product economics and compliance digest.",
                "audience": "F&I directors and finance managers at franchised dealers.",
                "payout_per_sub": 5.10,
                "min_quality_bar": "Web Boost",
            },
            {
                "id": "off_3",
                "name": "Crypto Trader Daily",
                "tags": ["crypto", "investing"],
                "description": "Daily crypto market signals.",
                "audience": "Retail crypto traders.",
                "payout_per_sub": 6.90,
                "min_quality_bar": "Email Boost",
            },
            {
                "id": "off_4",
                "name": "Manheim Wholesale Watch",
                "tags": ["used-car", "wholesale", "auction"],
                "description": "Twice-weekly used-car wholesale market briefing.",
                "audience": "Used-car managers and inventory specialists.",
                "payout_per_sub": 3.80,
                "min_quality_bar": "Web Boost",
            },
        ]
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(json.dumps(sample, indent=2), encoding="utf-8")
    return json.loads(fixture.read_text(encoding="utf-8"))


def _veto(offer: dict[str, Any]) -> bool:
    """Return True if this offer trips an editorial veto."""
    text = " ".join([
        offer.get("name", ""),
        offer.get("description", ""),
        " ".join(offer.get("tags", [])),
        offer.get("audience", ""),
    ]).lower()
    return any(v in text for v in VETO_KEYWORDS)


def pick_dry(offers: list[dict[str, Any]], recent_ids: list[str]) -> dict[str, Any]:
    """Deterministic picker for dry-run: highest payout among non-vetoed, non-recent
    offers tagged with auto/dealer/fni/used-car/store-ops."""
    fit_tags = {"automotive", "dealer-ops", "fni", "finance", "used-car", "wholesale", "compliance", "store-ops", "b2b"}
    eligible = []
    for o in offers:
        if _veto(o) or o.get("id") in recent_ids:
            continue
        tag_set = {t.lower() for t in o.get("tags", [])}
        if not (fit_tags & tag_set):
            continue
        eligible.append(o)
    if not eligible:
        return {"picked_id": None, "score": 0, "reasoning": "no offers passed veto + tag filter"}
    best = max(eligible, key=lambda o: o.get("payout_per_sub", 0))
    return {
        "picked_id": best["id"],
        "score": 7,
        "reasoning": f"deterministic dry pick: highest payout among on-niche offers ({best['name']}, ${best.get('payout_per_sub', 0):.2f}/sub)",
    }


def pick_with_claude(offers: list[dict[str, Any]], recent_ids: list[str]) -> dict[str, Any]:
    """Ask Claude to score + pick."""
    user = json.dumps({
        "today": date.today().isoformat(),
        "recently_used_partner_ids": recent_ids,
        "offers": offers,
    }, indent=2)
    return _llm.call_json(system=BOOST_PICKER_SYSTEM, user=user)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def _accept_boost(offer_id: str) -> dict[str, Any]:
    url = f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}/boosts/marketplace/{offer_id}/accept"
    r = httpx.post(
        url,
        headers={"Authorization": f"Bearer {settings.beehiiv_api_key}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def rotate(*, dry_run: bool = False) -> dict[str, Any]:
    """Daily rotation entry point.

    1. Fetch offers (live or fixture)
    2. Pick the best one (Claude or deterministic)
    3. Accept it via beehiiv API (skipped in dry-run)
    4. Append to boost_history.json
    """
    if dry_run or not (settings.beehiiv_api_key and settings.beehiiv_publication_id):
        offers = fetch_marketplace_fixture()
    else:
        offers = fetch_marketplace()

    recent = recent_partner_ids()

    if dry_run or not settings.anthropic_api_key:
        decision = pick_dry(offers, recent)
    else:
        decision = pick_with_claude(offers, recent)

    record = {
        "picked_at": datetime.now(timezone.utc).isoformat(),
        "picked_id": decision.get("picked_id"),
        "score": decision.get("score"),
        "reasoning": decision.get("reasoning"),
        "dry_run": dry_run,
    }

    if decision.get("picked_id") and not dry_run:
        try:
            api_response = _accept_boost(decision["picked_id"])
            record["accepted"] = True
            record["api_response"] = api_response
        except Exception as exc:  # noqa: BLE001
            log.warning("Boost accept failed: %s", exc)
            record["accepted"] = False
            record["error"] = str(exc)
            github_alerts.open_issue(
                title=f"⚠️ Boost accept failed for {decision['picked_id']}",
                body=f"Reasoning was: {decision.get('reasoning')}\n\nError: {exc}",
                labels=["boost", "needs-triage"],
            )

    history = _load_history()
    history.append(record)
    _save_history(history)
    return record


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = rotate(dry_run=args.dry_run or settings.dry_run)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
