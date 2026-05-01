# Proposed format change — 2026-05-01

**Strength:** weak

## Proposal

Add a 'Read time' badge at the top of each issue, directly below the title

## Rationale

The sole issue in the sample ('week of April 20') logged 0 clicks despite a 850-word body, suggesting readers may be abandoning before engaging — a common pattern when perceived time-cost is unclear at the point of open. A visible read-time signal (e.g., '⏱ 3 min read') immediately below the title reduces that friction and has documented lift in newsletter CTR benchmarks. While one issue is insufficient to confirm causation, the 0-click outcome on a multi-section issue makes this the highest-leverage low-risk structural intervention to isolate.

## Implementation diff (apply to current system prompt)

```
```markdown
## Section Order — Top of Issue

### CHANGE (v1 → v2)

**Before:**
```
## {{ issue_title }}
{{ cold_open }}
```

**After:**
```
## {{ issue_title }}
> ⏱ {{ estimated_read_minutes }} min read · {{ story_count }} stories

{{ cold_open }}
```

### Implementation Note
- `estimated_read_minutes` = `round(word_count / 200)` (calculated at render time)
- Badge renders as a blockquote line so it is visually distinct but not a full section header
- No other section order changes in this variant
```
```

## Rollout plan

Apply the read-time badge to Monday, Wednesday, and Friday issues for 4 consecutive weeks (8 treated issues). Leave Tuesday and Thursday issues as control (no badge). Compare average click rate between treated and control groups at end of period. Require a minimum of 200 opens per cohort before drawing conclusions; if volume is below that threshold, extend rollout by two additional weeks before evaluating.

---

To accept: edit `prompts/system-prompt-v1.md` per the diff above, increment the version line, and delete this proposal file. To reject: just delete this file.
