"""Loop 4: Affiliate link ROI rotation.

Weekly: pull 30-day click + conversion data per affiliate. Retire any link with
< 0.5% CTR (after ≥7 placements). When an affiliate is retired, auto-onboard the
top-scoring candidate from data/affiliate_watchlist.json.

Editorial constraint: never have zero affiliates loaded. If retiring would empty
the inventory, file an issue but keep the underperformer until a replacement
is available.
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .. import github_alerts
from ..config import settings
from ..models import Affiliate

log = logging.getLogger(__name__)

CLICKS_FILE = settings.data_dir / "affiliate_clicks.jsonl"
WATCHLIST_FILE = settings.data_dir / "affiliate_watchlist.json"
INVENTORY_FILE = settings.data_dir / "affiliates.json"

MIN_PLACEMENTS_TO_JUDGE = 7
MIN_CTR_TO_KEEP = 0.005  # 0.5%
WINDOW_DAYS = 30


@dataclass
class AffiliatePerf:
    product_id: str
    placements: int
    impressions: int
    clicks: int
    ctr: float


def record_click(product_id: str, click_count: int, impressions: int) -> None:
    """Called by analytics.py after attribution. One row per (issue, affiliate)."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "product_id": product_id,
        "click_count": int(click_count),
        "impressions": int(impressions),
    }
    with CLICKS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _load_clicks(window_days: int = WINDOW_DAYS) -> list[dict]:
    if not CLICKS_FILE.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    out: list[dict] = []
    with CLICKS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("logged_at", "") >= cutoff:
                out.append(row)
    return out


def compute_perf() -> dict[str, AffiliatePerf]:
    rows = _load_clicks()
    agg: dict[str, dict] = defaultdict(lambda: {"placements": 0, "impressions": 0, "clicks": 0})
    for r in rows:
        a = agg[r["product_id"]]
        a["placements"] += 1
        a["impressions"] += int(r["impressions"])
        a["clicks"] += int(r["click_count"])
    perf = {}
    for pid, vals in agg.items():
        ctr = vals["clicks"] / vals["impressions"] if vals["impressions"] else 0.0
        perf[pid] = AffiliatePerf(
            product_id=pid, placements=vals["placements"], impressions=vals["impressions"],
            clicks=vals["clicks"], ctr=ctr,
        )
    return perf


def _load_inventory() -> list[Affiliate]:
    if not INVENTORY_FILE.exists():
        return []
    raw = json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
    return [Affiliate.model_validate(a) for a in raw]


def _save_inventory(affiliates: list[Affiliate]) -> None:
    INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY_FILE.write_text(
        json.dumps([a.model_dump(mode="json") for a in affiliates], indent=2),
        encoding="utf-8",
    )


def _load_watchlist() -> list[Affiliate]:
    if not WATCHLIST_FILE.exists():
        return []
    raw = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    return [Affiliate.model_validate(a) for a in raw]


def _save_watchlist(items: list[Affiliate]) -> None:
    WATCHLIST_FILE.write_text(
        json.dumps([a.model_dump(mode="json") for a in items], indent=2),
        encoding="utf-8",
    )


def rotate(*, dry_run: bool = False) -> dict:
    """Retire underperformers, promote watchlist candidates."""
    perf = compute_perf()
    inventory = _load_inventory()
    watchlist = _load_watchlist()

    if not inventory:
        log.info("No inventory loaded; skipping")
        return {"retired": [], "promoted": []}

    underperformers = [
        a for a in inventory
        if a.product_id in perf
        and perf[a.product_id].placements >= MIN_PLACEMENTS_TO_JUDGE
        and perf[a.product_id].ctr < MIN_CTR_TO_KEEP
        and a.active
    ]

    retired_ids: list[str] = []
    promoted_ids: list[str] = []

    for under in underperformers:
        if not watchlist:
            log.warning("Underperformer %s but no watchlist; keeping in rotation", under.product_id)
            github_alerts.open_issue(
                title=f"🪦 Affiliate {under.product_id} underperforming, no replacement available",
                body=f"CTR: {perf[under.product_id].ctr:.3%} (target ≥{MIN_CTR_TO_KEEP:.1%}). Add candidates to data/affiliate_watchlist.json.",
                labels=["loop-affiliate-roi", "needs-review"],
            )
            continue

        # Inactivate underperformer
        under.active = False
        retired_ids.append(under.product_id)

        # Promote top of watchlist
        candidate = watchlist.pop(0)
        candidate.active = True
        inventory.append(candidate)
        promoted_ids.append(candidate.product_id)

        if not dry_run:
            github_alerts.open_issue(
                title=f"🔄 Affiliate rotated: {under.product_id} → {candidate.product_id}",
                body=(
                    f"**Retired:** {under.product_name} (CTR {perf[under.product_id].ctr:.3%} after {perf[under.product_id].placements} placements)\n\n"
                    f"**Promoted from watchlist:** {candidate.product_name}\n\n"
                    f"To revert: edit `data/affiliates.json` and `data/affiliate_watchlist.json`."
                ),
                labels=["loop-affiliate-roi"],
            )

    if dry_run:
        log.info("DRY RUN: would retire %s, promote %s", retired_ids, promoted_ids)
    else:
        _save_inventory(inventory)
        _save_watchlist(watchlist)

    return {"retired": retired_ids, "promoted": promoted_ids}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = rotate(dry_run=args.dry_run or settings.dry_run)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
