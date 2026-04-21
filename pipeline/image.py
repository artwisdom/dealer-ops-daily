"""Hero image generation.

Primary path: Replicate Flux Schnell from issue.hero_image_prompt.
Fallback (no REPLICATE_API_TOKEN): Pexels stock query derived from the prompt.
Final fallback: a static placeholder URL.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings

log = logging.getLogger(__name__)

_PLACEHOLDER_URL = "https://placehold.co/1200x630/0f172a/f59e0b?text=Dealer+Ops+Daily"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _replicate_flux(prompt: str) -> Optional[str]:
    if not settings.replicate_api_token:
        return None
    try:
        # Lazy import — replicate is optional
        import replicate  # type: ignore
    except ImportError:
        log.warning("replicate not installed; skipping Flux")
        return None

    client = replicate.Client(api_token=settings.replicate_api_token)
    output = client.run(
        "black-forest-labs/flux-schnell",
        input={
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "num_outputs": 1,
            "output_format": "jpg",
            "output_quality": 90,
        },
    )
    # Replicate returns a list of URLs (or FileOutput objects)
    if not output:
        return None
    first = output[0]
    return str(first) if hasattr(first, "__str__") else first


def _pexels_search(prompt: str) -> Optional[str]:
    if not settings.pexels_api_key:
        return None
    # Reduce the prompt to a 2-3 word search query
    keyword = _prompt_to_keyword(prompt)
    try:
        r = httpx.get(
            "https://api.pexels.com/v1/search",
            params={"query": keyword, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": settings.pexels_api_key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        photos = data.get("photos") or []
        if photos:
            return photos[0]["src"]["large2x"]
    except Exception as exc:  # noqa: BLE001
        log.warning("Pexels fallback failed: %s", exc)
    return None


def _prompt_to_keyword(prompt: str) -> str:
    """Heuristic — pick the most concrete noun phrase in the prompt for stock search."""
    lowered = prompt.lower()
    for term in ("car dealership", "auto dealer", "showroom", "automobile", "automotive"):
        if term in lowered:
            return term
    return "auto dealership"


def generate_hero_image(prompt: str, *, dry_run: bool = False) -> str:
    """Return a publicly accessible image URL for the issue hero.

    Order of attempts: Flux → Pexels → placeholder. Dry-run always returns the placeholder
    so we never spend on image gen during testing.
    """
    if dry_run:
        return _PLACEHOLDER_URL

    flux_url = _replicate_flux(prompt)
    if flux_url:
        return flux_url

    pexels_url = _pexels_search(prompt)
    if pexels_url:
        return pexels_url

    log.warning("Hero image generation fell through all paths; using placeholder")
    return _PLACEHOLDER_URL


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="Editorial illustration of a clean modern auto dealership at dawn")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    url = generate_hero_image(args.prompt, dry_run=args.dry_run or settings.dry_run)
    print(f"Hero image URL: {url}")


if __name__ == "__main__":
    main()
