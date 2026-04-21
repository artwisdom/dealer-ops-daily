"""Loop 3: Content format evolution.

Monthly: Claude reviews the highest-engagement issues from the last 30 days and
hypothesizes what *structural* format changes to try (e.g. "issues with a 3-bullet
hook are opening 12% better than single-paragraph openers").

Output: opens a draft PR-style file at prompts/proposed-format-vN.md describing the
proposed change. Operator approves by renaming/copying to system-prompt-v(N+1).md.

(Note: real PR opening requires a GitHub bot account or PAT — outside Phase 4 scope.
The loop produces the file + GitHub Issue, which is functionally equivalent for
the operator's review workflow.)

Self-test: dry-run runs the analysis on a synthetic engagement set.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from .. import _llm, github_alerts
from ..config import settings

log = logging.getLogger(__name__)


FORMAT_ANALYZER_SYSTEM = """You are evaluating Dealer Ops Daily issue formats for a monthly content-format experiment.

You receive a JSON payload with: a sample of the last 30 days' issue metadata (title, cold open, story count, sections used, tool of day used) and per-issue analytics (open rate, click rate).

Your task: identify ONE specific structural change worth A/B testing next month. Examples of "structural":
  - Move "Tool of the day" from end to middle
  - Add a "Read time" badge at the top
  - Replace cold-open with a 3-bullet hook
  - Add a "Yesterday's biggest miss" section

Do NOT propose:
  - Editorial-tone changes (those go through Loop 2)
  - Source-priority changes (those are Loop 1)
  - Affiliate changes (those are Loop 4)

Return ONLY a JSON object:
{
  "proposed_change": "<1-line summary>",
  "rationale": "<2-3 sentences citing the specific data pattern>",
  "evidence_strength": "weak|moderate|strong",
  "implementation_diff": "<exact text addition or modification to system-prompt-v1.md, in markdown>",
  "rollout_plan": "<how to test — e.g. 'apply Mon/Wed/Fri for 2 weeks, compare open rates'>"
}
"""


def _load_recent_issues(window_days: int = 30) -> list[dict[str, Any]]:
    """Read recent issue audit JSONs + matching analytics for the analyzer."""
    issue_dir = settings.issue_output_dir
    if not issue_dir.exists():
        return []
    from .. import analytics
    out: list[dict[str, Any]] = []
    for path in sorted(issue_dir.glob("*.json"))[-window_days:]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append({
            "issue_date": path.stem,
            "title": data.get("issue_title"),
            "cold_open": data.get("cold_open"),
            "story_count": data.get("metadata", {}).get("story_count"),
            "sections": [s.get("name") for s in data.get("sections", [])],
            "tool_of_day": data.get("tool_of_day", {}).get("product_id"),
            "word_count": data.get("metadata", {}).get("word_count_estimate"),
        })
    # Splice in per-issue analytics
    perf_by_date = {}
    if (settings.data_dir / "analytics.json").exists():
        for rec in json.loads((settings.data_dir / "analytics.json").read_text(encoding="utf-8")):
            perf_by_date[rec["issue_date"]] = {
                "open_rate": rec.get("open_rate"),
                "click_rate": rec.get("click_rate"),
            }
    for issue in out:
        issue["performance"] = perf_by_date.get(issue["issue_date"], {})
    return out


def _analyze_dry(issues: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristic dry-run: if avg story count > 6, propose tightening; otherwise no-op."""
    if not issues:
        return {
            "proposed_change": "(no data yet)",
            "rationale": "Not enough issues published.",
            "evidence_strength": "weak",
            "implementation_diff": "",
            "rollout_plan": "wait for ≥10 issues",
        }
    avg_count = sum(i.get("story_count") or 0 for i in issues) / len(issues)
    if avg_count > 6.5:
        return {
            "proposed_change": "Cap story count at 5 per issue",
            "rationale": f"Average story count is {avg_count:.1f}; readers report 5-min read time but issues exceed it.",
            "evidence_strength": "moderate",
            "implementation_diff": "Update STORY STRUCTURE section: change 'Total story count target: 4–6' to 'Total story count target: 4–5 (hard cap 5)'.",
            "rollout_plan": "Apply for 2 weeks; revert if open rate drops >5%",
        }
    return {
        "proposed_change": "(no change recommended this cycle)",
        "rationale": f"Average story count is {avg_count:.1f}; format is within target.",
        "evidence_strength": "moderate",
        "implementation_diff": "",
        "rollout_plan": "wait until next monthly cycle",
    }


def analyze_and_propose(*, dry_run: bool = False) -> dict[str, Any]:
    issues = _load_recent_issues()
    if not issues:
        log.info("No issue audit data yet")
        return {"proposed": False, "reason": "no_data"}

    if dry_run or not settings.anthropic_api_key:
        proposal = _analyze_dry(issues)
    else:
        user = json.dumps({"issues": issues}, indent=2, default=str)
        proposal = _llm.call_json(system=FORMAT_ANALYZER_SYSTEM, user=user)

    if not proposal.get("implementation_diff"):
        log.info("No format change recommended this cycle")
        return {"proposed": False, "proposal": proposal}

    today = date.today()
    out_path = settings.system_prompt_file.parent / f"proposed-format-{today:%Y-%m}.md"
    body = (
        f"# Proposed format change — {today}\n\n"
        f"**Strength:** {proposal.get('evidence_strength')}\n\n"
        f"## Proposal\n\n{proposal.get('proposed_change')}\n\n"
        f"## Rationale\n\n{proposal.get('rationale')}\n\n"
        f"## Implementation diff (apply to current system prompt)\n\n```\n{proposal.get('implementation_diff')}\n```\n\n"
        f"## Rollout plan\n\n{proposal.get('rollout_plan')}\n\n"
        f"---\n\n"
        f"To accept: edit `prompts/system-prompt-v1.md` per the diff above, increment the version line, "
        f"and delete this proposal file. To reject: just delete this file.\n"
    )

    if dry_run:
        log.info("DRY RUN: would write %s", out_path)
        return {"proposed": True, "would_write": str(out_path), "proposal": proposal}

    out_path.write_text(body, encoding="utf-8")
    github_alerts.open_issue(
        title=f"🧪 Format proposal — {proposal.get('proposed_change')}",
        body=f"Loop 3 (content format evolution) proposed a change.\n\nFile: `{out_path}`\n\n{proposal.get('rationale')}\n\n**Approve:** edit `prompts/system-prompt-v1.md` per the diff in the file, then delete the proposal file.",
        labels=["loop-format-evolution", "needs-review"],
    )
    return {"proposed": True, "wrote": str(out_path), "proposal": proposal}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = analyze_and_propose(dry_run=args.dry_run or settings.dry_run)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
