"""Auto-submit to beehiiv Ad Network as soon as eligibility thresholds are met.

Thresholds (from Phase 0 monetization research):
  - subscriber count ≥ 1,000
  - 30-day rolling open rate ≥ 20%
  - on Scale plan or higher (validated by API; we trust beehiiv's response)

Self-test: dry-run mode reports eligibility without submitting.
A persistent flag in data/state.json prevents repeated submissions.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..publish import BEEHIIV_BASE
from .. import analytics, github_alerts

log = logging.getLogger(__name__)

STATE_FILE = settings.data_dir / "state.json"
STATE_KEY = "ad_network_submitted_at"

MIN_SUBS = 1000
MIN_OPEN_RATE = 0.20


@dataclass
class Eligibility:
    eligible: bool
    subscribers: int
    open_rate: float
    blocking_reasons: list[str]


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _fetch_subscriber_count() -> int:
    """Fetch active subscriber count via beehiiv API."""
    url = f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}"
    r = httpx.get(
        url,
        params={"expand[]": "stats"},
        headers={"Authorization": f"Bearer {settings.beehiiv_api_key}"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    stats = data.get("stats") or {}
    return int(stats.get("active_subscriptions") or stats.get("active_subscribers") or 0)


def check_eligibility(*, dry_run: bool = False) -> Eligibility:
    """Return current eligibility state.

    Dry-run uses cached/local data so we can self-test without API access.
    """
    if dry_run or not (settings.beehiiv_api_key and settings.beehiiv_publication_id):
        # Use locally-tracked baseline; default to 0 / 0% if no analytics yet
        baseline = analytics.rolling_baseline_30d()
        subs = int(baseline.get("avg_recipients") or 0)
        open_rate = float(baseline.get("avg_open_rate") or 0.0)
    else:
        subs = _fetch_subscriber_count()
        baseline = analytics.rolling_baseline_30d()
        open_rate = float(baseline.get("avg_open_rate") or 0.0)

    reasons: list[str] = []
    if subs < MIN_SUBS:
        reasons.append(f"subscribers {subs} < {MIN_SUBS}")
    if open_rate < MIN_OPEN_RATE:
        reasons.append(f"open rate {open_rate:.1%} < {MIN_OPEN_RATE:.0%}")

    return Eligibility(
        eligible=not reasons,
        subscribers=subs,
        open_rate=open_rate,
        blocking_reasons=reasons,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def _submit_application() -> dict:
    """POST the Ad Network application to beehiiv.

    The exact endpoint shape may evolve — we hit the documented monetization endpoint
    and let beehiiv tell us if more data is needed.
    """
    url = f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}/ad_network/applications"
    r = httpx.post(
        url,
        json={"category": "auto_dealer_ops", "self_certify_open_rate": True},
        headers={
            "Authorization": f"Bearer {settings.beehiiv_api_key}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def maybe_submit(*, dry_run: bool = False) -> Optional[str]:
    """If eligible and not already submitted, submit. Returns a status message."""
    state = _load_state()
    if state.get(STATE_KEY):
        return f"Already submitted on {state[STATE_KEY]}; skipping"

    elig = check_eligibility(dry_run=dry_run)
    if not elig.eligible:
        return f"Not yet eligible: {', '.join(elig.blocking_reasons)}"

    if dry_run:
        msg = f"DRY RUN: eligible (subs={elig.subscribers}, open_rate={elig.open_rate:.1%}); would submit"
        log.info(msg)
        return msg

    if not (settings.beehiiv_api_key and settings.beehiiv_publication_id):
        return "Eligible but BEEHIIV_API_KEY missing; cannot submit"

    result = _submit_application()
    from datetime import datetime, timezone
    state[STATE_KEY] = datetime.now(timezone.utc).isoformat()
    _save_state(state)

    github_alerts.open_issue(
        title=f"📈 Ad Network application submitted — {elig.subscribers} subs, {elig.open_rate:.1%} open rate",
        body=f"Auto-submitted via pipeline.\n\nResponse:\n```json\n{json.dumps(result, indent=2)}\n```\n\nbeehiiv typically reviews within 5 business days. No action needed unless rejected.",
        labels=["ad-network", "milestone"],
    )
    return f"Submitted: {result}"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true", help="clear submitted state (testing only)")
    args = parser.parse_args()
    if args.reset:
        s = _load_state()
        s.pop(STATE_KEY, None)
        _save_state(s)
        print("Reset.")
        return
    print(maybe_submit(dry_run=args.dry_run or settings.dry_run))


if __name__ == "__main__":
    main()
