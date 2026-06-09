"""Anthropic client wrapper with prompt caching."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from anthropic import Anthropic
from loguru import logger

from trader.config import get_config, get_secrets


@lru_cache
def get_client() -> Anthropic:
    secrets = get_secrets()
    if not secrets.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Copy env.example to .env and fill in your key."
        )
    return Anthropic(api_key=secrets.anthropic_api_key)


def call_claude(
    *,
    system: str,
    user: str,
    cache_system: bool = True,
    json_response: bool = True,
    max_tokens: int = 2048,
) -> dict[str, Any] | str:
    """Send a prompt to Claude. Caches the system block when long enough.

    Returns parsed JSON if json_response=True, otherwise raw text.
    """
    client = get_client()
    cfg = get_config()

    system_blocks: list[dict[str, Any]] = [{"type": "text", "text": system}]
    # Anthropic requires cached blocks be ≥1024 tokens (~4K chars) to be eligible.
    # We always tag it; the API ignores the cache flag if the block is too small.
    if cache_system and cfg.llm.cache_system_prompt:
        system_blocks[0]["cache_control"] = {"type": "ephemeral"}

    response = client.messages.create(
        model=cfg.llm.model,
        max_tokens=max_tokens,
        system=system_blocks,
        messages=[{"role": "user", "content": user}],
    )

    text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    ).strip()

    usage = getattr(response, "usage", None)
    if usage:
        logger.debug(
            "Claude usage — input={}, output={}, cache_read={}, cache_create={}",
            getattr(usage, "input_tokens", 0),
            getattr(usage, "output_tokens", 0),
            getattr(usage, "cache_read_input_tokens", 0),
            getattr(usage, "cache_creation_input_tokens", 0),
        )

    if not json_response:
        return text

    # Strip code fences if Claude wrapped its JSON
    cleaned = text
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("Claude returned non-JSON: {}", text[:300])
        return {"error": "non_json_response", "raw": text, "parse_error": str(e)}
