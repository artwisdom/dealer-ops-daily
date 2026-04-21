# beehiiv Publication Config Spec — Dealer Ops Daily

This is the source of truth for every setting we apply during the beehiiv signup walkthrough. Every value here gets pasted into the dashboard.

## 1. Publication identity

| Field | Value |
|---|---|
| Publication name | **Dealer Ops Daily** |
| URL slug | `dealer-ops-daily` |
| Custom domain | `dealeropsdaily.com` (verify availability before purchase) |
| beehiiv subdomain (fallback) | `dealeropsdaily.beehiiv.com` |
| Tagline | The 5-minute morning briefing for the people running U.S. car dealerships |
| Logo | Generate placeholder on launch; commission proper mark in month 2 |
| Primary color | `#0F172A` (slate-900) — readable, neutral, not OEM-brand-coded |
| Accent color | `#F59E0B` (amber-500) — "save call" warmth |

## 2. About page copy (paste into beehiiv "About" field)

> **Dealer Ops Daily** is the five-minute morning briefing for the people actually running U.S. car dealerships — F&I directors, desk managers, and floor GMs.
>
> We cover what changed yesterday in compliance, F&I products, used-car values, and store ops, with the speed of a modern email brand and the operator credibility of a working dealer-tech company.
>
> No paywall. No parent-OEM agenda. No thirty-paragraph trade-mag features. Just the signal you need before your first save call.
>
> **How it's made:** Every issue is AI-edited from 70+ daily industry sources, then reviewed by a human editor before sending. We disclose this in the footer of every issue. We don't give financial, legal, or medical advice. Affiliate links are marked.
>
> Built by the team behind DealerIntel.

## 3. Sender identity

| Field | Value |
|---|---|
| From name | `Dealer Ops Daily` |
| Reply-to address | `editor@dealeropsdaily.com` (or beehiiv default until domain is verified) |
| Auto-responder enabled | **Yes** — see §10 below for copy |
| Sender physical address | **[YOU MUST PROVIDE — required by CAN-SPAM §5(a)(5). Cannot be a virtual mailbox.]** |

## 4. Sign-up form

- Single-field email-only form (no name field — friction kills conversion at this stage)
- CTA button text: `Get the brief`
- Post-signup redirect: thank-you page that immediately surfaces Boosts recommendations
- Embed code goes on:
  - The custom domain landing page
  - DealerIntel marketing site footer (warm seed list)
  - Each issue's web archive page

## 5. Welcome sequence (3 issues)

Drafts in `welcome-sequence/`. Sequence config:

| # | Trigger | Delay | File |
|---|---|---|---|
| 1 | New subscriber | Immediate | `welcome-sequence/welcome-1-who-we-are.md` |
| 2 | New subscriber | +1 day | `welcome-sequence/welcome-2-sample-issue.md` |
| 3 | New subscriber | +3 days | `welcome-sequence/welcome-3-referral-invite.md` |

Subject-line A/B/C variants are in each draft's frontmatter. beehiiv will auto-pick winner per send.

## 6. Subscriber tags

Apply to every subscriber on signup:

- `source:` — `direct`, `referral`, `boost`, `sparkloop`, `linkedin`, `reddit`, `dealerintel`, `unknown`
- `cohort:` — month of signup (`2026-05`, `2026-06`, ...)
- `interest:` — populated by their reply to welcome-1's "what beat?" question (`fni`, `compliance`, `used-car`, `fixed-ops`, `tech`, `hiring`, `none`)

## 7. Segments (saved searches)

| Segment | Definition | Use |
|---|---|---|
| `engaged-30d` | Opened ≥1 issue in last 30 days | Default audience for most sends |
| `re-engagement-needed` | No open in 30 days | Triggers re-engagement issue (Self-improvement loop §6) |
| `power-readers` | Opened ≥80% of last 30 issues | Test audience for new format experiments |
| `fni-interested` | Tag `interest:fni` | F&I-heavy issue gets weight upshift on send time |
| `compliance-interested` | Tag `interest:compliance` | Same |
| `seed-list` | Tag `source:dealerintel` | Track separately for LTV analysis |

## 8. Boosts

- **Opt in** to network at launch (free, generates revenue + provides post-subscribe cross-promo inventory)
- **Web Boosts only** (Email Boosts deprecated April 2026 per spec amendment §2)
- **Reject** boost offers in: payday lending, crypto, non-auto verticals
- **Accept** boost offers in: business newsletters, finance newsletters, B2B SaaS, anything dealer-vendor-adjacent
- Daily rotation handled by Phase 3 automation; for Phase 1, just enable + set the category filters

## 9. Referral program

Milestones (must match `welcome-sequence/welcome-3-referral-invite.md`):

| Referrals | Reward |
|---|---|
| 3 | Subscriber-only weekly meta-issue (Sunday digest) |
| 5 | Quarterly Dealer Ops Data Pack |
| 10 | All of the above + early access to tools/templates |
| 25 | Direct intro to one Dealer Ops sponsor of subscriber's choice |

The 5- and 25- rewards require Phase 3 deliverables (data pack template, sponsor relationships) — set them up in beehiiv anyway; we'll fulfill manually for the first month.

## 10. Reply auto-responder

Trigger: any incoming reply to a publication email.

```
Hi —

This is an automated note from Dealer Ops Daily.

We can't reply to individual emails (the publication is small and lean by design), but we read every reply ourselves and use them to tune what stories we cover.

If you're reporting a correction — thanks. We'll address it in tomorrow's issue.
If you're suggesting a beat or source — keep them coming, they shape the source list.
If you need to unsubscribe — use the link at the bottom of any issue.
If you want to sponsor or partner — reply with "PARTNER" in the subject; that gets routed to a human within 5 business days.

— Dealer Ops Daily
```

## 11. Footer template (every issue)

```
Dealer Ops Daily · [PHYSICAL ADDRESS] · [Unsubscribe]

This newsletter is produced with the assistance of AI tools and reviewed
by a human editor before sending. We are not financial, legal, medical,
or tax advisors. Information is for general interest only — verify
anything important with a qualified professional. Affiliate links are
marked. See a mistake? Reply to this email and we'll correct it in the
next issue.

Built by the team behind DealerIntel.
```

## 12. Plan choice for launch

- **Start: free tier** (up to 2,500 subs)
- **Upgrade trigger:** crossing 2,500 subs **or** earlier if Ad Network qualification arrives (which is now Scale-tier-gated per spec amendment §1)
- **First paid month likely:** ~Month 6 once Ad Network revenue covers the $43–80/mo cost

## 13. What I CAN'T do for you in the browser

Per safety policy, you must do these yourself:
- Create the beehiiv account (entering your email + password)
- Authorize any OAuth flows
- Enter payment info if/when upgrading
- Confirm the publication's physical address (CAN-SPAM compliance)
- Purchase the custom domain

Everything else (filling fields, configuring tags/segments, pasting copy from this doc) — I can drive in the browser with your per-screen approval.
