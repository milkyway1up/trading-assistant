"""Typed config: secrets from .env, app config from config.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Secrets(BaseSettings):
    """Loaded from .env at project root."""
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    schwab_app_key: str = ""
    schwab_app_secret: str = ""
    schwab_callback_url: str = "https://127.0.0.1:8182"
    slack_webhook_url: str = ""


class RiskConfig(BaseModel):
    max_risk_per_trade_pct: float = 2.0
    max_position_pct: float = 25.0
    max_stop_distance_pct: float = 8.0
    default_risk_pct: float = 1.0


class LLMConfig(BaseModel):
    model: str = "claude-sonnet-4-6"
    daily_cost_cap_usd: float = 2.00
    cache_system_prompt: bool = True


class AlertRule(BaseModel):
    name: str
    ticker: str
    timeframe: str = "daily"
    when: str
    cooldown_hours: float = 24.0


class AlertsConfig(BaseModel):
    rules: list[AlertRule] = Field(default_factory=list)


class ScannerConfig(BaseModel):
    universes: list[str] = Field(default_factory=lambda: ["watchlist"])
    min_dollar_volume: int = 5_000_000


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765


class AudioConfig(BaseModel):
    enabled: bool = True
    voice: str = "Samantha"
    sound_file: str = "/System/Library/Sounds/Glass.aiff"


class NotificationsConfig(BaseModel):
    desktop_enabled: bool = True
    browser_toast_enabled: bool = True
    slack_enabled: bool = False


class AppConfig(BaseModel):
    """Loaded from config.yaml at project root."""
    watchlist: list[str] = Field(default_factory=list)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_secrets() -> Secrets:
    return Secrets()


@lru_cache
def get_config() -> AppConfig:
    """Loads config.yaml if present, otherwise returns defaults."""
    yaml_path = PROJECT_ROOT / "config.yaml"
    raw = _load_yaml(yaml_path)
    return AppConfig(**raw)


def data_dir() -> Path:
    p = PROJECT_ROOT / "data"
    p.mkdir(exist_ok=True)
    return p


def prep_dir() -> Path:
    p = PROJECT_ROOT / "prep"
    p.mkdir(exist_ok=True)
    return p
