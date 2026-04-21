# Project 02 — Automated AI Newsletter on beehiiv

> **Priority rank: #2 of 13.** Cleanest legal/policy landscape of any 2026 opportunity — beehiiv explicitly allows AI-written content, pays creators $1M/month via its Ad Network, and charges 0% subscription fees. Verified revenue: Geekout $25K in one month, Cyber Corsairs $16.6K/mo, The Rundown AI $1M+ ARR, Milk Road 7-figure exit in 10 months.

---

## 🎯 Project Mission & The Automation North Star

**Mission:** Launch a hyper-niche daily newsletter on beehiiv that grows to 10,000+ subscribers with 30%+ open rate within 12 months, monetized via beehiiv Ad Network + Boosts + affiliate links + eventually a low-ticket digital product upsell.

**The Automation Mandate — non-negotiable:**

Once launched, I should never have to:
- Pick today's story
- Write the issue
- Edit or format anything
- Hit publish
- Respond to subscriber replies (use auto-responder with "this is an automated publication")
- Manually check ad earnings or analytics
- Hunt for new ad opportunities
- Decide when to pivot the niche

Every one of those is a scheduled GitHub Actions workflow calling Claude Code → beehiiv API → Apps Script analytics feedback → next-day smarter prompt.

**Acceptable human touch: 30 minutes/week** — reading the Sunday digest of what happened, approving any structural changes Claude proposes (new section, new niche sub-topic, new affiliate partner).

---

## 🔬 Pre-Build Research Directives (Do These FIRST)

### Research Task 1 — Niche selection deep dive
Evaluate these 8 candidate niches on 5 criteria: (a) CPM/ad rates in category, (b) existing newsletter competition, (c) subscriber acquisition cost, (d) my domain authority in the space, (e) longevity of topic (3+ year horizon):

1. **Dealer Ops Daily** — F&I, sales manager, desking, compliance news for auto dealerships
2. **Field Sales Intel** — Door-to-door industry roundup across solar/roofing/pest/HVAC
3. **RV Dealer Brief** — RV industry news, inventory trends, finance
4. **Indie App Revenue** — Revenue-focused newsletter for indie iOS/mobile app portfolio operators
5. **The Vertical SaaS Report** — Niche B2B software launches, acquisitions, revenue
6. **Claude Code Weekly** — Workflow patterns, new features, open-source agents
7. **AutoTech Pulse** — Automotive software/DMS/CRM industry news
8. **The Commission Report** — High-income sales operator content (goals, tools, tactics)

Output: `research/01-niche-selection.md` with scoring and a specific recommendation, plus top 3 backup niches.

### Research Task 2 — Competitor newsletter dissection
For the recommended niche, find the top 5–10 existing newsletters and analyze:
- Subscriber count (via SparkLoop, Boosts network, beehiiv discovery)
- Issue frequency and format
- Monetization (sponsor CPMs, affiliate stacks, paid tier)
- Open rate if disclosed
- Growth tactics used

Output: `research/02-competitors.md` with gap analysis and positioning statement.

### Research Task 3 — Source list discovery
Find 25–50 high-signal sources for the chosen niche:
- Industry trade press + RSS feeds
- X/Twitter accounts (if scrapable via API)
- Subreddits and Hacker News topics
- LinkedIn newsletters (public only)
- YouTube channels (transcripts via yt-dlp)
- Press-release feeds (Cision, PR Newswire)
- Earnings calls + SEC filings for industry players

Output: `research/03-sources.yaml` — structured, categorized, the daily cron consumes directly.

### Research Task 4 — Ad network + sponsorship economics
Research 2026 beehiiv Ad Network specifics:
- Exact qualification thresholds (1,000 subs + 20% open rate as of research)
- Average CPM by category in 2026
- Boosts economics (current $/sub rates)
- SparkLoop Upscribe integration value
- Direct-sold vs programmatic mix at scale

Output: `research/04-monetization-plan.md` — projected revenue curve tied to subscriber count.

### Research Task 5 — Growth channel audit
Research cold-start growth tactics that work in 2026 (post-Twitter ossification):
- Boosts network swaps
- ConvertKit Creator Network
- SparkLoop paid acquisition thresholds
- Reddit/HN organic posting cadence safe from bans
- LinkedIn cross-post automation
- Medium syndication
- Threads/Bluesky cross-post

Output: `research/05-growth-strategy.md`.

### Research Task 6 — Legal, claims, editorial guidelines
Draft:
- AI disclosure policy (what we disclose, how, where)
- Editorial guardrails (no financial advice, no political takes, no medical claims)
- Sources & verification policy
- Affiliate disclosure template
- Correction policy

Output: `research/06-editorial-standards.md`.

**Do not create the beehiiv publication until all six research docs exist and I've approved the niche selection.**

---

## 🏗️ Architecture & Tech Stack

### The pipeline (mirrors your existing DealerIntel pattern)
```
[25 RSS/API sources] 
   ↓ (GitHub Actions cron, 05:30 UTC daily)
[Claude Code: dedupe, rank, draft]
   ↓ (writes issue markdown + metadata.json to repo)
[GitHub Actions: commit]
   ↓
[beehiiv API: POST /v2/publications/{id}/posts]
   ↓ (schedule send for 06:00 UTC)
[Apps Script: poll beehiiv analytics API at 18:00]
   ↓ (writes opens/clicks/ad-earnings to Google Sheet)
[Claude Code tomorrow: reads Sheet, re-ranks source priorities]
```

### Core stack
- **Publisher:** beehiiv (API access on Scale plan; Launch plan has API too now)
- **Cron:** GitHub Actions scheduled workflows
- **LLM:** Claude Sonnet 4.5 via Anthropic API (Opus 4.7 for Sunday "weekly digest" only)
- **Ingestion:** `feedparser`, Apify (for sources without RSS), yt-dlp for video transcripts
- **Analytics relay:** Google Apps Script → Google Sheet (matches your existing infrastructure pattern)
- **Asset generation:** Flux Schnell for hero images, Recraft for section dividers
- **Affiliate link management:** Self-hosted key-value store (Supabase) + Claude picks best-fit CTA per issue

### File structure
```
/prompts/              # versioned system prompts — Claude reads the current one
/sources.yaml          # structured feed list
/issues/YYYY-MM-DD.md  # every issue ever shipped (audit trail)
/analytics.json        # latest 90-day performance by source and topic
/.github/workflows/
   daily-issue.yml
   weekly-review.yml
   monthly-growth-report.yml
   boost-management.yml
```

---

## 💸 Lean Launch Stack (Start Here, Upgrade on Trigger)

**The default rule:** every tool starts on its free tier. Upgrade only when a specific trigger event proves the cost is justified.

| Component | Lean choice | Cost | Upgrade trigger |
|---|---|---|---|
| Newsletter platform | **beehiiv free tier** (up to 2,500 subs, full features incl. Boosts + Ad Network) | $0 | Crossing 2,500 subs (good problem — upgrade to Launch $39/mo) |
| LLM | **Claude API** (already using; this is the engine) | ~$30-80/mo | N/A — never substitute a weaker model |
| Source ingestion | **`feedparser` Python lib + Apps Script** (already in your stack) | $0 | Need scrapes that bypass anti-bot — use Project 06 infra |
| Analytics relay | **Google Sheets + Apps Script** (already in your stack) | $0 | Never — Sheets is enough until 100K+ rows |
| Hero images | **Flux Schnell via Replicate** pay-per-use, OR free Pexels/Unsplash API for stock | $0–3/mo | Brand demands more polished art (likely never) |
| Affiliate tracking | **Custom Cloudflare Workers free tier** + Google Sheets ledger | $0 | Click volume exceeds 100K/day |
| Hosting/cron | **GitHub Actions free tier** (2K min/mo public, 3K private) | $0 | Workflow minutes exceed limits — unlikely for 1 daily run |
| Welcome sequence | **Native beehiiv automation** (free) | $0 | N/A |

**Lean monthly cost for this project: ~$30–80** (almost entirely Claude API).

**Things NOT to cheap out on:**
- **Don't run a worse LLM to save $30/mo.** Claude is doing the editorial work — quality compounds in open rate.
- **Don't skip Boosts** — it's free and is the #1 cold-start growth lever for niche newsletters.

**When you would consider paying:**
- beehiiv Launch ($39/mo): mandatory at 2,500 subs. By then you should have $200+/mo in Ad Network.
- beehiiv Scale ($99/mo) or Max: only if direct sponsor revenue justifies advanced segmentation. Likely month 9+.
- SparkLoop Upscribe paid acquisition: only after you've validated $0.50+ subscriber LTV via Ad Network earnings.

---

## ✅ Automation Requirements Checklist

- [ ] Daily 05:30 UTC cron generates issue without human input
- [ ] 3 subject-line variants generated; beehiiv A/B selects winner
- [ ] Hero image auto-generated and uploaded
- [ ] Affiliate links auto-injected from inventory based on semantic fit
- [ ] "Tool of the day" section pulls from an Airtable of rotating affiliate products
- [ ] Boosts recommendations auto-added when eligible
- [ ] Analytics pulled back nightly and fed to tomorrow's prompt
- [ ] Weekly Sunday "meta-review" issue written by Opus 4.7 (summarizing the week's biggest stories)
- [ ] Monthly growth report auto-filed as GitHub Issue summarizing MRR, subs, open rate trend
- [ ] Auto-submit to beehiiv Ad Network the moment threshold is hit
- [ ] Auto-rotate system prompt when open rate drops >15% vs 30-day baseline
- [ ] Subscriber reply auto-responder ("This is an automated publication, follow our X for faster updates")
- [ ] Churn-risk auto-detection: subs who haven't opened in 30 days get re-engagement issue

---

## 💰 Revenue Model & Monetization

Monetization stacks cumulatively as subscribers grow:

| Milestone | Subs | Unlocked revenue | Target monthly |
|---|---|---|---|
| Launch | 0 | Nothing | $0 |
| 500 | 500 | Boosts partnerships | $200–500 |
| 1,000 | 1,000 | **Ad Network eligibility + 20% open req** | $500–1,500 |
| 2,500 | 2,500 | Direct sponsor outreach (CPM $25–40) | $2K–5K |
| 5,000 | 5,000 | Premium tier launch ($10/mo, 3% convert) | $3K–8K |
| 10,000 | 10,000 | Mature CPMs + digital product upsell | $8K–20K |

**Rule:** Never sell anything the pipeline can't automate. No paid community. No courses with live sessions. No consulting.

Approved upsells (all automated):
- Digital product bundle via Gumroad (ties to Project 09)
- Paid premium tier with bonus data/insights
- Affiliate commissions (automated via link injection)
- Job board (automated listing submission + payment)

---

## ⚠️ Risk, Compliance & Platform Policy

### Primary risks
1. **Open rate decay** — biggest revenue killer. Self-improvement loops address this.
2. **Niche burn-out** — if chosen niche goes cold (e.g., industry consolidation), pivot plan needed.
3. **CAN-SPAM / GDPR** — beehiiv handles most of it, but correct physical address + unsubscribe + AI disclosure required.
4. **AI disclosure expectations** — no legal requirement on beehiiv as of 2026, but best practice: footer disclosure "Edited by AI, reviewed by human editor" (which becomes true when I click approve on Sunday).

### Guardrails
- NO stock picks, trade ideas, or specific financial advice
- NO political/partisan commentary
- NO health/medical claims beyond citing peer-reviewed sources
- ALL statistics must have a source link
- Affiliate disclosure in every issue with affiliate links
- Stated "AI-assisted editorial" footer

---

## 🔄 Self-Improvement Loops

### Loop 1: Source quality scoring
Every issue records which sources contributed which stories. Stories that drove the highest click-through get their sources up-weighted in tomorrow's priority ranking. Sources that consistently produce ignored content get pruned after 30 days.

### Loop 2: Subject line optimization
A/B data feeds a Claude analysis prompt weekly. Winning patterns (format, length, punctuation, emoji usage) get baked into the next week's prompt instructions.

### Loop 3: Content format evolution
Monthly, Claude analyzes the highest-engagement issues and hypothesizes what format changes to try (e.g., "issues with a 3-bullet hook are opening 12% better than single-paragraph openers"). Auto-opens PR to update the system prompt.

### Loop 4: Affiliate link ROI rotation
Weekly, affiliate click-through and conversion data pulled. Links with <0.5% CTR after 30 days are retired. New affiliates auto-onboarded from a watchlist when they outperform the replaced one.

### Loop 5: Growth channel reallocation
Monthly, growth source attribution (Boost, SparkLoop, organic, referral) is analyzed. Budget (if any) shifts toward the highest LTV source.

### Loop 6: Open-rate drift alerting
If rolling 7-day open rate drops >15% from 30-day baseline, an emergency GitHub Issue is filed with Claude's analysis of probable causes (subject line pattern change, send-time drift, list-quality decay) and a proposed fix.

---

## 📊 Success Metrics & Monitoring

### Daily KPIs
- Opens, clicks, unsubs, bounces
- CTR per link
- Subject line winner

### Weekly KPIs (auto-filed Sunday)
- Net new subs, growth rate
- Open rate rolling average
- Ad Network earnings
- Boosts earnings
- Top 3 and bottom 3 stories by engagement

### Monthly KPIs
- MRR breakdown by source
- Churn rate
- LTV per subscriber
- Source ROI leaderboard

### Alerting (GitHub Issues, labeled)
- Open rate -15% vs baseline
- Unsubscribe rate >0.5% on a single issue
- API failure (beehiiv, Claude, RSS)
- Ad network earnings -30% month-over-month

---

## 🚀 The Ready-to-Execute Claude Code Kickoff Prompt

Paste this into the new Claude Code project:

```
You are the editor-in-chief and automation engineer of a new beehiiv newsletter. Read PROJECT.md fully. Your mission: ship a fully automated daily newsletter that grows to 10K subscribers with 30%+ open rate inside 12 months, requiring less than 30 minutes per week of my time after launch.

PHASE 0 — RESEARCH (mandatory, no shortcuts):
Execute all six research tasks in "Pre-Build Research Directives". Use web_search and web_fetch for external data, the Anthropic API for structured analysis. Persist to ./research/*.md and ./research/*.yaml. Produce research/00-summary.md with: (1) recommended niche and positioning, (2) top 25 content sources, (3) first 90-day editorial calendar theme list, (4) projected revenue curve by month. Pause for my approval of the niche choice before proceeding.

PHASE 1 — PUBLICATION SETUP:
- Create the beehiiv publication via API (or guide me through the one-time signup if API-gated)
- Configure: publication name, about, custom domain if applicable, sign-up form, welcome sequence (3 automated issues drip), subscriber tags, segments
- Set up the boosts program opt-in
- Configure the referral program
- Write and schedule the welcome sequence (3 issues)

PHASE 2 — THE DAILY PIPELINE:
Build the GitHub Actions workflow described in the "Architecture" section. Key components:
- Source ingestion script (sources.yaml → today's candidate stories)
- Dedupe + rank via Claude
- Draft issue generation with versioned prompt
- 3-variant subject line
- Hero image generation via Flux
- Affiliate link injection from Supabase inventory
- beehiiv API post + schedule
- Analytics feedback loop via Apps Script → Google Sheet → next-day prompt

Deliver a dry-run mode that I can trigger manually to see an issue drafted without sending, so I can validate quality before going live.

PHASE 3 — GROWTH & MONETIZATION AUTOMATION:
- Auto-submit to beehiiv Ad Network as soon as threshold is met
- Daily Boosts cross-promotion rotation (Claude picks best-fit newsletter from network)
- SparkLoop Upscribe integration
- Monthly sponsor prospect list auto-generated (direct-sold pipeline)
- Automated partner outreach email draft (saved for my review, not sent — this is the only "maybe manual" piece)

PHASE 4 — SELF-IMPROVEMENT LOOPS:
Implement all six loops described in PROJECT.md. Each is its own workflow with a dedicated Claude prompt and a success test.

PHASE 5 — LAUNCH:
Ship the first live issue. Monitor for 7 days. File a "launch post-mortem" GitHub Issue with what worked, what didn't, and what Claude auto-adjusted.

CONSTRAINTS:
- 30 minutes/week of my time max after launch
- No feature that requires me to answer subscriber emails
- No section that requires me to "pick" something weekly — if a human has to pick, the pipeline is broken
- Every workflow must have a self-test

OUTPUT:
PR per phase with verification script. Don't advance phases without verification passing. Begin Phase 0 now.
```

---

## 🛠️ Post-Launch Maintenance (~30 min/week)

**Sunday ritual:**
- Read the weekly meta-issue (5 min)
- Approve or reject the 1–2 improvement PRs Claude opened (15 min)
- Glance at growth and revenue metrics (5 min)
- Review any flagged editorial concerns (5 min)

**That's it.** If anything else creeps in, patch the pipeline.
