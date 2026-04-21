"""Loop 2: Subject line optimization.

Weekly: pull last 30 days of (subject_a, subject_b, subject_c, winner_text, open_rate)
from analytics. Ask Claude to identify winning patterns (length, format, punctuation,
emoji usage, leading word). Write the findings to prompts/subject-rules-vN.md.

The drafter's system prompt references prompts/subject-rules-current.md (a symlink
or copied file). Once Claude proposes new rules, we either:
  - Auto-apply if the change is small (e.g. "shorten to 35-50 chars")
  - Open a PR for operator review if the change is structural

Self-test: dry-run analyzes a fixture of subject performance.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .. import _llm, github_alerts
from ..config import settings

log = logging.getLogger(__name__)


SUBJECT_HISTORY_FILE = settings.data_dir / "subject_history.jsonl"
RULES_FILE = settings.system_prompt_file.parent / "subject-rules-current.md"


SUBJECT_ANALYZER_SYSTEM = """You are analyzing subject-line A/B test results for Dealer Ops Daily, a daily newsletter for U.S. auto dealership operators.

You receive a JSON array of last-30-day subject test results: each row has the three variants tested, which won, and the open rate of the winner.

Identify the patterns that win. Examine:
  - Length (chars, words)
  - Lead word type (verb, number, name)
  - Punctuation use (colons, em-dashes, question marks)
  - Emoji presence (any?)
  - Specificity (named entity vs generic)
  - Curiosity gap vs concrete promise

Return ONLY a JSON object:
{
  "summary": "<1-paragraph summary of the dominant winning pattern>",
  "rules": [
    "<actionable rule 1, e.g. 'Lead with a number when one is available; numbers won 7/10 head-to-head tests'>",
    "<actionable rule 2>",
    "..."
  ],
  "patterns_to_avoid": [
    "<pattern that consistently lost>"
  ],
  "confidence": "low|medium|high",
  "recommend_apply": true/false,
  "reasoning": "<1 sentence — why or why not auto-apply>"
}
"""


def record_subject_result(
    issue_date: date,
    subject_a: str,
    subject_b: str,
    subject_c: str,
    winner_idx: int,  # 0, 1, or 2
    winner_open_rate: float,
) -> None:
    """Called from analytics.py after beehiiv reports the A/B winner."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "issue_date": issue_date.isoformat(),
        "subject_a": subject_a,
        "subject_b": subject_b,
        "subject_c": subject_c,
        "winner_idx": winner_idx,
        "winner_text": [subject_a, subject_b, subject_c][winner_idx],
        "winner_open_rate": winner_open_rate,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    with SUBJECT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _load_history(window_days: int = 30) -> list[dict]:
    if not SUBJECT_HISTORY_FILE.exists():
        return []
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()
    out: list[dict] = []
    with SUBJECT_HISTORY_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("issue_date", "") >= cutoff:
                out.append(row)
    return out


def _analyze_dry(history: list[dict]) -> dict[str, Any]:
    """Heuristic dry-run analyzer: count winners by length and emoji."""
    if not history:
        return {"summary": "No data", "rules": [], "patterns_to_avoid": [], "confidence": "low", "recommend_apply": False, "reasoning": "no history"}
    lengths = [len(r["winner_text"]) for r in history]
    avg_len = sum(lengths) / len(lengths)
    emoji_winners = sum(1 for r in history if any(ord(c) > 0x2700 for c in r["winner_text"]))
    return {
        "summary": f"Average winning subject length: {avg_len:.0f} chars across {len(history)} tests. Emoji-using subjects won {emoji_winners}/{len(history)}.",
        "rules": [
            f"Target subject length around {int(avg_len)} chars (±5)",
            "Emoji usage: " + ("preferred" if emoji_winners > len(history) / 2 else "avoid"),
        ],
        "patterns_to_avoid": ["clickbait", "ALL CAPS"],
        "confidence": "medium" if len(history) >= 20 else "low",
        "recommend_apply": len(history) >= 20,
        "reasoning": "deterministic heuristic — Claude analysis recommended once data is sufficient",
    }


def analyze_and_apply(*, dry_run: bool = False) -> dict[str, Any]:
    history = _load_history()
    if not history:
        log.info("No subject-line history yet")
        return {"applied": False, "reason": "no_data"}

    if dry_run or not settings.anthropic_api_key:
        analysis = _analyze_dry(history)
    else:
        user = json.dumps({"history": history}, indent=2)
        analysis = _llm.call_json(system=SUBJECT_ANALYZER_SYSTEM, user=user)

    if not analysis.get("recommend_apply"):
        log.info("Analysis says don't apply yet (confidence=%s)", analysis.get("confidence"))
        return {"applied": False, "analysis": analysis}

    # Persist the new rules
    today = date.today().isoformat()
    body = (
        f"# Subject-line rules — auto-generated {today}\n\n"
        f"**Confidence:** {analysis.get('confidence')}\n"
        f"**Based on:** {len(history)} subject tests in the trailing 30 days\n\n"
        f"## Summary\n\n{analysis.get('summary', '')}\n\n"
        f"## Rules to apply (drafter prompt should reference these)\n\n"
        + "\n".join(f"- {r}" for r in analysis.get("rules", []))
        + "\n\n## Patterns to avoid\n\n"
        + "\n".join(f"- {r}" for r in analysis.get("patterns_to_avoid", []))
        + "\n"
    )

    if dry_run:
        log.info("DRY RUN: would write %s with %d rules", RULES_FILE, len(analysis.get("rules", [])))
        return {"applied": False, "analysis": analysis, "would_write": str(RULES_FILE)}

    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(body, encoding="utf-8")
    log.info("Wrote new subject rules to %s", RULES_FILE)

    github_alerts.open_issue(
        title=f"🎯 Subject-line rules auto-updated ({today})",
        body=f"Loop 2 ran and updated `{RULES_FILE.name}`.\n\n{analysis.get('reasoning', '')}\n\n```\n{body[:1200]}\n```",
        labels=["loop-subject-lines"],
    )
    return {"applied": True, "analysis": analysis}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = analyze_and_apply(dry_run=args.dry_run or settings.dry_run)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
