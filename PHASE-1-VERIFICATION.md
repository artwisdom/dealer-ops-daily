# Phase 1 — Verification & Handoff

**Date:** 2026-04-20
**Status:** ⚠️ Phase 1 partial — free-tier launch viable, but several spec components require Scale-plan upgrade to activate.

---

## ✅ What's done

| Item | Status | Where |
|---|---|---|
| beehiiv account created | Done | Michael's account, Max trial (Day 1/14) |
| Publication "Dealer Ops Daily" created | Done | URL: `dealer-ops-daily.beehiiv.com` |
| Publication tags | Done | Business, News, Finance |
| Publishing cadence | Done | Daily |
| One-line description / tagline | Done | "The 5-minute morning briefing for the people running U.S. car dealerships." |
| Subscribe button text | Done | "Get the brief" |
| Default timezone | Done | Eastern Time (US & Canada) |
| Sender name | Done | "Dealer Ops Daily" |
| Reply-to email | **Pending verification** | Set to `Michael@AndromedaKinship.com` — beehiiv sent verify link, **Michael must click to activate** |
| Email footer copyright | Done | "© 2026 Dealer Ops Daily" |
| Physical address (CAN-SPAM compliance) | Done | 46 Lane St, Fall River, MA 02721, US |
| AI disclosure language in welcome | Done | Per editorial standards research |
| Welcome Email enabled | Done | Single welcome email, 341 words, AI disclosure included |
| Local artifacts: welcome sequence drafts | Done | `welcome-sequence/welcome-{1,2,3}-*.md` |
| Local artifacts: beehiiv config spec | Done | [beehiiv-config.md](beehiiv-config.md) |
| Local artifacts: system prompt v1 | Done | [prompts/system-prompt-v1.md](prompts/system-prompt-v1.md) |
| Domain availability check | Done | `dealeropsdaily.com` available; not registered yet (skip per Michael) |
| GitHub repo | Done | `https://github.com/artwisdom/dealer-ops-daily` (public, README only) |

---

## ⏸ Deferred to Scale-plan upgrade

Phase 0 research said the free tier had Boosts + Ad Network + automations. **That was wrong** — verified in product 2026-04-20. The following are all gated:

| Feature | Plan needed | Phase 1 impact |
|---|---|---|
| Multi-step Automations (3-issue welcome sequence) | Scale | Replaced with single Welcome Email; rebuild on upgrade |
| Boosts (monetize) | Scale + not in trial | No Boost revenue at launch; activate at Scale upgrade |
| Recommendations cross-promo (sub-exchange) | Scale | Configurable but won't deliver subs at launch |
| Referral program | Scale | Configurable but pauses after trial; **rewards not yet built** |
| Ad Network | Scale | No ad revenue at launch; activate when 1K subs + open rate ≥20% AND on Scale |
| Private branding / custom email templates | Max | Cosmetic, can wait |

---

## 🚨 Critical strategic decision Michael needs to make

The Phase 0 monetization model assumed Boosts + Referrals + Recommendations all working from Day 1 on free tier. **They don't.** This changes the launch strategy meaningfully:

**Option A — Slow free-tier launch:** Stay on free, rely on manual organic + DealerIntel seed list. Sub growth will be slower than projected (~half the rate). Upgrade to Scale ~Month 6 once natural growth justifies it (~1,500-2,000 subs).

**Option B — Day-1 Scale upgrade:** Pay $43-99/mo from launch to get Boosts + Referrals + Automations active immediately. Expected payback: Boost revenue + Referral-driven growth covers the cost by Month 3-4 if growth ramp holds.

**My recommendation: Option B.** The whole point of the project was automated growth. Without Boosts and Referrals, we lose the two highest-leverage growth channels. Going free-tier-first is penny-wise / pound-foolish here. Worth revisiting after Day 1 traffic data lands.

This decision should be made before Phase 2 begins — the daily pipeline architecture differs slightly based on which monetization features are active.

---

## 📝 Other Phase 1 carryovers / TODO list for Michael

1. **Verify reply-to email** — check `Michael@AndromedaKinship.com` inbox, click verification link
2. **Make Scale-plan decision** (see above)
3. **Configure Referral program** (when on Scale) — use [beehiiv-config.md](beehiiv-config.md) §9 for tier values
4. **Build referral fulfillment artifacts** (when on Scale):
   - Sunday meta-issue template (3 referrals)
   - Quarterly Dealer Ops Data Pack template (5 referrals)
   - "Early access" content cadence (10 referrals)
   - Sponsor intro program (25 referrals)
5. **Build 3-issue welcome sequence as Automation** (when on Scale) — content already drafted in `welcome-sequence/`
6. **Optional:** register `dealeropsdaily.com` (~$12/yr at Cloudflare or Namecheap) and configure beehiiv Custom Domain
7. **Optional:** swap Reply-to from personal Gmail to `editor@dealeropsdaily.com` once custom domain is live

---

## 🧪 Verification script

Run this from the project directory to verify Phase 1 local artifacts are intact:

```bash
# Verify all expected files exist
test -f welcome-sequence/welcome-1-who-we-are.md && echo "✅ welcome-1" || echo "❌ welcome-1 missing"
test -f welcome-sequence/welcome-2-sample-issue.md && echo "✅ welcome-2" || echo "❌ welcome-2 missing"
test -f welcome-sequence/welcome-3-referral-invite.md && echo "✅ welcome-3" || echo "❌ welcome-3 missing"
test -f beehiiv-config.md && echo "✅ beehiiv-config" || echo "❌ beehiiv-config missing"
test -f prompts/system-prompt-v1.md && echo "✅ system-prompt-v1" || echo "❌ system-prompt-v1 missing"
test -f research/00-summary.md && echo "✅ research-summary" || echo "❌ research-summary missing"
test -f research/03-sources.yaml && echo "✅ sources-yaml" || echo "❌ sources-yaml missing"
echo ""
echo "Word counts:"
wc -w welcome-sequence/*.md beehiiv-config.md prompts/system-prompt-v1.md
```

Expected output: 7 ✅, no ❌. Word counts: each file should be >300 words.

**Manual verification (in beehiiv dashboard):**
1. Visit `https://dealer-ops-daily.beehiiv.com` — should show subscribe page with "Get the brief" button + tagline
2. Visit Settings → General Info → confirm tagline + tags + button text
3. Visit Settings → Emails → confirm sender name "Dealer Ops Daily" + address "46 Lane St, Fall River MA 02721"
4. Visit Settings → Emails → Welcome Email toggle should be ON (pink) with "View Welcome Email" button
5. Click "View Welcome Email" → should show 341-word welcome with AI disclosure footer

---

## 🚀 Greenlight criteria for Phase 2

Phase 2 (the daily pipeline build) should not start until:

- [ ] Reply-to email verified (or accept Gmail as launch reply-to)
- [ ] Scale-plan decision made (Option A or B above)
- [ ] GitHub repo created and Michael has push access
- [ ] At least placeholder values for: `BEEHIIV_API_KEY`, `BEEHIIV_PUBLICATION_ID` (you have these in beehiiv → Workspace Settings → API)
- [ ] Anthropic API key obtained and ready to add as repo secret
- [ ] Decision: Supabase (paid path) or local SQLite/JSON (free path) for analytics state

Once those clear, Phase 2 starts with the daily pipeline scaffolding.

---

## Phase 1 elapsed effort

~2 hours of conversation including all Phase 0 research that came before. beehiiv signup + config: ~30 min in browser. Most time went to discovering and routing around the free-tier feature gates that Phase 0 research had wrong.
