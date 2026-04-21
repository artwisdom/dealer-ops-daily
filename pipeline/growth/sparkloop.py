"""SparkLoop Upscribe integration.

SparkLoop is the third-party paid-acquisition layer beehiiv plugs into.
Once a SPARKLOOP_API_KEY is set, this module:
  - Reads our current cost-per-sub from SparkLoop
  - Reads our LTV (computed from analytics + monetization tracking)
  - Decides whether to keep paid acquisition on or pause based on LTV/CAC ratio

Decision rules (from monetization research):
  - LTV/CAC ≥ 3.0 → keep on, no action
  - 2.0 ≤ LTV/CAC < 3.0 → keep on but file an issue to review caps
  - LTV/CAC < 2.0 → pause Upscribe via API and file an alert

This is a Phase 3 stub — the real SparkLoop endpoints require account setup.
The control logic (when to pause/resume) is fully implemented and tested.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .. import analytics, github_alerts
from ..config import settings

log = logging.getLogger(__name__)

SPARKLOOP_BASE = "https://api.sparkloop.app/v1"


@dataclass
class LTVCACReport:
    cost_per_sub: float
    ltv_per_sub: float
    ratio: float
    recommendation: str  # "keep_on" | "review" | "pause"
    reasoning: str


def _sparkloop_api_key() -> str:
    return os.environ.get("SPARKLOOP_API_KEY", "")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def fetch_cost_per_sub() -> float:
    """Pull the trailing 30-day cost-per-subscriber from SparkLoop."""
    api_key = _sparkloop_api_key()
    if not api_key:
        raise RuntimeError("SPARKLOOP_API_KEY not set")
    r = httpx.get(
        f"{SPARKLOOP_BASE}/upscribe/stats",
        params={"period": "30d"},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    return float(data.get("cost_per_subscriber") or 0.0)


def estimate_ltv_per_sub() -> float:
    """Estimate LTV from our own analytics + monetization tracking.

    Conservative formula: 30-day Ad Network revenue per active subscriber × 12.
    Replaced with cohort-tracked LTV once we have ≥6 months of data.
    """
    baseline = analytics.rolling_baseline_30d()
    avg_recipients = baseline.get("avg_recipients") or 0
    if not avg_recipients:
        return 0.0
    # Pull monthly Ad Network revenue from a separate tracker (Phase 4 ROI loop will fill this)
    ad_network_state = settings.data_dir / "ad_network_revenue.json"
    monthly_revenue = 0.0
    if ad_network_state.exists():
        try:
            data = json.loads(ad_network_state.read_text(encoding="utf-8"))
            monthly_revenue = float(data.get("trailing_30d_total") or 0.0)
        except Exception:  # noqa: BLE001
            log.warning("Could not parse ad_network_revenue.json; assuming 0")
    revenue_per_sub_monthly = monthly_revenue / avg_recipients
    return revenue_per_sub_monthly * 12  # annualize


def evaluate(*, dry_run: bool = False) -> LTVCACReport:
    """Compute today's LTV/CAC and the recommendation."""
    if dry_run or not _sparkloop_api_key():
        # In dev, use realistic placeholders so the recommendation logic is exercised
        cost = 1.80
        ltv = estimate_ltv_per_sub() or 4.50
    else:
        cost = fetch_cost_per_sub()
        ltv = estimate_ltv_per_sub()

    if cost == 0:
        return LTVCACReport(
            cost_per_sub=0,
            ltv_per_sub=ltv,
            ratio=float("inf"),
            recommendation="keep_on",
            reasoning="No paid acquisition cost recorded yet — cannot compute ratio",
        )

    ratio = ltv / cost if cost > 0 else 0
    if ratio >= 3.0:
        rec = "keep_on"
        reason = f"Healthy: LTV/CAC = {ratio:.1f}x — no action."
    elif ratio >= 2.0:
        rec = "review"
        reason = f"Marginal: LTV/CAC = {ratio:.1f}x — review caps but don't pause."
    else:
        rec = "pause"
        reason = f"Underwater: LTV/CAC = {ratio:.1f}x — pause Upscribe to stop bleeding."

    return LTVCACReport(cost_per_sub=cost, ltv_per_sub=ltv, ratio=ratio, recommendation=rec, reasoning=reason)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def pause_upscribe() -> dict:
    api_key = _sparkloop_api_key()
    r = httpx.post(
        f"{SPARKLOOP_BASE}/upscribe/pause",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def act_on(report: LTVCACReport, *, dry_run: bool = False) -> Optional[str]:
    """Take the action implied by the report. Returns a status message."""
    if report.recommendation == "keep_on":
        return None
    if report.recommendation == "review":
        url = github_alerts.open_issue(
            title=f"⚠️ SparkLoop LTV/CAC marginal — {report.ratio:.1f}x",
            body=f"{report.reasoning}\n\n- Cost/sub: ${report.cost_per_sub:.2f}\n- LTV/sub: ${report.ltv_per_sub:.2f}\n\nRecommended action: review SparkLoop spend caps. Don't pause yet.",
            labels=["sparkloop", "monetization"],
        )
        return f"Filed review alert: {url}"
    if report.recommendation == "pause":
        if dry_run or not _sparkloop_api_key():
            return f"DRY RUN: would pause Upscribe (ratio={report.ratio:.1f}x)"
        result = pause_upscribe()
        url = github_alerts.open_issue(
            title=f"🛑 SparkLoop paused — LTV/CAC = {report.ratio:.1f}x",
            body=f"Auto-paused via pipeline.\n\n{report.reasoning}\n\nResponse:\n```json\n{json.dumps(result, indent=2)}\n```\n\nResume manually after the underlying acquisition quality issue is fixed.",
            labels=["sparkloop", "monetization", "auto-paused"],
        )
        return f"Paused. Alert: {url}"
    return f"Unknown recommendation: {report.recommendation}"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = evaluate(dry_run=args.dry_run or settings.dry_run)
    print(json.dumps(report.__dict__, indent=2))
    msg = act_on(report, dry_run=args.dry_run or settings.dry_run)
    if msg:
        print(msg)


if __name__ == "__main__":
    main()
