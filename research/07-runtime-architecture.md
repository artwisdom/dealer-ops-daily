# 07 — Runtime & Cron Architecture for the Daily Pipeline

**Decision target:** Where does the daily 05:30 UTC beehiiv pipeline execute? The reference spec (`02-automated-newsletter-beehiiv.md`) assumes GitHub Actions. The user has flagged "Claude Routines" as a possible alternative and wants a defensible comparison before committing.

**Operator profile:** Solo non-DevOps user on Windows 11, no existing API keys, time budget < 30 min/week of upkeep, runtime needs ~5–10 min, must persist analytics state across runs, must call Claude API + Replicate + beehiiv API.

---

## 1. What "Claude Routines" actually is in April 2026

This was the most ambiguous item in the brief, so it gets resolved first.

There are **three distinct "scheduled Claude" products** as of April 2026, and they are not interchangeable:

| Product | What it is | Where it runs | Survives laptop closed? |
|---|---|---|---|
| **Claude Code Routines** | Cloud-hosted Claude Code sessions on a cron / API / GitHub-event trigger. Research preview launched April 2026. | Anthropic-managed cloud infra. | Yes |
| **Claude Code Scheduled Tasks** (desktop / `/loop`) | Local recurring prompt run by the desktop app or CLI session. | User's machine. | **No** — only fires while desktop app is open and machine awake |
| **Claude Cowork scheduled tasks** | In-app "run this prompt every weekday" feature inside claude.ai/Cowork. | Anthropic cloud, but limited tool surface. | Yes |

The relevant option for a daily unattended newsletter is **Claude Code Routines** ("Routines" hereafter). Per the official docs ([code.claude.com/docs/en/routines](https://code.claude.com/docs/en/routines)):

- Available on Pro / Max / Team / Enterprise with Claude Code on the web enabled.
- **Daily run cap: 5 (Pro) / 15 (Max) / 25 (Team & Enterprise)** per account ([9to5Mac coverage](https://9to5mac.com/2026/04/14/anthropic-adds-repeatable-routines-feature-to-claude-code-heres-how-it-works/)).
- **Minimum cron interval: 1 hour.**
- A routine = `prompt + repos + connectors + environment + triggers`. It clones a GitHub repo at the start of every run, can call shell commands, MCP connectors, and any HTTPS endpoint allowed by the environment's network settings.
- State persistence: the cloned repo. Claude can only push to `claude/`-prefixed branches unless you grant unrestricted push.
- **Status: research preview.** API surface ships behind `experimental-cc-routine-2026-04-01` beta header. Anthropic explicitly warns "behavior, limits, and the API surface may change."

This is genuinely a cron-equivalent product, but it is brand new, capped, and carries deprecation risk.

---

## 2. The five options, side-by-side

### Option A — GitHub Actions (the spec's assumption)

- **What:** YAML workflow in a repo, triggered by `schedule:` cron.
- **Cost:** 2,000 free minutes/month on private repos for Pro accounts; **public repos are free with no minute cap**. Pricing dropped up to 39% in January 2026 ([GitHub changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)).
- **Pipeline fit:** Excellent. Standard Python / Node script with `requests` to RSS, Anthropic SDK, Replicate SDK, beehiiv API.
- **State persistence:** Commit JSON/SQLite back to the repo, or use a free Supabase / Neon / Turso DB. Both are well-trodden.
- **AI step:** `ANTHROPIC_API_KEY` stored as a GitHub Actions Secret, used by the script.
- **Failure handling:** Built-in re-run UI, `if: failure()` step for email/Slack alerts, native retry. Logs retained 90 days.
- **Setup friction:** Medium. Requires creating a repo, writing YAML, learning Actions secret management. ~2 hours one-time.
- **Risks:** GitHub-scheduled cron is famously imprecise — workflows can be delayed 15–60 minutes during heavy load, and silent skips have been reported during peak hours. Workflows on private repos auto-disable after 60 days of repo inactivity (mitigation: nightly bot commit).

### Option B — Claude Code Routines

- **What:** See section 1.
- **Cost:** Bundled with Pro ($20/mo) / Max ($100–200/mo) subscription. Counts against subscription usage.
- **Pipeline fit:** Workable but awkward. Routines expect "agentic work in a repo," not a deterministic ETL job. The prompt would need to instruct Claude to fetch RSS, score, draft, call Replicate, POST to beehiiv. Each run pays the LLM tax for code that does not need an LLM (RSS fetch, beehiiv POST).
- **State persistence:** Connected GitHub repo. Routine commits the analytics CSV/JSON each run. Works.
- **AI step:** Native — the routine *is* a Claude session.
- **Failure handling:** Run shows in claude.ai session list; no native retry; no alerting hooks documented in preview.
- **Setup friction:** Low — point-and-click at claude.ai/code/routines, paste prompt, link repo, set schedule. ~30 min.
- **Risks:** **High.** Research preview, daily caps (5/day on Pro is fine for a daily newsletter but leaves no headroom for ad-hoc runs), 1-hour minimum cron, beta API headers will rev, pricing model could change. No SLA. Anthropic could pull or repackage the feature.

### Option C — Local Windows 11 + Task Scheduler

- **What:** Python script invoked by `schtasks.exe` at 01:30 local (= 05:30 UTC for US Eastern in DST).
- **Cost:** Free.
- **Pipeline fit:** Fine technically.
- **State persistence:** Local SQLite — easiest possible setup.
- **AI step:** API key in a local `.env` file.
- **Failure handling:** Almost none built-in. Need to bolt on email-on-error in the script itself.
- **Setup friction:** Low–medium for someone comfortable in Windows.
- **Risks:** **The killer issue.** Windows 11 Task Scheduler is unreliable across sleep/wake. Multiple [Microsoft Q&A threads](https://learn.microsoft.com/en-us/answers/questions/4140865/task-scheduler-not-waking-home-use-windows-11-from) document that wake timers fail intermittently, S0 Modern Standby breaks the wake-from-sleep contract entirely, and clock-resync after wake can cause tasks to be skipped. A daily newsletter that silently misses a day every few weeks is a credibility problem. Workarounds (disable sleep, configure BIOS wake, "Run task as soon as possible after a scheduled start is missed") help but never reach the reliability of a cloud cron.

### Option D — Cloud cron (Cloudflare Workers / Vercel / Modal / Render)

- **Cloudflare Workers Cron Triggers:** Free tier includes cron triggers at no extra cost; minimum 1-minute granularity; no per-trigger fee ([Cloudflare docs](https://developers.cloudflare.com/workers/configuration/cron-triggers/)). However, Workers' 30-second CPU limit on the free tier and no native Python runtime for our SDKs make this a poor fit. Bundled plan removes duration limit but still adds friction.
- **Vercel Cron:** Hobby tier capped at one run/day total — fine for this use case but a footgun if you ever add a second job.
- **Modal:** Python-native, generous free tier ($30/mo credit), 5–10 min jobs trivial, persistent volumes for state. Best technical fit in this category but a new vendor to learn.
- **Render Cron Jobs:** $1/month per job, dead simple, runs any container. Decent option.
- **State persistence:** Each requires bolting on storage (KV, Postgres, Volume).
- **Risks:** Vendor lock-in is mild on Modal/Render; Cloudflare KV for state could trap you long-term.

### Option E — n8n / Make.com / Zapier

- **What:** Visual workflow builders with a "Schedule" trigger node.
- **Cost (per [MassiveGRID 2026 comparison](https://massivegrid.com/blog/n8n-pricing-self-hosted-vs-cloud-vs-zapier/)):** n8n Cloud €24/mo Starter, Make.com $9/mo for 10k operations, Zapier $19.99/mo for 750 tasks. n8n self-hosted on a €5 VPS is the cheap end.
- **Pipeline fit:** OK for n8n (has a Code node, HTTP node, Anthropic + Replicate community nodes). Make.com workable. Zapier strains on the multi-step LLM logic and would burn tasks.
- **State persistence:** n8n has built-in static data; Make.com needs Data Stores; Zapier needs a third-party DB.
- **AI step:** API key as workflow credential.
- **Failure handling:** All three have execution history + email-on-error. Best in class for a non-coder.
- **Setup friction:** Lowest of all options — drag, drop, paste keys.
- **Risks:** Per-execution billing punishes loops; vendor pricing has historically jumped with little notice (Zapier task pricing more than doubled over the past 5 years). Pulling logic out later is painful.

---

## 3. Comparison table

| Criterion | GitHub Actions | Claude Routines | Win11 Task Sched | Modal (cloud cron) | n8n Cloud |
|---|---|---|---|---|---|
| Cost @ 1 run/day | Free | $20/mo (Pro) | Free | Free (under credit) | €24/mo |
| Reliability | High (occasional cron lag) | Unknown (preview) | **Low** (sleep/wake) | High | High |
| Multi-step pipeline | Native | Awkward (LLM-mediated) | Native | Native | Native |
| State persistence | Repo or external DB | Repo (auto) | Local SQLite | Volumes | Built-in |
| AI step location | Script + secret | Native session | Script + .env | Script + secret | Workflow credential |
| Failure alerts | Built-in | Minimal | DIY | Built-in | Built-in |
| Setup time | ~2h | ~30 min | ~1h | ~1h | ~30 min |
| Lock-in risk | Low | **High** (preview) | None | Low | Medium |
| Deprecation risk | Very low | **High** | Very low | Medium | Medium |

---

## 4. Recommendation

### Primary: GitHub Actions + Supabase (free tier) for state

Sticking with the spec is the right call, with one explicit addition: **don't store analytics in the repo itself**, use a free Postgres (Supabase, Neon, or Turso). Reasoning:

1. **Reliability beats novelty.** GitHub Actions has a decade of operational track record. The newsletter cadence is daily; a one-day skip is visible to subscribers.
2. **Cost is zero.** A public repo (the codebase doesn't expose secrets) gets unlimited Actions minutes. Even private uses ~150 of 2,000 free min/month.
3. **The pipeline is deterministic ETL with one LLM step in the middle.** That's a script, not an agent. Forcing it through an agentic Routine pays an LLM tax on the deterministic 80% of the pipeline.
4. **API keys are needed anyway** (Anthropic + Replicate + beehiiv). Storing them as Actions secrets is a one-time UI click.
5. **Skill match.** Once the repo exists, the user edits one Python file and one YAML file. Total surface area: 2 files. Zero DevOps.

### Fallback: Claude Code Routines (if user resists GitHub setup)

If the user genuinely won't set up a repo + secrets, Routines is a defensible fallback because the AI editorial step is its native primitive and setup is point-and-click. Accept the daily cap, the preview status, and that you'll need to migrate within 12 months when Anthropic settles the pricing/SLA.

### Avoid

- **Windows Task Scheduler:** wake/sleep reliability is too poor for a public-facing daily product.
- **Zapier:** task billing model punishes multi-step LLM workflows.
- **Vercel Cron Hobby:** one-job-per-day cap is a future trap.

---

## 5. Biggest tradeoff vs the spec

The spec is essentially correct. The only refinement: **move analytics state out of the repo and into a hosted Postgres** so the feedback loop survives `git reset --hard` accidents and so the workflow isn't auto-disabled by 60 days of repo inactivity (which Actions does on private repos with no commits).

---

## Sources

- [Claude Code Routines docs (code.claude.com)](https://code.claude.com/docs/en/routines)
- [Claude Code Scheduled Tasks docs](https://code.claude.com/docs/en/scheduled-tasks)
- [9to5Mac — Anthropic adds routines to Claude Code](https://9to5mac.com/2026/04/14/anthropic-adds-repeatable-routines-feature-to-claude-code-heres-how-it-works/)
- [SiliconANGLE — Claude Code routines and desktop](https://siliconangle.com/2026/04/14/anthropics-claude-code-gets-automated-routines-desktop-makeover/)
- [DevOps.com — Claude Code Routines analysis](https://devops.com/claude-code-routines-anthropics-answer-to-unattended-dev-automation/)
- [GitHub Actions 2026 pricing changes](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)
- [GitHub Actions billing docs](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [Cloudflare Workers Cron Triggers docs](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [MassiveGRID — n8n vs Make vs Zapier 2026 pricing](https://massivegrid.com/blog/n8n-pricing-self-hosted-vs-cloud-vs-zapier/)
- [Microsoft Q&A — Win11 Task Scheduler wake-from-sleep failures](https://learn.microsoft.com/en-us/answers/questions/4140865/task-scheduler-not-waking-home-use-windows-11-from)
- [Microsoft Q&A — Win11 does not wake to run task](https://learn.microsoft.com/en-us/answers/questions/651690/windows-11-does-not-wake-computer-to-run-scheduled)
