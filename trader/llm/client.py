"""Claude wrapper that shells out to the Claude Code CLI.

Using the CLI instead of the Anthropic SDK lets the user reuse their Claude.ai
Pro/Max subscription rather than paying separately for Anthropic API credits.
It also sidesteps corporate TLS proxies that would otherwise block direct
calls to api.anthropic.com.

Requires:
- `claude` on PATH (https://claude.com/claude-code)
- `claude /login` already done with the personal Anthropic account
- That account NOT pointed at a corporate proxy (no ANTHROPIC_BASE_URL in env)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from loguru import logger

from trader.config import get_config


def call_claude(
    *,
    system: str,
    user: str,
    cache_system: bool = True,  # ignored — Claude Code manages its own caching
    json_response: bool = True,
    max_tokens: int = 2048,  # ignored — controlled by the CLI / model defaults
) -> dict[str, Any] | str:
    """Send a prompt to Claude via the Claude Code CLI.

    Returns parsed JSON if json_response=True, otherwise the raw text response.
    Raises RuntimeError if the `claude` CLI is missing or the call fails.
    """
    if not shutil.which("claude"):
        raise RuntimeError(
            "`claude` CLI not found on PATH. Install Claude Code "
            "(https://claude.com/claude-code), then run `claude /login` "
            "with your personal Anthropic account."
        )

    cfg = get_config()

    import tempfile

    # Write prompts to temp files to avoid Windows 32k command-line limit.
    sys_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8",
    )
    sys_file.write(system)
    sys_file.close()

    cmd = [
        "claude",
        "-p", "-",
        "--append-system-prompt-file", sys_file.name,
        "--output-format", "json",
        "--model", cfg.llm.model,
        "--max-turns", "1",
    ]

    env = {k: v for k, v in os.environ.items()
           if k not in {"ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"}}

    logger.debug("Calling claude CLI (model={})", cfg.llm.model)

    try:
        proc = subprocess.run(
            cmd, input=user, capture_output=True, text=True,
            timeout=120, check=False, env=env,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("claude CLI timed out after 120s") from e
    finally:
        try:
            os.unlink(sys_file.name)
        except OSError:
            pass

    # The CLI emits structured JSON even on API errors and exits non-zero,
    # so prefer parsing stdout over trusting the exit code.
    if not proc.stdout.strip():
        raise RuntimeError(
            f"claude CLI exited {proc.returncode} with empty stdout. "
            f"stderr: {(proc.stderr or '').strip()[:300]}"
        )

    try:
        wrapper = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"claude CLI returned non-JSON: {proc.stdout[:300]}"
        ) from e

    if wrapper.get("is_error"):
        raise RuntimeError(
            f"Claude API error (status={wrapper.get('api_error_status')}): "
            f"{(wrapper.get('result') or '')[:500]}"
        )

    text = (wrapper.get("result") or "").strip()

    usage = wrapper.get("usage") or {}
    if usage or "total_cost_usd" in wrapper:
        logger.debug(
            "Claude usage — input={}, output={}, cost_usd={}",
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            wrapper.get("total_cost_usd"),
        )

    if not json_response:
        return text

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
