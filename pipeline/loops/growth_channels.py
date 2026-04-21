"""Loop 5: Growth channel reallocation.

Monthly: walk subscriber attribution data, compute LTV per source channel
(Boost, SparkLoop, organic referral, direct, dealerintel-seed). Recommend
where to shift budget — concretely, by writing a recommendation file and
filing a GitHub Issue.

This module decides; it does not move money. The operator must approve any
SparkLoop budget changes manually (per safety rules — financial transactions
require explicit user permission).
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .. import github_alerts
from ..config import settings

log = logging.getLogger(__name__)


SUB_ATTRIBUTION_FILE = settings.data_dir / "subscriber_attribution.jsonl"
WINDOW_DAYS = 30


@dataclass
class ChannelPerf:
    channel: str
    new_subs: int
    cost_total: float
    revenue_attributed: float
    cost_per_sub: float
    revenue_per_sub: float
    ltv_cac_ratio: float


def record_subscriber_event(channel: str, new_subs: int, cost: float, revenue_attributed: float) -> None:
    """Append one row per (date, channel). Called from a separate ingest of beehiiv data."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "channel": channel,  # "boost" | "sparkloop" | "referral" | "direct" | "seed-list"
        "new_subs": int(new_subs),
        "cost": float(cost),
        "revenue_attributed": float(revenue_attributed),
    }
    with SUB_ATTRIBUTION_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _load(window_days: int = WINDOW_DAYS) -> list[dict]:
    if not SUB_ATTRIBUTION_FILE.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    out = []
    with SUB_ATTRIBUTION_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("logged_at", "") >= cutoff:
                out.append(row)
    return out


def compute_perf() -> dict[str, ChannelPerf]:
    rows = _load()
    agg: dict[str, dict] = defaultdict(lambda: {"new_subs": 0, "cost": 0.0, "revenue": 0.0})
    for r in rows:
        a = agg[r["channel"]]
        a["new_subs"] += int(r["new_subs"])
        a["cost"] += float(r["cost"])
        a["revenue"] += float(r["revenue_attributed"])

    out: dict[str, ChannelPerf] = {}
    for ch, vals in agg.items():
        cps = vals["cost"] / vals["new_subs"] if vals["new_subs"] else 0.0
        rps = vals["revenue"] / vals["new_subs"] if vals["new_subs"] else 0.0
        ratio = rps / cps if cps else float("inf")
        out[ch] = ChannelPerf(
            channel=ch,
            new_subs=vals["new_subs"],
            cost_total=vals["cost"],
            revenue_attributed=vals["revenue"],
            cost_per_sub=cps,
            revenue_per_sub=rps,
            ltv_cac_ratio=ratio,
        )
    return out


def make_recommendation(perf: dict[str, ChannelPerf]) -> dict[str, Any]:
    """Produce a scored recommendation. Pure function; no side effects."""
    if not perf:
        return {"recommendation": "insufficient_data", "details": "No channel attribution recorded yet"}

    paid = [p for p in perf.values() if p.cost_total > 0]
    free = [p for p in perf.values() if p.cost_total == 0]

    paid_sorted = sorted(paid, key=lambda p: p.ltv_cac_ratio, reverse=True)
    free_sorted = sorted(free, key=lambda p: p.new_subs, reverse=True)

    actions: list[str] = []
    if paid_sorted:
        winner = paid_sorted[0]
        loser = paid_sorted[-1] if len(paid_sorted) > 1 else None
        if winner.ltv_cac_ratio >= 3.0:
            actions.append(f"Increase budget on `{winner.channel}` (LTV/CAC = {winner.ltv_cac_ratio:.1f}x).")
        if loser and loser is not winner and loser.ltv_cac_ratio < 2.0:
            actions.append(f"Reduce or pause `{loser.channel}` (LTV/CAC = {loser.ltv_cac_ratio:.1f}x).")
    if free_sorted:
        leader = free_sorted[0]
        if leader.new_subs > 0:
            actions.append(f"Highest free channel: `{leader.channel}` ({leader.new_subs} subs/mo) — keep doing what's working.")

    return {
        "recommendation": "; ".join(actions) if actions else "no_action",
        "channels": {p.channel: vars(p) for p in perf.values()},
    }


def report(*, dry_run: bool = False) -> dict[str, Any]:
    perf = compute_perf()
    rec = make_recommendation(perf)
    if rec.get("recommendation") in ("insufficient_data", "no_action"):
        log.info("Loop 5: %s", rec["recommendation"])
        return rec

    body_lines = ["**Channel performance (last 30d):**\n"]
    for ch, p in rec["channels"].items():
        body_lines.append(
            f"- `{ch}` — {p['new_subs']} subs, "
            f"cost ${p['cost_total']:.2f} (${p['cost_per_sub']:.2f}/sub), "
            f"attributed revenue ${p['revenue_attributed']:.2f}, "
            f"LTV/CAC = {p['ltv_cac_ratio']:.1f}x"
        )
    body_lines.append("\n**Recommendation:**\n")
    body_lines.append(rec["recommendation"])
    body_lines.append("\n*Operator approval required for any budget change. This loop reports only.*")

    if not dry_run:
        github_alerts.open_issue(
            title=f"📊 Growth channel report — {date.today():%Y-%m}",
            body="\n".join(body_lines),
            labels=["loop-growth-channels"],
        )
    else:
        log.info("DRY RUN — would file:\n%s", "\n".join(body_lines))

    return rec


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = report(dry_run=args.dry_run or settings.dry_run)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
