"""Broker authentication.

Two paths:
- Schwab: browser OAuth (schwab-py easy_client). Tokens persisted to disk;
  refresh-token expiry is 7 days.
- Alpaca: API key + secret. No OAuth, no token file. We "auth" by hitting
  /v2/account once to confirm the keys are valid.

The CLI / Settings panel call `run_auth()` and `auth_status()`; both branch on
`cfg.broker.provider`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from trader.config import get_config, get_secrets

TOKEN_PATH = Path.home() / ".config" / "trader" / "schwab_tokens.json"


# ─────────────────────────────────────────────────────────────────
# Public entrypoints — branch on provider
# ─────────────────────────────────────────────────────────────────

def run_auth() -> dict[str, Any]:
    """Run the auth flow appropriate for the configured broker."""
    cfg = get_config()
    if cfg.broker.provider == "alpaca":
        return _alpaca_validate()
    return _schwab_oauth()


def auth_status() -> dict[str, Any]:
    """Return current auth/connectivity status for the configured broker."""
    cfg = get_config()
    if cfg.broker.provider == "alpaca":
        return _alpaca_status()
    return _schwab_token_status()


# ─────────────────────────────────────────────────────────────────
# Alpaca
# ─────────────────────────────────────────────────────────────────

def _alpaca_validate() -> dict[str, Any]:
    """Hit /v2/account to confirm the keys work. No token file to write."""
    secrets = get_secrets()
    if not secrets.alpaca_api_key or not secrets.alpaca_secret_key:
        return {
            "broker": "alpaca",
            "status": "missing_keys",
            "hint": "Generate paper-trading keys at alpaca.markets, then "
                    "paste into the Settings panel (or .env).",
        }

    try:
        from trader.broker.factory import get_broker, reset_clients

        reset_clients()  # in case keys were just saved
        client = get_broker()
        account = client.get_account()
    except Exception as e:
        logger.error("Alpaca auth failed: {}", e)
        return {"broker": "alpaca", "status": "error", "error": str(e)}

    return {
        "broker": "alpaca",
        "status": "ok",
        "paper": account.get("paper"),
        "account_id": account.get("id"),
        "equity": account.get("equity"),
        "cash": account.get("cash"),
    }


def _alpaca_status() -> dict[str, Any]:
    secrets = get_secrets()
    if not secrets.alpaca_api_key or not secrets.alpaca_secret_key:
        return {
            "broker": "alpaca",
            "status": "missing_keys",
            "hint": "Paste ALPACA_API_KEY + ALPACA_SECRET_KEY in the Settings panel.",
        }
    return _alpaca_validate()


# ─────────────────────────────────────────────────────────────────
# Schwab (Phase 1+ — uses browser OAuth)
# ─────────────────────────────────────────────────────────────────

def _schwab_oauth() -> dict[str, Any]:
    """Run the schwab-py browser OAuth flow."""
    secrets = get_secrets()
    if not secrets.schwab_app_key or not secrets.schwab_app_secret:
        msg = ("SCHWAB_APP_KEY / SCHWAB_APP_SECRET not set — complete "
               "developer.schwab.com app approval first.")
        logger.error(msg)
        return {"broker": "schwab", "status": "missing_keys", "hint": msg}

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        from schwab.auth import easy_client
    except ImportError:
        return {"broker": "schwab", "status": "error",
                "error": "schwab-py not installed. Run `uv sync`."}

    logger.info("Starting Schwab OAuth — a browser window will open...")
    easy_client(
        api_key=secrets.schwab_app_key,
        app_secret=secrets.schwab_app_secret,
        callback_url=secrets.schwab_callback_url,
        token_path=str(TOKEN_PATH),
    )
    TOKEN_PATH.chmod(0o600)
    logger.success("Token saved to {}", TOKEN_PATH)
    return {"broker": "schwab", "status": "ok", "token_path": str(TOKEN_PATH)}


def _schwab_token_status() -> dict[str, Any]:
    if not TOKEN_PATH.exists():
        return {"broker": "schwab", "status": "no_token",
                "path": str(TOKEN_PATH), "hint": "Run `trader auth login`"}

    import json
    try:
        data = json.loads(TOKEN_PATH.read_text())
    except Exception as e:
        return {"broker": "schwab", "status": "error", "error": str(e)}

    return {
        "broker": "schwab",
        "status": "present",
        "path": str(TOKEN_PATH),
        "created_at": data.get("creation_timestamp"),
        "note": "Refresh tokens expire 7 days after issuance. Re-run `trader auth login` if needed.",
    }


def refresh_token() -> None:
    """Force a refresh of the Schwab access token (Phase 1)."""
    logger.info("Token refresh — wired in Phase 1.")


# ─────────────────────────────────────────────────────────────────
# Backwards-compat wrappers (older code paths import these by name)
# ─────────────────────────────────────────────────────────────────

def run_oauth_flow() -> None:
    """Deprecated — use `run_auth()`. Kept so existing CLI imports don't break."""
    run_auth()


def token_status() -> dict[str, Any]:
    """Deprecated — use `auth_status()`."""
    return auth_status()
