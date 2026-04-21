"""Loop 6: Open-rate drift alerting.

If 7-day rolling open rate drops > 15% from the 30-day baseline, file an
emergency GitHub Issue with Claude's diagnosis.

Diagnosis prompt analyzes:
  - Subject line patterns in the last 7 days vs the prior 30
  - Send time consistency
  - Story count / format drift
  - Sender domain reputation hints (bounce rate, unsub rate trends)

This loop is the safety net for everything else. It should run nightly.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .. import _llm, analytics, github_alerts
from ..config import settings

log = logging.getLogger(__name__)

DRIFT_THRESHOLD = 0.15  # 15% relative drop


DIAGNOSIS_SYSTEM = """You are diagnosing an open-rate drop for Dealer Ops Daily.

You receive: 7-day rolling stats, 30-day baseline stats, and metadata about the last 14 issues (subject lines, story counts, sections used).

Hypothesize the most likely 1-2 causes. Be specific — not "deliverability issues" but "subject lines have all started with 'BREAKING:' which spam-filters down-rank".

Return ONLY a JSON object:
{
  "severity": "low|medium|high",
  "primary_hypothesis": "<1-2 sentences>",
  "secondary_hypothesis": "<1-2 sentences, or null>",
  "specific_evidence": ["<bullet 1>", "<bullet 2>"],
  "recommended_action": "<concrete next step the operator can take in <30 min>"
}
"""


@dataclass
class DriftStatus:
    drift_detected: bool
    rolling_7d: float
    baseline_30d: float
    relative_drop: float
    reason: str


def _compute_7d_baseline() -> float:
    """Average open rate over the last 7 days."""
    records = []
    if not (settings.data_dir / "analytics.json").exists():
        return 0.0
    raw = json.loads((settings.data_dir / "analytics.json").read_text(encoding="utf-8"))
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    records = [r for r in raw if r.get("issue_date", "") >= cutoff]
    if not records:
        return 0.0
    return sum(r.get("open_rate", 0) for r in records) / len(records)


def check() -> DriftStatus:
    rolling_7 = _compute_7d_baseline()
    baseline_30 = analytics.rolling_baseline_30d().get("avg_open_rate", 0.0)

    if rolling_7 == 0 or baseline_30 == 0:
        return DriftStatus(
            drift_detected=False, rolling_7d=rolling_7, baseline_30d=baseline_30,
            relative_drop=0.0, reason="insufficient_data",
        )

    drop = (baseline_30 - rolling_7) / baseline_30
    if drop > DRIFT_THRESHOLD:
        return DriftStatus(
            drift_detected=True, rolling_7d=rolling_7, baseline_30d=baseline_30,
            relative_drop=drop, reason=f"7d={rolling_7:.1%} vs 30d={baseline_30:.1%} ({drop:+.1%} drop)",
        )
    return DriftStatus(
        drift_detected=False, rolling_7d=rolling_7, baseline_30d=baseline_30,
        relative_drop=drop, reason="within_threshold",
    )


def _gather_issue_metadata(window_days: int = 14) -> list[dict]:
    """Collect last 14 issues' metadata for the analyzer."""
    issue_dir = settings.issue_output_dir
    if not issue_dir.exists():
        return []
    out = []
    for path in sorted(issue_dir.glob("*.json"))[-window_days:]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append({
            "issue_date": path.stem,
            "subject_a": data.get("subject_a"),
            "subject_b": data.get("subject_b"),
            "subject_c": data.get("subject_c"),
            "story_count": data.get("metadata", {}).get("story_count"),
            "sections": [s.get("name") for s in data.get("sections", [])],
        })
    return out


def diagnose(status: DriftStatus, *, dry_run: bool = False) -> dict[str, Any]:
    if dry_run or not settings.anthropic_api_key:
        return {
            "severity": "medium" if status.relative_drop > 0.20 else "low",
            "primary_hypothesis": "Possible subject-line pattern fatigue or reduced novelty in source pool. Inspect last 7 days of subject lines for repeated structural patterns.",
            "secondary_hypothesis": "Send-time drift; verify scheduled_at in audits is consistent.",
            "specific_evidence": [f"7-day open rate: {status.rolling_7d:.1%}", f"30-day baseline: {status.baseline_30d:.1%}"],
            "recommended_action": "Review issues/<last-7-days>.json subject lines; if patterns repeat, manually rotate Loop 2 rules.",
        }
    user = json.dumps({
        "rolling_7d_open_rate": status.rolling_7d,
        "baseline_30d_open_rate": status.baseline_30d,
        "relative_drop": status.relative_drop,
        "recent_issues": _gather_issue_metadata(),
    }, indent=2, default=str)
    return _llm.call_json(system=DIAGNOSIS_SYSTEM, user=user)


def run(*, dry_run: bool = False) -> dict[str, Any]:
    status = check()
    if not status.drift_detected:
        log.info("No drift detected (%s)", status.reason)
        return {"alerted": False, "status": vars(status)}

    diag = diagnose(status, dry_run=dry_run)

    body = (
        f"**Severity:** {diag.get('severity')}\n\n"
        f"**Drop:** 7-day open rate {status.rolling_7d:.1%} vs 30-day baseline {status.baseline_30d:.1%} "
        f"({status.relative_drop:+.1%})\n\n"
        f"## Primary hypothesis\n{diag.get('primary_hypothesis')}\n\n"
        f"## Secondary hypothesis\n{diag.get('secondary_hypothesis') or '(none)'}\n\n"
        f"## Evidence\n" + "\n".join(f"- {e}" for e in diag.get("specific_evidence", []))
        + f"\n\n## Recommended action\n{diag.get('recommended_action')}\n"
    )

    if dry_run:
        log.info("DRY RUN — would file alert:\n%s", body)
        return {"alerted": False, "status": vars(status), "diagnosis": diag, "would_file": True}

    url = github_alerts.open_issue(
        title=f"🚨 Open-rate drift detected — {status.relative_drop:+.0%} vs baseline",
        body=body,
        labels=["loop-open-rate-drift", "alert", "needs-triage"],
    )
    return {"alerted": True, "status": vars(status), "diagnosis": diag, "issue_url": url}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = run(dry_run=args.dry_run or settings.dry_run)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
