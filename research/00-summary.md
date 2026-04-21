# Phase 0 Research Summary — Decision Brief

**Project:** Automated daily beehiiv newsletter
**Date:** 2026-04-20
**Status:** ⏸ **PAUSED — awaiting niche approval before Phase 1**

This document is the executive summary of seven research deliverables. Read this top-to-bottom; dive into the linked detail docs only where you want to second-guess a recommendation.

| # | Deliverable | File |
|---|---|---|
| 1 | Niche selection scoring (8 candidates) | [01-niche-selection.md](01-niche-selection.md) |
| 2 | Competitor dissection | [02-competitors.md](02-competitors.md) |
| 3 | Source list (YAML) + notes | [03-sources.yaml](03-sources.yaml) · [03-sources-notes.md](03-sources-notes.md) |
| 4 | Monetization plan & 12-month revenue curve | [04-monetization-plan.md](04-monetization-plan.md) |
| 5 | Growth strategy (90-day plan) | [05-growth-strategy.md](05-growth-strategy.md) |
| 6 | Editorial standards & guardrails | [06-editorial-standards.md](06-editorial-standards.md) |
| 7 | Runtime architecture comparison | [07-runtime-architecture.md](07-runtime-architecture.md) |

---

## 1. Recommended Niche & Positioning

### Recommendation: **Dealer Ops Daily** — score 41/50

A daily 5-minute morning briefing for U.S. auto-dealership operators (F&I directors, desk managers, used-car managers, compliance leads, floor GMs).

**Why it wins on the 5 criteria** (full matrix in [01-niche-selection.md](01-niche-selection.md)):

| Criterion | Score | Why |
|---|---|---|
| CPM / ad rates | 9/10 | Auto-vendor sponsor CPMs run $75–200 — top quartile of any B2B niche |
| Competition | 7/10 | CDG (~55K subs) proves daily format works; no one owns the *operator-tactical* lane |
| CAC | 7/10 | Warm DealerIntel customer base = free seed; auto Twitter still active for organic |
| Operator authority | 10/10 | DealerIntel = highest credibility of any candidate; vendors already know you |
| Longevity | 9/10 | 16K+ U.S. franchised + 60K+ independent dealers; CARS Rule + EV transition keep churn high for 5+ years |

**Positioning statement** (vetted against CDG, Automotive News, SubPrime Auto Finance News):

> *Dealer Ops Daily is the five-minute morning briefing for the people actually running U.S. car dealerships — F&I directors, desk managers, and floor GMs. We cover what changed yesterday in compliance, F&I products, used-car values, and store ops, with the speed of a modern email brand and the operator credibility of a working dealer-tech company. No paywall, no parent-OEM agenda, no thirty-paragraph trade-mag features — just the signal you need before your first save call.*

**Top 3 backup niches** (in case you reject the recommendation):
1. AutoTech Pulse — 40/50 — automotive software/DMS/CRM industry news. Lower CAC, slightly weaker CPMs.
2. Field Sales Intel — 35/50 — door-to-door industry roundup (solar, roofing, pest, HVAC). Bigger TAM but weaker domain authority.
3. The Vertical SaaS Report — 34/50 — niche B2B software news. Highest CPM ceiling, hardest cold start.

---

## 2. Top 25 Content Sources

Pulled from [03-sources.yaml](03-sources.yaml) (which has 70 verified entries across 10 categories). These are the tier-1 weight-≥8 daily-cycle sources the cron will hit every morning.

| # | Source | Category | Weight |
|---|---|---|---|
| 1 | Automotive News | Trade press | 10 |
| 2 | Automotive News Retail | Trade press | 10 |
| 3 | F&I and Showroom (FI Magazine) | Trade press | 10 |
| 4 | FTC Press Releases | Government | 10 |
| 5 | FTC Automobiles topic feed | Government | 10 |
| 6 | CFPB Newsroom | Government | 10 |
| 7 | Manheim Used Vehicle Value Index | Market data | 10 |
| 8 | Cox Automotive Industry Insights | Market data | 10 |
| 9 | NHTSA Recalls feed | Government | 9 |
| 10 | Automotive Dive | Trade press | 9 |
| 11 | CBT News | Trade press | 9 |
| 12 | Auto Remarketing | Trade press | 9 |
| 13 | Car Dealership Guy News (CDG) | Trade press | 9 |
| 14 | NADA Press Releases | Trade association | 9 |
| 15 | vAuto / Cox Automotive Insights | Vendor newsroom | 9 |
| 16 | @GuyDealership (Car Dealership Guy) | X handle | 9 |
| 17 | WardsAuto / Automotive Dive | Trade press | 8 |
| 18 | AutoSuccess | Trade press | 8 |
| 19 | Auto Dealer Today | Trade press | 8 |
| 20 | NADA Headlines | Trade association | 8 |
| 21 | NIADA Dashboard | Trade association | 8 |
| 22 | ASOTU Daily | Trade association | 8 |
| 23 | CDK Global Newsroom | Vendor newsroom | 8 |
| 24 | Tekion News | Vendor newsroom | 8 |
| 25 | Black Book Insights | Market data | 8 |

The remaining 45 sources (OEM newsrooms, X handles, subreddits, YouTube channels, SEC EDGAR feeds for the public auto-retail groups) populate the secondary candidate pool the ranker draws from when tier-1 is thin. See [03-sources-notes.md](03-sources-notes.md) for which ones need paid Apify scraping (X handles, vendor newsrooms without RSS, state DMV pages).

**Known gaps to close in Phase 2:** captive auto-finance lender press (Ford Credit, Ally, Westlake), GAP/VSC vendor news, compliance-attorney blogs (Hudson Cook, Ballard Spahr).

---

## 3. First 90-Day Editorial Calendar — Recurring Themes

The pipeline is candidate-story-driven, not pre-planned, but these themes act as the prompt's "what to upweight when ambiguous" signal. Each Monday the prompt hard-anchors on the week's theme; Tue–Fri ride the news cycle.

### Month 1 — Establish the operator-tactical voice

| Week | Theme anchor | Why now |
|---|---|---|
| 1 | **CARS Rule readiness** — operational checklists | FTC enforcement still rolling out; high search demand |
| 2 | **Used-car desking math** — gross-per-retail-unit trends | Manheim Q2 index always lands here; ride the data |
| 3 | **F&I product menu economics** — VSC/GAP attach rates | Evergreen; first sponsorship pitch hook |
| 4 | **Compliance week** — Safeguards Rule, Holder Rule, state-level updates | Pivots to attorney-source quotes; positions us as the "compliance-aware" brief |

### Month 2 — Layer in tech, vendor, and people stories

| Week | Theme anchor | Why now |
|---|---|---|
| 5 | **DMS migration economics** — CDK vs Tekion vs Reynolds switching cost | Always topical; vendor newsroom heavy |
| 6 | **Variable-ops hiring & comp** — pay plan benchmarks | Early-summer hiring cycle; high engagement |
| 7 | **Subprime & captive lender update** — approval rates, buy-rate moves | Aligns with end-of-Q2 lender data |
| 8 | **EV retail playbook** — what works on the floor today | Ride OEM Q2 earnings cycle |

### Month 3 — Differentiate sharply, open monetization runways

| Week | Theme anchor | Why now |
|---|---|---|
| 9 | **Buy-sell market** — multiples, megadealer M&A | Boutique brokers want sponsor placement here |
| 10 | **AI in the store** — practical desking/F&I/BDC use cases | High virality; aligns with operator's authority |
| 11 | **Fixed-ops profit** — service/parts margin levers | Underserved; opens HVAC-of-cars sponsor category |
| 12 | **90-day reader survey + state-of-the-store quarterly** | Native lead-magnet for first sponsor sell-sheet |

The weekly Sunday "meta-issue" (per spec, written by Opus 4.7) recaps the week and previews next week's theme — also functions as the weekly engagement spike the Ad Network values.

---

## 4. Projected Revenue Curve (12 Months)

From [04-monetization-plan.md](04-monetization-plan.md). Assumes the growth ramp from [05-growth-strategy.md](05-growth-strategy.md) holds (~2,500 subs by day 90 → 10,000 by month 12) and open rate stays ≥25%.

| Month | Subs | Ad Network | Boosts | SparkLoop | Direct sponsor | Affiliate | Premium | **Total MRR** |
|---|---|---|---|---|---|---|---|---|
| 1 | 100 | $0 | $0 | $0 | $0 | $0 | $0 | **$0** |
| 2 | 250 | $0 | $0 | $0 | $0 | ~$25 | $0 | **~$25** |
| 3 | 500 | $0 | $50 | $0 | $0 | ~$60 | $0 | **~$110** |
| 4 | 1,000 | $150 | $150 | $0 | $0 | ~$120 | $0 | **~$420** |
| 5 | 1,800 | $400 | $300 | $200 | $0 | ~$220 | $0 | **~$1,120** |
| 6 | 2,800 | $750 | $500 | $350 | $1,000 | ~$340 | $0 | **~$2,940** |
| 7 | 4,000 | $1,200 | $700 | $500 | $2,000 | ~$480 | $0 | **~$4,880** |
| 8 | 5,500 | $1,800 | $900 | $700 | $3,000 | ~$650 | $550 | **~$7,600** |
| 9 | 7,000 | $2,400 | $1,100 | $900 | $4,000 | ~$840 | $1,050 | **~$10,290** |
| 10 | 8,200 | $2,900 | $1,250 | $1,000 | $5,000 | ~$980 | $1,475 | **~$12,605** |
| 11 | 9,200 | $3,300 | $1,400 | $1,100 | $5,500 | ~$1,100 | $1,840 | **~$14,240** |
| 12 | 10,000 | $3,700 | $1,500 | $1,200 | $6,000 | ~$1,200 | $2,000 | **~$15,600** |

**Year-1 cumulative revenue:** ~$63K–$75K depending on direct-sponsor close timing.
**Steady-state MRR at 10K subs (month 13+):** ~$11.5K–$15.6K (~$138K–$187K ARR run-rate).
**Biggest revenue lever:** direct-sold sponsorship from month 6 — 3× the Ad Network CPM for the same impression.
**Biggest risk:** growth ramp slipping. If sub growth from month 5 stalls below ~800/month, model collapses to ~$3–4K MRR.

⚠️ **Plan-cost note:** beehiiv Ad Network and Boosts now require the Scale plan ($43–$99/mo at relevant tiers). Your real first-paid month is when you cross 2,500 subs (~month 6) and Ad Network revenue covers it.

---

## 5. Critical Findings & Spec Updates Needed

These deserve flagging before Phase 1 because they change decisions in the kickoff prompt:

1. **beehiiv Ad Network is gated to Scale plan as of 2026** (not the free tier as PROJECT.md assumes on line 150). Free tier still works for launch, but the "auto-submit when threshold is met" automation needs to also trigger a plan upgrade. Real lean cost is ~$43–80/mo from month 6, not $0.

2. **Email Boosts deprecated April 2026.** Only Web Boosts remain. PROJECT.md's "Boosts cross-promotion rotation" needs to switch to web-based recommendations on the post-subscribe page only.

3. **beehiiv AUP (Dec 2025) bans pure-AI publications without "meaningful human input."** Your Sunday 30-min approval ritual is the documented human review — formalize this or risk account suspension. Editorial standards doc has the language.

4. **GitHub Actions is the right runtime** (not Claude Code Routines as a primary). Routines are still in research preview, capped at 5 runs/day on Pro, and Anthropic explicitly warns the API surface may change. Use Routines as the fallback for the *weekly meta-review* only (lower stakes, AI-native step). Full comparison in [07-runtime-architecture.md](07-runtime-architecture.md).

5. **Reddit + 1:1 founder DMs cannot be automated.** Both stay manual or risk bans. Your 30-min/week budget needs to absorb ~10 min of Reddit/DM posting in months 1–3.

6. **Affiliate disclosure must appear near top, not just footer** (FTC 16 CFR 255 in 2026). The issue template needs three disclosure touchpoints: section header, inline tag, footer. Existing spec only mentions footer — would be non-compliant.

7. **Two-source minimum + attribution rules** must be hard-baked into the system prompt or you take on defamation liability. Editorial doc has the constraint language ready to paste.

---

## 6. What Phase 1 Will Look Like (preview, not yet started)

Pending your approval of the niche, Phase 1 will:
- Walk you through one-time beehiiv signup (API can't create publications)
- Generate 3 welcome-sequence drafts (issue 1: who/what we are; issue 2: 5-min sample issue; issue 3: invitation to refer)
- Propose a custom domain (suggested: `dealeropsdaily.com` — verify availability before committing)
- Pre-populate the boosts opt-in copy and referral milestones
- Hand you a checklist of beehiiv settings to click through (sender name, physical address, AI-disclosure footer)

---

## ⏸ Approval Gate — Decision Required

To unblock Phase 1, please confirm:

1. **Niche:** Approve **Dealer Ops Daily**? (Or pick a backup: AutoTech Pulse / Field Sales Intel / Vertical SaaS Report.)
2. **Runtime:** Confirm **GitHub Actions** as primary cron (you'll need to create a GitHub repo + add 3–5 secrets when we get there). If you'd rather avoid GitHub entirely, the fallback is Cloudflare Workers Cron + Supabase — slightly more setup but equally robust.
3. **Brand name:** Stick with "Dealer Ops Daily"? Alternatives if you'd rather: "The F&I Brief", "Variable Ops Daily", "The Save Call". Naming gets locked in Phase 1.
4. **Spec changes:** Acknowledge the 7 critical findings above will be applied to subsequent phases.

I'm holding here until you reply.
