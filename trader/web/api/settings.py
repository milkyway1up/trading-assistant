"""Settings API: read+write config.yaml and .env from the in-app panel."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from trader.config import (
    AppConfig, get_config, get_secrets, save_config, save_secrets,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class SecretsView(BaseModel):
    """Never returns actual secret values to the client — only whether each is set."""
    anthropic_api_key_set: bool
    schwab_app_key_set: bool
    schwab_app_secret_set: bool
    schwab_callback_url: str  # not really a secret; safe to round-trip
    slack_webhook_url_set: bool


class SecretsUpdate(BaseModel):
    """All fields optional. Empty string clears a value; missing field leaves it."""
    anthropic_api_key: str | None = None
    schwab_app_key: str | None = None
    schwab_app_secret: str | None = None
    schwab_callback_url: str | None = None
    slack_webhook_url: str | None = None


@router.get("")
async def get_settings() -> dict[str, Any]:
    s = get_secrets()
    return {
        "secrets": SecretsView(
            anthropic_api_key_set=bool(s.anthropic_api_key),
            schwab_app_key_set=bool(s.schwab_app_key),
            schwab_app_secret_set=bool(s.schwab_app_secret),
            schwab_callback_url=s.schwab_callback_url,
            slack_webhook_url_set=bool(s.slack_webhook_url),
        ).model_dump(),
        "config": get_config().model_dump(),
    }


@router.post("/secrets")
async def update_secrets(body: SecretsUpdate) -> dict[str, str]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"status": "noop"}
    try:
        save_secrets(updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "updated": list(updates.keys())}


class ConfigUpdate(BaseModel):
    """Partial AppConfig — any subset of top-level keys."""
    watchlist: list[str] | None = None
    risk: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None
    alerts: dict[str, Any] | None = None
    scanner: dict[str, Any] | None = None
    server: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    notifications: dict[str, Any] | None = None


@router.post("/config")
async def update_config(body: ConfigUpdate) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"status": "noop", "config": get_config().model_dump()}
    try:
        new_cfg = save_config(updates)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    return {"status": "ok", "config": new_cfg.model_dump()}
