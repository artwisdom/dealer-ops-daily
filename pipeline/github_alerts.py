"""GitHub Issues alert helper — used by self-improvement loops to surface
non-actionable findings to the operator without needing email.

Auth: in CI, GITHUB_TOKEN is provided automatically. Locally, you can set
GITHUB_TOKEN + GITHUB_REPOSITORY in .env to test issue creation.

If neither is set, alerts log to stdout (still useful in dev).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)


def open_issue(title: str, body: str, labels: Optional[list[str]] = None) -> Optional[str]:
    """Create a GitHub Issue. Returns the issue URL, or None if not configured."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/name", auto-set in Actions
    if not (token and repo):
        log.info("[ALERT — would file GH issue] %s\n%s", title, body)
        return None

    r = httpx.post(
        f"https://api.github.com/repos/{repo}/issues",
        json={"title": title, "body": body, "labels": labels or ["needs-triage"]},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=15,
    )
    r.raise_for_status()
    url = r.json().get("html_url")
    log.info("Filed GH issue: %s", url)
    return url
