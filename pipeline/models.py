"""Typed data structures shared across pipeline stages.

Pydantic models give us cheap I/O serialization for fixtures + analytics + audit logs.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# --- Source list (sources.yaml) ----------------------------------------------

class Source(BaseModel):
    name: str
    category: str
    url: str
    rss: Optional[str] = None
    weight: int = 5
    update_frequency: Literal["daily", "weekly", "monthly", "event"] = "daily"
    notes: Optional[str] = None


class SourceList(BaseModel):
    version: int = 1
    niche: str
    last_verified: str
    sources: list[Source]

    @field_validator("last_verified", mode="before")
    @classmethod
    def _coerce_date_to_str(cls, v):
        # YAML auto-parses unquoted ISO dates as date objects; we keep it as string.
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v


# --- Candidate stories (after ingest) -----------------------------------------

class Candidate(BaseModel):
    """A story pulled from a source, before ranking."""
    source_name: str
    source_weight: int = 5
    headline: str
    url: str
    summary: str = ""
    published: Optional[datetime] = None

    # Computed by rank stage
    importance_score: float = 0.0
    novelty_score: float = 0.0
    final_rank: int = 0
    section_assignment: Optional[str] = None  # "compliance" | "fni" | "used-car" | "store-ops"

    @property
    def stable_id(self) -> str:
        """Deterministic ID for dedupe."""
        # Strip protocol, lowercase, take first 80 chars of url
        normalized = self.url.lower().replace("https://", "").replace("http://", "").rstrip("/")
        return normalized[:80]


# --- Issue output (after draft) ----------------------------------------------

class IssueSource(BaseModel):
    outlet: str
    url: str


class IssueStory(BaseModel):
    headline: str
    body: str
    action_line: str
    sources: list[IssueSource]
    source_ids: list[str] = Field(default_factory=list)


class IssueSection(BaseModel):
    # Daily issue sections + weekly meta-issue sections (last 4)
    name: Literal[
        "compliance", "fni", "used-car", "store-ops",
        "top-stories", "data-recap", "watch-next-week", "tool-of-week",
    ]
    stories: list[IssueStory]


class ToolOfDay(BaseModel):
    product_id: Optional[str] = None
    rationale: str = ""
    disclosure_tag: Literal["Sponsored", "Affiliate", "None"] = "None"


class GuardrailSelfCheck(BaseModel):
    two_source_min: bool
    no_financial_advice: bool
    no_political_take: bool
    quotes_under_25_words: bool
    all_numbers_sourced: bool


class IssueMetadata(BaseModel):
    story_count: int
    word_count_estimate: int
    sources_used: list[str] = Field(default_factory=list)
    affiliate_used: bool = False
    guardrail_self_check: GuardrailSelfCheck


class Issue(BaseModel):
    """The full output of pipeline/draft.py, ready for publish."""
    subject_a: str
    subject_b: str
    subject_c: str
    preheader: str
    issue_title: str
    cold_open: str
    sections: list[IssueSection]
    tool_of_day: ToolOfDay
    soft_footer: str
    hero_image_prompt: str
    metadata: IssueMetadata

    # Filled after image gen
    hero_image_url: Optional[str] = None

    # Filled after publish
    beehiiv_post_id: Optional[str] = None
    scheduled_send_at: Optional[datetime] = None

    dry_run: bool = False


# --- Affiliate inventory ----------------------------------------------------

class Affiliate(BaseModel):
    product_id: str
    product_name: str
    one_liner: str
    url: str
    semantic_tags: list[str] = Field(default_factory=list)
    disclosure_type: Literal["Sponsored", "Affiliate"] = "Affiliate"
    cpc_or_commission_note: str = ""
    active: bool = True


# --- Analytics --------------------------------------------------------------

class IssueAnalytics(BaseModel):
    issue_date: str  # YYYY-MM-DD
    beehiiv_post_id: str
    sent_at: datetime
    recipients: int = 0
    opens: int = 0
    open_rate: float = 0.0
    clicks: int = 0
    click_rate: float = 0.0
    unsubscribes: int = 0
    bounces: int = 0
    top_clicked_url: Optional[str] = None
    bottom_clicked_url: Optional[str] = None
    sources_used: list[str] = Field(default_factory=list)
