"""Source ingestion: load sources.yaml, fetch RSS feeds, return candidate stories.

Uses feedparser for RSS/Atom. Sources without an RSS feed (X handles, vendor newsrooms,
state DMV pages) are skipped here — they'd be added in Phase 3 via Apify.

Self-test: `python -m pipeline.ingest --dry-run` prints the candidate pool from
fixtures so you don't need network access to verify the module wiring.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone

import feedparser
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .models import Candidate, Source, SourceList

log = logging.getLogger(__name__)


def load_sources() -> SourceList:
    with settings.sources_file.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return SourceList.model_validate(raw)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Fetch + parse one RSS/Atom feed. Retries on transient failure."""
    parsed = feedparser.parse(url, request_headers={"User-Agent": "DealerOpsDailyBot/0.1"})
    if parsed.bozo and not parsed.entries:
        # Real failure — feedparser sets bozo on parse errors AND on harmless quirks.
        # We only treat as failure when there's no usable content.
        raise RuntimeError(f"Feed parse failed: {url} ({parsed.bozo_exception!r})")
    return parsed


def _entries_to_candidates(source: Source, parsed: feedparser.FeedParserDict, since: datetime) -> list[Candidate]:
    out: list[Candidate] = []
    for entry in parsed.entries[: settings.max_stories_per_source]:
        published = None
        for key in ("published_parsed", "updated_parsed"):
            if entry.get(key):
                # feedparser returns time.struct_time
                published = datetime(*entry[key][:6], tzinfo=timezone.utc)
                break
        if published and published < since:
            continue

        out.append(
            Candidate(
                source_name=source.name,
                source_weight=source.weight,
                headline=entry.get("title", "").strip(),
                url=entry.get("link", "").strip(),
                summary=(entry.get("summary") or entry.get("description") or "").strip()[:600],
                published=published,
            )
        )
    return out


def fetch_candidates(since_hours: int = 36) -> list[Candidate]:
    """Walk every source with an RSS URL and return the candidate pool.

    `since_hours=36` gives us a 1.5-day window so weekend/Monday issues see Friday news.
    """
    sources = load_sources()
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    all_candidates: list[Candidate] = []

    for source in sources.sources:
        if not source.rss:
            continue
        try:
            parsed = _fetch_feed(source.rss)
        except Exception as exc:  # noqa: BLE001 — network IO, intentional broad catch
            log.warning("Skipping %s: %s", source.name, exc)
            continue
        all_candidates.extend(_entries_to_candidates(source, parsed, since))

    # Dedupe by stable_id (URL-based)
    seen: dict[str, Candidate] = {}
    for c in all_candidates:
        if c.stable_id not in seen or c.source_weight > seen[c.stable_id].source_weight:
            seen[c.stable_id] = c

    deduped = sorted(seen.values(), key=lambda c: c.source_weight, reverse=True)
    return deduped[: settings.max_candidates_to_rank]


def fetch_candidates_from_fixture() -> list[Candidate]:
    """For dry-run + tests: load a deterministic candidate pool from fixtures/."""
    fixture_path = settings.fixtures_dir / "candidates.json"
    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Dry-run requires {fixture_path}. Run `python -m pipeline.ingest --seed-fixture` to generate one."
        )
    with fixture_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Candidate.model_validate(item) for item in raw]


def seed_fixture() -> None:
    """Write a deterministic candidates.json for offline development."""
    settings.fixtures_dir.mkdir(parents=True, exist_ok=True)
    sample = [
        Candidate(
            source_name="FTC Press Releases",
            source_weight=10,
            headline="FTC settles with three dealer groups over CARS Rule add-on disclosure violations",
            url="https://www.ftc.gov/news-events/news/press-releases/2026/04/ftc-settles-cars-rule-2026",
            summary="The Federal Trade Commission today announced settlements totaling $4.7M with three multi-rooftop dealer groups for violations of the Combatting Auto Retail Scams Rule, specifically around aggregated add-on disclosures and timing of consumer acknowledgement.",
            published=datetime(2026, 4, 19, 14, 0, tzinfo=timezone.utc),
        ),
        Candidate(
            source_name="Cox Automotive Industry Insights",
            source_weight=10,
            headline="Manheim Used Vehicle Value Index falls 1.4% MoM in April; compact SUV leads decline",
            url="https://www.coxautoinc.com/market-insights/manheim-used-vehicle-value-index-april-2026/",
            summary="The April Manheim Used Vehicle Value Index posted a 1.4% month-over-month decline. Compact SUV (-3.1%) led the drop while full-size pickup (+0.6%) continued to defy the trend.",
            published=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
        ),
        Candidate(
            source_name="F&I and Showroom (FI Magazine)",
            source_weight=10,
            headline="GM Financial expands subprime tier 4-5 approvals 9% YoY in Q1; Ford Credit tightens",
            url="https://www.fi-magazine.com/news/gm-financial-q1-2026-subprime-expansion",
            summary="GM Financial reported a 9% year-over-year increase in tier 4-5 subprime approvals in Q1, while Ford Credit moved in the opposite direction with a 6% tightening of the same band.",
            published=datetime(2026, 4, 19, 11, 30, tzinfo=timezone.utc),
        ),
        Candidate(
            source_name="CFPB Newsroom",
            source_weight=10,
            headline="CFPB issues guidance on Holder Rule application to digital retail finance contracts",
            url="https://www.consumerfinance.gov/about-us/newsroom/cfpb-holder-rule-digital-finance-2026/",
            summary="New CFPB guidance clarifies how the Holder Rule applies to retail installment contracts originated through digital storefronts and third-party application portals.",
            published=datetime(2026, 4, 19, 16, 15, tzinfo=timezone.utc),
        ),
        Candidate(
            source_name="Automotive News",
            source_weight=10,
            headline="Penske Automotive Q1 net income up 6% on F&I per-vehicle gross gains",
            url="https://www.autonews.com/retail/penske-q1-2026-results",
            summary="Penske Automotive Group reported Q1 net income of $267M, up 6% YoY, driven by per-vehicle F&I gross profit gains of $112 across both new and used.",
            published=datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
        ),
        Candidate(
            source_name="CBT News",
            source_weight=9,
            headline="Survey: 62% of dealer BDC appointments lack qualifying data; close rate gap widens",
            url="https://www.cbtnews.com/bdc-qualification-survey-april-2026/",
            summary="A new operator survey of 412 U.S. franchised dealers found 62% of BDC-set appointments lacked at least two of three qualifying data points (budget, trade, credit comfort).",
            published=datetime(2026, 4, 19, 13, 45, tzinfo=timezone.utc),
        ),
        Candidate(
            source_name="NHTSA Recalls",
            source_weight=9,
            headline="NHTSA expands Stellantis recall to 1.4M Jeep Wrangler / Gladiator units over fuel pump driver",
            url="https://www.nhtsa.gov/recalls/stellantis-fuel-pump-driver-april-2026",
            summary="The expanded recall covers MY 2018-2024 Jeep Wrangler and Gladiator units. Dealers will be notified next week with parts allocation.",
            published=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
        ),
        Candidate(
            source_name="Tekion News",
            source_weight=8,
            headline="Tekion announces Q2 release: native CARS Rule disclosure flow + audit log export",
            url="https://www.tekion.com/news/q2-2026-release-cars-rule",
            summary="Tekion's Q2 platform release includes a native CARS Rule disclosure capture flow and an audit log export sized for FTC inquiry response.",
            published=datetime(2026, 4, 18, 17, 30, tzinfo=timezone.utc),
        ),
    ]
    with (settings.fixtures_dir / "candidates.json").open("w", encoding="utf-8") as f:
        json.dump([c.model_dump(mode="json") for c in sample], f, indent=2, default=str)
    print(f"Wrote {len(sample)} candidates to fixtures/candidates.json")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="load from fixtures instead of network")
    parser.add_argument("--seed-fixture", action="store_true", help="write a deterministic candidates.json")
    parser.add_argument("--since-hours", type=int, default=36)
    args = parser.parse_args()

    if args.seed_fixture:
        seed_fixture()
        return

    candidates = (
        fetch_candidates_from_fixture()
        if args.dry_run or settings.dry_run
        else fetch_candidates(since_hours=args.since_hours)
    )
    print(f"Got {len(candidates)} candidates")
    for c in candidates[:10]:
        print(f"  [{c.source_weight:2d}] {c.source_name:40s}  {c.headline[:80]}")


if __name__ == "__main__":
    main()
