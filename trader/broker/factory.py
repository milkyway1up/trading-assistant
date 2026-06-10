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


@lru_cache(maxsize=1)
def get_broker() -> BrokerClient:
    cfg = get_config()
    secrets = get_secrets()
    provider = cfg.broker.provider

    if provider == "alpaca":
        from trader.broker.alpaca import AlpacaBrokerClient

        logger.debug("Constructing AlpacaBrokerClient (paper={})", cfg.broker.paper)
        return AlpacaBrokerClient(
            api_key=secrets.alpaca_api_key,
            secret_key=secrets.alpaca_secret_key,
            paper=cfg.broker.paper,
        )

    if provider == "schwab":
        from trader.broker.schwab import SchwabBrokerClient

        return SchwabBrokerClient()

    raise ValueError(f"Unknown broker provider: {provider}")


@lru_cache(maxsize=1)
def get_data_client() -> DataClient:
    cfg = get_config()
    secrets = get_secrets()
    provider = cfg.broker.provider

    if provider == "alpaca":
        from trader.data.alpaca_data import AlpacaDataClient

        return AlpacaDataClient(
            api_key=secrets.alpaca_api_key,
            secret_key=secrets.alpaca_secret_key,
        )

    if provider == "schwab":
        from trader.data.schwab_rest import SchwabRestDataClient

        return SchwabRestDataClient()

    raise ValueError(f"Unknown broker provider: {provider}")


def reset_clients() -> None:
    """Drop cached clients — call after saving new keys / changing provider."""
    get_broker.cache_clear()
    get_data_client.cache_clear()
