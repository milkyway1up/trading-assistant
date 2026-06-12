"""Pick the right broker + data client based on `cfg.broker.provider`.

Callers should always go through here instead of importing concrete clients
directly — that's what keeps the rest of the app provider-agnostic.

Both factories memoize their result via `lru_cache` so a fresh client isn't
constructed on every API call. After saving new keys via the Settings panel
call `reset_clients()` so the next call picks up the new credentials.
"""
from __future__ import annotations

from functools import lru_cache

from loguru import logger

from trader.broker.base import BrokerClient, DataClient
from trader.config import get_config, get_secrets


def _alpaca_keys_for_mode(mode: str) -> tuple[str, str]:
    """Return (api_key, secret_key) for the requested mode, falling back to the
    legacy single-pair keys when the mode-specific keys are blank. Legacy keys
    are treated as paper credentials, matching the historical default."""
    secrets = get_secrets()
    if mode == "live":
        if secrets.alpaca_live_api_key and secrets.alpaca_live_secret_key:
            return secrets.alpaca_live_api_key, secrets.alpaca_live_secret_key
        return "", ""  # never silently fall back to paper keys for live
    if secrets.alpaca_paper_api_key and secrets.alpaca_paper_secret_key:
        return secrets.alpaca_paper_api_key, secrets.alpaca_paper_secret_key
    return secrets.alpaca_api_key, secrets.alpaca_secret_key


@lru_cache(maxsize=1)
def get_broker() -> BrokerClient:
    cfg = get_config()
    provider = cfg.broker.provider

    if provider == "alpaca":
        from trader.broker.alpaca import AlpacaBrokerClient

        mode = cfg.broker.mode
        api_key, secret = _alpaca_keys_for_mode(mode)
        logger.debug("Constructing AlpacaBrokerClient (mode={})", mode)
        return AlpacaBrokerClient(
            api_key=api_key,
            secret_key=secret,
            paper=(mode == "paper"),
        )

    if provider == "schwab":
        from trader.broker.schwab import SchwabBrokerClient

        return SchwabBrokerClient()

    raise ValueError(f"Unknown broker provider: {provider}")


@lru_cache(maxsize=1)
def get_data_client() -> DataClient:
    cfg = get_config()
    provider = cfg.broker.provider

    if provider == "alpaca":
        from trader.data.alpaca_data import AlpacaDataClient

        # Data API works for either key set — prefer paper since it's the safer
        # default and most users will have those configured first.
        api_key, secret = _alpaca_keys_for_mode("paper")
        if not api_key:
            api_key, secret = _alpaca_keys_for_mode(cfg.broker.mode)
        return AlpacaDataClient(api_key=api_key, secret_key=secret)

    if provider == "schwab":
        from trader.data.schwab_rest import SchwabRestDataClient

        return SchwabRestDataClient()

    raise ValueError(f"Unknown broker provider: {provider}")


def reset_clients() -> None:
    """Drop cached clients — call after saving new keys / changing provider."""
    get_broker.cache_clear()
    get_data_client.cache_clear()
