"""Schwab OAuth flow — browser-based login + token persistence.

Wired in Phase 0/1 once the developer.schwab.com app is approved.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from trader.config import get_secrets

TOKEN_PATH = Path.home() / ".config" / "trader" / "schwab_tokens.json"


def run_oauth_flow() -> None:
    """Run the schwab-py browser OAuth flow."""
    secrets = get_secrets()
    if not secrets.schwab_app_key or not secrets.schwab_app_secret:
        logger.error(
            "SCHWAB_APP_KEY / SCHWAB_APP_SECRET not set in .env — "
            "complete the developer.schwab.com app approval first."
        )
        return

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        from schwab.auth import easy_client
    except ImportError:
        logger.error("schwab-py not installed. Run `uv sync`.")
        return

    logger.info("Starting Schwab OAuth — a browser window will open...")
    client = easy_client(
        api_key=secrets.schwab_app_key,
        app_secret=secrets.schwab_app_secret,
        callback_url=secrets.schwab_callback_url,
        token_path=str(TOKEN_PATH),
    )
    TOKEN_PATH.chmod(0o600)
    logger.success("Token saved to {}", TOKEN_PATH)


def token_status() -> dict:
    """Return current token expiry info."""
    if not TOKEN_PATH.exists():
        return {"status": "no_token", "path": str(TOKEN_PATH), "hint": "Run `trader auth login`"}

    import json
    try:
        data = json.loads(TOKEN_PATH.read_text())
    except Exception as e:
        return {"status": "error", "error": str(e)}

    # schwab-py token format includes creation_timestamp + token blob
    return {
        "status": "present",
        "path": str(TOKEN_PATH),
        "created_at": data.get("creation_timestamp"),
        "note": "Refresh tokens expire 7 days after issuance. Re-run `trader auth login` if needed.",
    }


def refresh_token() -> None:
    """Force a refresh of the Schwab access token (Phase 1)."""
    logger.info("Token refresh — wired in Phase 1.")
