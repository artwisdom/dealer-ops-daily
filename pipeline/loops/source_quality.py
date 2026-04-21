"""Loop 1: Source quality scoring.

Every issue records which sources contributed which stories. Stories that drove
the highest click-through get their sources up-weighted in tomorrow's priority
ranking. Sources that consistently produce ignored content get pruned after 30 days.

Inputs:
  - data/source_attribution.jsonl  (one row per (issue_date, story_id, source_id, click_count))
  - data/analytics.json            (issue-level click totals)
  - sources.yaml                   (current weights — we read AND write this)

Output:
  - sources.yaml is rewritten with updated weights
  - Sources with 30+ days of low CTR are flagged for removal in a GitHub Issue
    (we don't auto-delete — operator approves)

Self-test: with no attribution data, weights stay unchanged (no-op).
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

import yaml

from .. import github_alerts
from ..config import settings
from ..models import SourceList

log = logging.getLogger(__name__)

ATTRIBUTION_FILE = settings.data_dir / "source_attribution.jsonl"
WINDOW_DAYS = 30
MIN_CONTRIBUTIONS_TO_PRUNE = 5  # need ≥5 stories before judging
MIN_CTR_TO_KEEP = 0.005  # 0.5% — sources below this get flagged
WEIGHT_BUMP_FOR_TOP_QUARTILE = 1
WEIGHT_DEDUCT_FOR_BOTTOM_QUARTILE = 1
MIN_WEIGHT = 1
MAX_WEIGHT = 10


@dataclass
class SourcePerf:
    name: str
    contributions: int = 0
    total_clicks: int = 0
    weighted_ctr: float = 0.0  # clicks per 1k recipients


def record_attribution(issue_date: date, story_id: str, source_id: str, click_count: int, recipients: int) -> None:
    """Append one attribution row. Called from publish.py after a send."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "issue_date": issue_date.isoformat(),
        "story_id": story_id,
        "source_id": source_id,
        "click_count": click_count,
        "recipients": recipients,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    with ATTRIBUTION_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _load_attribution(window_days: int = WINDOW_DAYS) -> list[dict]:
    if not ATTRIBUTION_FILE.exists():
        return []
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()
    out: list[dict] = []
    with ATTRIBUTION_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("issue_date", "") >= cutoff:
                out.append(row)
    return out


def compute_perf() -> dict[str, SourcePerf]:
    """Aggregate attribution data into per-source CTR."""
    rows = _load_attribution()
    perf: dict[str, SourcePerf] = defaultdict(lambda: SourcePerf(name=""))
    for row in rows:
        sid = row.get("source_id", "")
        if not sid:
            continue
        p = perf[sid]
        p.name = sid
        p.contributions += 1
        p.total_clicks += int(row.get("click_count", 0))
        recipients = int(row.get("recipients", 0))
        if recipients > 0:
            p.weighted_ctr += (row["click_count"] / recipients) * 1000
    # Average CTR per contribution (weighted_ctr was a sum)
    for p in perf.values():
        if p.contributions:
            p.weighted_ctr /= p.contributions
    return dict(perf)


def adjust_weights(*, dry_run: bool = False) -> dict[str, int]:
    """Walk perf data, adjust source weights, write sources.yaml. Returns {source_name: delta}."""
    perf = compute_perf()
    if not perf:
        log.info("No attribution data yet; skipping")
        return {}

    # Compute quartiles among sources with enough data to judge
    judgable = [p for p in perf.values() if p.contributions >= MIN_CONTRIBUTIONS_TO_PRUNE]
    if not judgable:
        log.info("No sources have enough contributions yet; skipping")
        return {}

    sorted_by_ctr = sorted(judgable, key=lambda p: p.weighted_ctr)
    n = len(sorted_by_ctr)
    bottom_q = sorted_by_ctr[: max(1, n // 4)]
    top_q = sorted_by_ctr[-max(1, n // 4):]

    bottom_names = {p.name for p in bottom_q}
    top_names = {p.name for p in top_q}

    sources_text = settings.sources_file.read_text(encoding="utf-8")
    sources_obj = yaml.safe_load(sources_text)
    deltas: dict[str, int] = {}

    for entry in sources_obj.get("sources", []):
        name = entry.get("name", "")
        old = int(entry.get("weight", 5))
        new = old
        if name in top_names:
            new = min(MAX_WEIGHT, old + WEIGHT_BUMP_FOR_TOP_QUARTILE)
        elif name in bottom_names:
            new = max(MIN_WEIGHT, old - WEIGHT_DEDUCT_FOR_BOTTOM_QUARTILE)
        if new != old:
            deltas[name] = new - old
            entry["weight"] = new

    # Flag pure-zero CTR sources after MIN_CONTRIBUTIONS_TO_PRUNE for removal review
    flag_for_removal = [
        p.name for p in judgable
        if p.total_clicks == 0 and p.contributions >= MIN_CONTRIBUTIONS_TO_PRUNE
    ]
    if flag_for_removal and not dry_run:
        github_alerts.open_issue(
            title=f"🪦 Source-quality loop: {len(flag_for_removal)} sources with 0 clicks in 30d",
            body=(
                "These sources contributed ≥5 stories in the last 30 days but generated zero clicks. "
                "Consider removing from sources.yaml:\n\n"
                + "\n".join(f"- {n}" for n in flag_for_removal)
                + "\n\nThis loop never auto-deletes — review and delete manually."
            ),
            labels=["loop-source-quality", "needs-triage"],
        )

    if deltas and not dry_run:
        settings.sources_file.write_text(yaml.safe_dump(sources_obj, sort_keys=False), encoding="utf-8")
        log.info("Updated %d source weights", len(deltas))
    elif dry_run:
        log.info("DRY RUN: would update %d source weights", len(deltas))

    return deltas


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    deltas = adjust_weights(dry_run=args.dry_run or settings.dry_run)
    print(f"Adjusted {len(deltas)} source weights:")
    for name, delta in sorted(deltas.items(), key=lambda kv: kv[1]):
        sign = "+" if delta > 0 else ""
        print(f"  {sign}{delta}  {name}")


if __name__ == "__main__":
    main()
