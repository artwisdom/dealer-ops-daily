# Next steps when you return

**Last left off:** 2026-04-20, code pushed to GitHub. Sleeping. Wake up to this list.

---

## State of play

✅ **Done** — code is live at https://github.com/artwisdom/dealer-ops-daily
✅ Phases 0–5 complete: pipeline, growth automation, 6 self-improvement loops, Sunday Opus meta-issue, launch toolkit
✅ 60/60 tests pass, all offline-runnable
✅ beehiiv publication exists, Welcome Email is on, address + sender are set
✅ git push works from this machine without extra auth setup

⏳ **Blocked on you** — needs your inputs / payment / credential creation

---

## The 6 remaining steps, in order

### 1. Verify the reply-to email (~30 seconds)

Check `Michael@AndromedaKinship.com` inbox for a verification email from beehiiv. Click the link. Until done, replies still go to your old Gmail.

### 2. Upgrade beehiiv to Scale plan (~3 minutes — needs your card)

URL: https://app.beehiiv.com → Settings → Workspace Settings → Billing & Plan → Scale.
Cost: ~$43–99/mo. Required for: Boosts, Ad Network, Automations, Referral program, full API.

Why now: per the Day-1 Scale decision (PHASE-1-VERIFICATION.md). The whole growth stack is gated to this plan.

### 3. Create the API keys (~5 minutes)

Two required, two optional:

| Key | Where | Required? |
|---|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → Settings → API Keys → Create Key | **yes** |
| `BEEHIIV_API_KEY` | beehiiv → Settings → Workspace Settings → API → Create API Key | **yes** |
| `BEEHIIV_PUBLICATION_ID` | beehiiv → Settings → API → Publications endpoint, OR the URL of your dashboard | **yes** |
| `REPLICATE_API_TOKEN` | https://replicate.com/account/api-tokens | optional (Pexels fallback exists) |
| `PEXELS_API_KEY` | https://www.pexels.com/api/new/ | optional |

Naming convention: name them `dealer-ops-daily-prod` so you can audit later.

### 4. Add the keys to GitHub Secrets (~2 minutes)

URL: https://github.com/artwisdom/dealer-ops-daily/settings/secrets/actions

Click "New repository secret" for each. Names must match the table above exactly.

### 5. Run preflight + ship the first live issue (~5 minutes)

URL: https://github.com/artwisdom/dealer-ops-daily/actions

a. **"Launch (preflight + monitor + postmortem)"** workflow → Run workflow → step: `preflight` → Run.
   - Wait ~2 min for the green check. If red, click in to see which check failed (probably a missing secret).

b. **"Daily issue"** workflow → Run workflow → toggle dry_run: ✅ ON → Run.
   - Read the audit at `issues/<today>.md` in the repo. Confirm editorially correct.

c. **"Daily issue"** workflow → Run workflow → toggle dry_run: ❌ OFF → Run.
   - Pipeline POSTs to beehiiv as a draft, schedules send for 06:00 ET tomorrow.

d. Open beehiiv → drafts → final review → leave it scheduled. The send fires automatically.

e. **"Launch (preflight + monitor + postmortem)"** workflow → step: `mark-launched` → Run.
   - This starts the launch-monitor.yml nightly capture for the next 14 days.

### 6. Day 7 post-mortem (~3 minutes — set a calendar reminder)

URL: https://github.com/artwisdom/dealer-ops-daily/actions

**"Launch (preflight + monitor + postmortem)"** workflow → step: `postmortem` → Run.

Files a GitHub Issue with verdict (success / mixed / needs intervention), what worked, what didn't, what the loops auto-adjusted, week-2 recommendations.

---

## If something breaks

- **Pipeline fails on a real run** → it auto-files a GitHub Issue tagged `pipeline-failure`. Check Actions tab for the run log.
- **Open rate drops >15% in week 2+** → Loop 6 (open-rate drift) files an issue with Claude's diagnosis.
- **Ad Network not auto-submitted at 1K subs / 20% open rate** → Loop runs daily at 23:31 UTC; check `data/state.json` for the timestamp.
- **An affiliate keeps appearing despite low CTR** → Loop 4 needs a candidate in `data/affiliate_watchlist.json` to swap in. If empty, it keeps the underperformer and files a request-for-watchlist issue.

---

## Per-week maintenance after launch

The promised 30 min/week breakdown:

- **Sunday morning** (5 min): read the auto-published Sunday meta-issue
- **Sunday morning** (15 min): check open issues in the repo — any `needs-triage` or `needs-review` labels need a glance
- **Sunday morning** (10 min): one Reddit post, one LinkedIn post (manual per spec amendments — these can't be safely automated)

Anything else creeping in beyond that = bug in the pipeline. File a `pipeline-debt` issue.

---

## Where to find things

- **Project root:** `C:/Users/dube5/Desktop/Andromeda Kinship/Claude Code Project Files/Automated Newsletter/`
- **Original spec:** [02-automated-newsletter-beehiiv.md](02-automated-newsletter-beehiiv.md)
- **Phase 0 research:** [research/00-summary.md](research/00-summary.md) (start here for niche/competitor/sources/monetization context)
- **Phase 1 setup record:** [PHASE-1-VERIFICATION.md](PHASE-1-VERIFICATION.md)
- **Setup walkthrough:** [SETUP.md](SETUP.md)
- **Codebase overview:** [README.md](README.md)
- **System prompts (read these to tune editorial voice):**
  - [prompts/system-prompt-v1.md](prompts/system-prompt-v1.md) (daily, Sonnet 4.6)
  - [prompts/weekly-meta-prompt-v1.md](prompts/weekly-meta-prompt-v1.md) (Sunday, Opus 4.6)
- **Source list to audit/edit:** [sources.yaml](sources.yaml)
- **Affiliate inventory:** [data/affiliates.json](data/affiliates.json)

---

## Conversation context if you start a new chat

Memory at `C:/Users/dube5/.claude/projects/C--Users-dube5-Desktop-Andromeda-Kinship-Claude-Code-Project-Files-Automated-Newsletter/memory/` captures:
- User profile (you), runtime decision, browser-setup preference
- Project state, spec amendments (9 findings overriding original PROJECT.md), service references

A new Claude session in this directory will load that context automatically.

Sleep well.
