"""Shared Claude wrapper used by every module that calls the API.

Centralizes: client construction, model selection, retry, and JSON-response parsing.

`call_json()` is the canonical helper — it asks Claude for a JSON object, parses
robustly (handles ``` fences and stray prose), and validates against an optional
Pydantic model.

There is no dry-run path here; callers MUST decide whether to call this or use
their deterministic fallback. We keep this module side-effect-free in dry-run.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional, Type, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        stripped = "\n".join(lines)
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and last > first:
        stripped = stripped[first : last + 1]
    return stripped


def parse_json_response(text: str) -> dict[str, Any]:
    return json.loads(_strip_fences(text))


def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=settings.anthropic_api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def call_text(*, system: str, user: str, model: Optional[str] = None, max_tokens: int = 4096) -> str:
    """Run one prompt → return assistant text. Retries on transient errors."""
    client = _client()
    resp = client.messages.create(
        model=model or settings.daily_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text  # type: ignore[union-attr]


def call_json(*, system: str, user: str, model: Optional[str] = None, max_tokens: int = 4096) -> dict[str, Any]:
    """Run one prompt → return parsed JSON dict."""
    return parse_json_response(call_text(system=system, user=user, model=model, max_tokens=max_tokens))


def call_validated(
    schema: Type[T],
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    max_tokens: int = 4096,
) -> T:
    """Run one prompt → return the response validated against `schema`."""
    raw = call_json(system=system, user=user, model=model, max_tokens=max_tokens)
    return schema.model_validate(raw)
