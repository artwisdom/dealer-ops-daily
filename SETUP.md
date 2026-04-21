# Setup — getting from "code in a folder" to "live daily issues"

This walks you (Michael) through everything between Phase 2 (code complete) and Phase 5 (first live send).
Sequence matters — do them in order.

---

## 0. Verify the code works on your machine

This step requires nothing external. Confirms the pipeline scaffolding is intact.

```bash
cd "C:/Users/dube5/Desktop/Andromeda Kinship/Claude Code Project Files/Automated Newsletter"
pip install -r requirements.txt
python -m pipeline.ingest --seed-fixture     # writes fixtures/candidates.json
python -m pipeline.run --dry-run              # full pipeline, no API costs
python -m pytest tests/                       # all 17 tests should pass
```

If the dry-run prints a JSON summary with `"dry_run": true` and writes `issues/<today>.md`, you're good.

---

## 1. Push the code to your GitHub repo

The repo at `https://github.com/artwisdom/dealer-ops-daily` currently has only the README we created in Phase 1.
Push everything else:

```bash
cd "C:/Users/dube5/Desktop/Andromeda Kinship/Claude Code Project Files/Automated Newsletter"

git init
git remote add origin https://github.com/artwisdom/dealer-ops-daily.git
git fetch origin
git checkout -b main --track origin/main 2>/dev/null || git checkout main

# Stage everything that isn't gitignored (.env stays out, etc.)
git add .
git status                                    # SANITY CHECK: review what's about to be committed
git commit -m "Phase 2: pipeline scaffolding + tests"

git push -u origin main
```

Two things to double-check before pushing:
- `git status` does NOT show a `.env` file (it's gitignored, but verify)
- `git status` does NOT show anything under `data/analytics.json` containing real subscriber data (only the empty default)

---

## 2. Obtain the API keys

Each one in priority order. You can launch in dry-run mode without any of these — they're for going live.

### A. Anthropic API key (required)

1. Go to https://console.anthropic.com/
2. Settings → API Keys → Create Key
3. Name it `dealer-ops-daily-prod`
4. Copy the value (starts with `sk-ant-...`) — you'll add it as a GitHub secret in step 3

Cost expectation: ~$30-80/mo at our daily-issue volume on Sonnet 4.6.

### B. beehiiv API key + publication ID (required)

1. **Upgrade to Scale plan first** — per our Day-1 Scale decision. beehiiv → Settings → Workspace Settings → Billing & Plan → Scale.
2. beehiiv → Settings → Workspace Settings → API → Create API Key. Name it `pipeline`.
3. Copy the API key.
4. For publication ID: it's in the URL when you visit your dashboard, or via Settings → API → "Publications" call. Format: `pub_xxxxxxxxxxxxx`.

### C. Replicate API token (optional — Flux hero images)

1. https://replicate.com/account/api-tokens
2. Create token, copy.
3. Cost: ~$0.003/image, so ~$0.10/month for daily issues.

Without this, the pipeline falls back to Pexels stock photos (free) or a static placeholder.

### D. Pexels API key (optional — fallback hero images)

1. https://www.pexels.com/api/new/ → free tier, 200 req/hr.
2. Copy the key.

### E. Supabase (optional — affiliate inventory)

Skip for Phase 2. The local `data/affiliates.json` works fine for one affiliate (DealerIntel).
Only set this up when you have ≥5 affiliates and want a managed UI.

### F. Google Sheets (optional — analytics)

Skip for Phase 2. Local `data/analytics.json` works. Set up later if you want to share metrics outside the repo.

---

## 3. Add the secrets to GitHub

```
Repo → Settings → Secrets and variables → Actions → New repository secret
```

Add each of:

| Secret name | Required | Source |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | from step 2.A |
| `BEEHIIV_API_KEY` | yes | from step 2.B |
| `BEEHIIV_PUBLICATION_ID` | yes | from step 2.B |
| `REPLICATE_API_TOKEN` | no | from step 2.C |
| `PEXELS_API_KEY` | no | from step 2.D |
| `SUPABASE_URL` | no | skip Phase 2 |
| `SUPABASE_SERVICE_KEY` | no | skip Phase 2 |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | no | skip Phase 2 |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | no | skip Phase 2 |
| `SPARKLOOP_API_KEY` | no | only when you turn on paid acquisition (Phase 3 — month 4+) |

After adding, the daily workflow will pick them up on the next scheduled or manual run.

### Phase 3 + 4 workflows that auto-arm once secrets are in place

| Workflow | Cron | What it needs to be useful |
|---|---|---|
| `daily-boosts.yml` | 04:47 UTC daily | Scale plan + BEEHIIV_API_KEY (uses fixture offers when neither) |
| `daily-thresholds.yml` | 23:31 UTC daily | BEEHIIV_API_KEY for live subs; SPARKLOOP_API_KEY for paid acquisition eval |
| `weekly-loops.yml` | 14:17 UTC Sun | ANTHROPIC_API_KEY for Loop 2 analysis (Loops 1+4 work without keys) |
| `monthly-loops.yml` | 13:23 UTC 1st | ANTHROPIC_API_KEY for Loops 3 + sponsors + outreach |

All loops degrade gracefully — they print a "no data yet" or "skipping (no key)" message instead of failing.

---

## 4. Manually trigger a test run on GitHub

Before relying on the cron, prove it works in CI:

1. Repo → Actions → "Daily issue" workflow → Run workflow
2. Toggle "Run in dry mode" → ON
3. Click Run workflow.

Within ~3 minutes you should see a green check. If red, click into the run and read the failure.

Common first-run issues:
- Missing secrets → fix in step 3
- Python version mismatch → workflow pins 3.12; ensure your local matches in your `.env`
- beehiiv API 401 → API key wrong or not on Scale plan

---

## 5. First real send (Phase 5 — launch day)

Don't auto-publish your first live issue. Walk it through using the launch toolkit:

```
# Step 1 — preflight (verifies every component, exits non-zero on any blocker)
# Run via GitHub Actions: workflow "Launch (preflight + monitor + postmortem)" → step: preflight
# Or locally: python -m pipeline.launch preflight

# Step 2 — manually run a dry-run end-to-end and review issues/<today>.{md,json}
python -m pipeline.run --dry-run

# Step 3 — when the dry-run looks editorially correct, run live
python -m pipeline.run

# Step 4 — open beehiiv → drafts, review one more time, send fires at 06:00 ET tomorrow

# Step 5 — record the launch (idempotent)
# Via GitHub Actions: launch.yml → step: mark-launched
# Or locally: python -m pipeline.launch mark-launched

# Step 6 — for the next 7 days, launch-monitor.yml runs nightly and captures metrics
# (auto-disables after day 14; no action needed)

# Step 7 — at day 7+, run the post-mortem
# Via GitHub Actions: launch.yml → step: postmortem
# Or locally: python -m pipeline.launch postmortem
# Files a GitHub Issue with verdict + week-2 recommendations.
```

## 6. Sunday meta-issue

Once daily issues are running, the Sunday Opus 4.6 meta-issue auto-publishes via
`weekly-meta-issue.yml` (14:30 UTC Sundays). Its prompt is at
`prompts/weekly-meta-prompt-v1.md` — adjust if you want a different format.

---

## 6. Ongoing maintenance — your 30 min/week

Sunday morning ritual once the pipeline is stable:

1. Read [PROJECT.md](02-automated-newsletter-beehiiv.md) §Sunday ritual for the full list (5 min)
2. Glance at the most recent commit history → did all 7 issues ship cleanly? (2 min)
3. Open any GitHub Issue with the `pipeline-failure` or `needs-triage` label (15 min)
4. Open `data/analytics.json` (or your Sheets dashboard) → eyeball open rate trend (5 min)
5. Approve / merge any auto-opened PRs from the self-improvement loops (next phase) (5 min)

If anything else creeps in beyond 30 min/week → it's a bug in the pipeline. File a Phase 4 issue.

---

## Appendix — Local development tips

- Always use `--dry-run` for any code changes; only switch to live when ready to publish
- `.env` is gitignored; copy `.env.example` to `.env` and fill in real values for local live testing
- Tests must pass before any push: `python -m pytest tests/`
- The 8 sample candidates in `fixtures/candidates.json` are designed to mimic a typical day's news — adjust seed_fixture() in `pipeline/ingest.py` if you want to test edge cases
- To test the Claude-powered (non-dry) ranker locally, set `ANTHROPIC_API_KEY` in `.env` and run `python -m pipeline.rank` (without `--dry-run`)
