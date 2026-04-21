"""Analytics relay.

Pulls the previous day's post metrics from beehiiv API and persists them so the
next morning's prompt can read yesterday_analytics + rolling_baseline.

Two backends for state:
  1. Google Sheets (via Apps Script-compatible API) — production, matches the existing pattern
  2. Local data/analytics.json — dev / fallback

The 30-day rolling baseline is computed over whichever backend is active.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .models import IssueAnalytics
from .publish import BEEHIIV_BASE

log = logging.getLogger(__name__)

LOCAL_STATE = Path(settings.data_dir) / "analytics.json"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def fetch_post_stats(post_id: str) -> dict:
    if not (settings.beehiiv_api_key and settings.beehiiv_publication_id):
        raise RuntimeError("BEEHIIV_API_KEY required to fetch analytics")
    url = f"{BEEHIIV_BASE}/publications/{settings.beehiiv_publication_id}/posts/{post_id}"
    headers = {"Authorization": f"Bearer {settings.beehiiv_api_key}"}
    r = httpx.get(url, params={"expand[]": "stats"}, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json().get("data", {})


def parse_post_stats(post_id: str, raw: dict, sources_used: list[str]) -> IssueAnalytics:
    stats = raw.get("stats", {}) or {}
    email = stats.get("email", {}) or {}
    web = stats.get("web", {}) or {}
    sent_at_raw = raw.get("sent_at") or raw.get("scheduled_at")
    sent_at = (
        datetime.fromisoformat(sent_at_raw.replace("Z", "+00:00"))
        if sent_at_raw
        else datetime.now(timezone.utc)
    )
    recipients = int(email.get("recipients") or 0)
    opens = int(email.get("opens") or 0)
    clicks = int(email.get("clicks") or 0) + int(web.get("clicks") or 0)
    return IssueAnalytics(
        issue_date=sent_at.date().isoformat(),
        beehiiv_post_id=post_id,
        sent_at=sent_at,
        recipients=recipients,
        opens=opens,
        open_rate=(opens / recipients) if recipients else 0.0,
        clicks=clicks,
        click_rate=(clicks / recipients) if recipients else 0.0,
        unsubscribes=int(email.get("unsubscribes") or 0),
        bounces=int(email.get("bounces") or 0),
        sources_used=sources_used,
    )


# --- Local JSON state -------------------------------------------------------

def _load_local() -> list[IssueAnalytics]:
    if not LOCAL_STATE.exists():
        return []
    with LOCAL_STATE.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [IssueAnalytics.model_validate(r) for r in raw]


def _save_local(records: list[IssueAnalytics]) -> None:
    LOCAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    with LOCAL_STATE.open("w", encoding="utf-8") as f:
        json.dump([r.model_dump(mode="json") for r in records], f, indent=2, default=str)


# --- Google Sheets state ---------------------------------------------------

def _save_sheets(record: IssueAnalytics) -> bool:
    """Append a row to the analytics sheet. Returns True if persisted."""
    if not (settings.google_sheets_credentials_json and settings.google_sheets_spreadsheet_id):
        return False
    try:
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        info = json.loads(settings.google_sheets_credentials_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        row = [
            record.issue_date,
            record.beehiiv_post_id,
            record.recipients,
            record.opens,
            record.open_rate,
            record.clicks,
            record.click_rate,
            record.unsubscribes,
            record.bounces,
            ",".join(record.sources_used),
        ]
        svc.spreadsheets().values().append(  # type: ignore[attr-defined]
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range="analytics!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Sheets append failed: %s; falling back to local", exc)
        return False


def persist(record: IssueAnalytics) -> None:
    """Write the record. Sheets first, local always (so we always have a backup)."""
    _save_sheets(record)
    records = _load_local()
    records = [r for r in records if r.beehiiv_post_id != record.beehiiv_post_id]
    records.append(record)
    _save_local(records)


# --- Read-side: yesterday + rolling baseline -------------------------------

def yesterday_analytics() -> Optional[dict]:
    """Return the most recent analytics record as a dict, or None if there isn't one yet."""
    records = _load_local()
    if not records:
        return None
    latest = max(records, key=lambda r: r.issue_date)
    return latest.model_dump(mode="json")


def rolling_baseline_30d() -> dict:
    """Aggregate 30-day stats for the prompt's baseline reference."""
    records = _load_local()
    if not records:
        return {}
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    recent = [r for r in records if r.issue_date >= cutoff]
    if not recent:
        return {}
    n = len(recent)
    return {
        "issues_in_window": n,
        "avg_open_rate": sum(r.open_rate for r in recent) / n,
        "avg_click_rate": sum(r.click_rate for r in recent) / n,
        "avg_recipients": sum(r.recipients for r in recent) / n,
        "total_unsubscribes": sum(r.unsubscribes for r in recent),
    }


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-id", help="beehiiv post id to fetch + persist")
    args = parser.parse_args()
    if args.post_id:
        raw = fetch_post_stats(args.post_id)
        rec = parse_post_stats(args.post_id, raw, sources_used=[])
        persist(rec)
        print(f"Persisted: {rec.model_dump_json(indent=2)}")
    else:
        print("Yesterday:", yesterday_analytics())
        print("30-day baseline:", rolling_baseline_30d())


if __name__ == "__main__":
    main()
