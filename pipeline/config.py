"""Centralized config: env vars, paths, sane defaults.

Every module imports `settings` from here; we never read os.environ elsewhere.
This makes the dry-run + test paths tractable.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # Required at runtime (warned, not crashed, so dry-run still works)
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    beehiiv_api_key: str = field(default_factory=lambda: os.environ.get("BEEHIIV_API_KEY", ""))
    beehiiv_publication_id: str = field(default_factory=lambda: os.environ.get("BEEHIIV_PUBLICATION_ID", ""))

    # Optional — feature degrades gracefully when missing
    replicate_api_token: str = field(default_factory=lambda: os.environ.get("REPLICATE_API_TOKEN", ""))
    pexels_api_key: str = field(default_factory=lambda: os.environ.get("PEXELS_API_KEY", ""))
    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
    supabase_service_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SERVICE_KEY", ""))
    google_sheets_credentials_json: str = field(default_factory=lambda: os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", ""))
    google_sheets_spreadsheet_id: str = field(default_factory=lambda: os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", ""))

    # Behavior flags
    dry_run: bool = field(default_factory=lambda: _bool("DRY_RUN", False))

    # Paths
    sources_file: Path = field(default_factory=lambda: ROOT / os.environ.get("SOURCES_FILE", "sources.yaml"))
    system_prompt_file: Path = field(default_factory=lambda: ROOT / os.environ.get("SYSTEM_PROMPT_FILE", "prompts/system-prompt-v1.md"))
    issue_output_dir: Path = field(default_factory=lambda: ROOT / os.environ.get("ISSUE_OUTPUT_DIR", "issues"))
    data_dir: Path = field(default_factory=lambda: ROOT / "data")
    fixtures_dir: Path = field(default_factory=lambda: ROOT / "fixtures")

    # Models
    daily_model: str = "claude-sonnet-4-6"
    weekly_model: str = "claude-opus-4-6"

    # Ingestion
    max_stories_per_source: int = 5
    max_candidates_to_rank: int = 60
    target_stories_per_issue: int = 5  # editorial target

    def missing_required(self) -> list[str]:
        """Return env vars that must be set for a non-dry-run send."""
        missing = []
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not self.beehiiv_api_key:
            missing.append("BEEHIIV_API_KEY")
        if not self.beehiiv_publication_id:
            missing.append("BEEHIIV_PUBLICATION_ID")
        return missing


settings = Settings()
