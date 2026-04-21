# Dealer Ops Daily — Source-list Notes

## How the categories were chosen

A daily newsletter for U.S. auto-dealership operators competes on two dimensions: speed (the recipient finds out before they would have on their own) and synthesis (someone has already read the four articles, three filings, and one tweet and tied them together). The ten source categories in `03-sources.yaml` are organized so the pipeline can hit all four "places news breaks" each morning — trade press, primary sources (regulators, OEMs, public companies), insider chatter (X, Reddit, YouTube), and aggregated industry data.

The order roughly mirrors editorial priority. Trade press (cat. 1) gives polished, near-real-time coverage of everything else and is the densest source-per-byte. OEM and PR-wire feeds (cat. 2) catch incentive program changes, recalls before NHTSA finalizes them, and supplier deals. Government feeds (cat. 3) drive the entire compliance beat — F&I products, advertising rules, indirect-lending oversight. Trade associations (cat. 4) tell you what NADA and NIADA think the industry should care about, which is itself news. Vendor newsrooms (cat. 5) capture the DMS/CRM beat that has become an above-the-fold story since the June 2024 CDK Global cyberattack and the ongoing CDK-Tekion legal fight. Market-data publishers (cat. 6) drop the monthly MUVVI and weekly Black Book reports that anchor wholesale conversations. X, Reddit, and YouTube (cat. 7-9) are the leading-indicator layer — dealers tweet about a manufacturer policy hours before the trade press writes it up. SEC filings and earnings calls (cat. 10) provide the quantitative backbone for any "how the public dealer groups are doing" segment.

## Tier-1 vs nice-to-have

Tier-1 (weight 9-10) sources, which the pipeline must reach every cycle:

- **Automotive News** and the Automotive News Retail subfeed (the canonical industry of-record).
- **F&I and Showroom** (the only daily publication explicitly indexed to the F&I role this newsletter targets).
- **Cox Automotive newsroom** plus **Manheim Used Vehicle Value Index** (the sentiment + wholesale-data stack).
- **FTC press releases**, the FTC Automobiles topic feed, and **CFPB newsroom** (compliance is non-negotiable for F&I and desking content).
- **Car Dealership Guy News** plus the **@GuyDealership** X account (community sentiment + viral-news leading indicator).
- **CBT News** and **Auto Remarketing** (daily trade press with strong dealer engagement).
- **SEC EDGAR Atom feeds for AutoNation, Lithia, and CarMax** (financial signal for the public-group-watching segment).

Tier-2 (weight 7-8) sources — pulled daily but not blocking: WardsAuto/Automotive Dive, NIADA, ASOTU, CDK/Tekion/Reynolds vendor pages, Black Book, J.D. Power, Edmunds, and remaining SEC EDGAR feeds.

Tier-3 (weight 4-6) sources — nice-to-have, weekly to monthly cadence: Auto Dealer Today, Used Car News, Digital Dealer, AIADA, ATAE, RouteOne, DealerSocket/Solera, Cars.com/TrueCar SEC filings, niche subreddits, secondary YouTube channels.

## Known coverage gaps

1. **State-level regulatory news** is under-covered. Only California, Texas, and CA DOI made the list; the daily cron should ideally hit dealer-association newsletters from the top-10 dealer-population states (FL, NY, IL, PA, OH, GA, NC, MI, NJ). None publish RSS — all would need scraping. Worth adding once the pipeline is stable.

2. **Captive auto-finance lender news** (Ford Credit, GM Financial, Toyota Financial Services, Ally, Santander Consumer USA, Westlake) is only partially captured via OEM newsrooms. Captives drive more F&I-product economics than the OEMs themselves. A future revision should add their press pages individually.

3. **Insurance / GAP / VSC market** content is mostly absent — this is a measurable revenue lever for F&I managers and a likely paid-newsletter expansion area. Trade press coverage is thin; the gap probably needs to be filled with newsletter cross-subscriptions (e.g., AutoFinanceNews.net, P&C Specialist) plus selected company press pages (Allstate Dealer Services, GWC Warranty, Assurant Vehicle Care).

4. **Compliance-attorney blogs** (Hudson Cook LLP, Counselor Library, Ballard Spahr's Consumer Finance Monitor) are excellent CFPB/FTC interpretation sources. Adding 3-4 of them as `category: regulatory_commentary` would meaningfully strengthen the compliance beat with very little marginal cost (all expose RSS).

5. **Recall-specific signal** beyond NHTSA is not captured — Transport Canada and Mexico's Profeco occasionally pre-empt U.S. recalls. Nice-to-have, low priority.

## Sources that need paid Apify (or X API) scraping

All entries with `category: social_x` (15 sources) require either the paid X/Twitter API or an Apify twitter-scraper actor. Reddit feeds work natively via the public `.rss` endpoint and are free to ingest, though Reddit has been progressively limiting that endpoint and may force a switch to the official API. YouTube channel transcripts are free in principle (whisper.cpp on the audio downloaded by yt-dlp is the cheapest path; the unofficial transcript-API library is faster but breaks every few months — Apify has stable actors for both at low per-run cost).

Vendor newsrooms (CDK, Tekion, Reynolds, Reynolds, Solera, RouteOne) and several state DMV pages have no RSS and will need either Playwright scrapers run from the cron or Apify website-content-crawler runs. Apify is recommended for the state DMV pages because they are JavaScript-heavy and infrequently updated — the per-run cost is trivial and the maintenance is offloaded.

The PR Newswire automotive feed and the GlobeNewswire automotive feed both expose RSS but limit to ~20 most recent items; if a dealer-relevant release is buried, the pipeline should fall back to the search UI (which can be scraped via Apify if needed).

## Operational notes for the pipeline

- Verify each `rss` URL on first crawl; treat 404s as soft-fail and log for review rather than blocking the cycle.
- Many WordPress-based publications (CBT News, AutoSuccess, Impel) expose `/feed`, `/feed/`, and `/rss` interchangeably. The pipeline should try variants before declaring an RSS dead.
- SEC EDGAR Atom feeds (the `&output=atom` trick) are stable and rate-limited but effectively unmetered for low volumes. Use the official EDGAR fair-access policy (declare a User-Agent string with a contact email).
- Keep the `weight` field as a starting prior; after the first 30 days, recompute weights from "stories that survived editorial selection" rather than a priori judgment.
