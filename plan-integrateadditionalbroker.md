# Alpaca Broker Integration Plan

## Context

Schwab API approval takes 1-3 business days. Alpaca is an API-first broker with instant API key provisioning — adding it as an alternative broker lets you trade (or paper trade) today. The existing broker layer in `trader/broker/` is fully stubbed with `NotImplementedError` placeholders and clear method signatures, so this is a clean integration point.

## Approach

Introduce a broker abstraction (ABC) and implement Alpaca as the first concrete broker, keeping Schwab stubs intact for future completion.

---

## Files to Create

### 1. `trader/broker/base.py` — Broker ABC

Abstract base class extracted from the method signatures already in `schwab.py`:

```python
class BrokerClient(ABC):
    def get_account(self) -> dict  # {equity, cash, settled_cash, unsettled_cash}
    def get_positions(self) -> list[dict]  # [{ticker, qty, avg_price, market_value, unrealized_pl}]
    def get_position(ticker) -> Optional[dict]
    def get_open_orders(self) -> list[dict]
    def get_filled_orders(since) -> list[dict]
    def place_order(order_spec: dict) -> dict
    def cancel_order(order_id: str) -> dict
    def replace_order(order_id: str, new_spec: dict) -> dict
```

Also define a `DataClient(ABC)` for price data:

```python
class DataClient(ABC):
    def get_price_history(ticker, timeframe, period) -> pd.DataFrame
    def get_quote(ticker) -> dict  # {price, change, change_pct, volume}
    async def start_stream(tickers: list[str]) -> AsyncIterator[dict]
```

### 2. `trader/broker/alpaca.py` — Alpaca Broker Client

Implements `BrokerClient` using `alpaca-py` SDK:
- `AlpacaBrokerClient(api_key, secret_key, paper=True)`
- Maps Alpaca account/position/order responses to the same dict format Schwab stubs define
- Supports `paper=True` (default) for instant paper trading, `paper=False` for live
- Bracket orders via Alpaca's OTO (one-triggers-other) API

### 3. `trader/data/alpaca_data.py` — Alpaca Data Client

Implements `DataClient` using Alpaca's market data API:
- Historical bars (daily, hourly, 15m) from Alpaca's free IEX feed or paid SIP feed
- Real-time quotes via Alpaca WebSocket streaming
- Falls back to yfinance if Alpaca data is unavailable

### 4. `trader/broker/factory.py` — Broker Factory

```python
def get_broker() -> BrokerClient:
    cfg = get_config()
    if cfg.broker.provider == "alpaca":
        return AlpacaBrokerClient(...)
    elif cfg.broker.provider == "schwab":
        return SchwabBrokerClient(...)
    raise ValueError(f"Unknown broker: {cfg.broker.provider}")
```

Same pattern for `get_data_client()`.

---

## Files to Modify

### 5. `trader/config.py` — Add broker config

Add a `BrokerConfig` model:

```python
class BrokerConfig(BaseModel):
    provider: Literal["schwab", "alpaca"] = "alpaca"
    paper: bool = True  # Alpaca paper trading mode
```

Add to `Secrets`:
- `ALPACA_API_KEY: str = ""`
- `ALPACA_SECRET_KEY: str = ""`

Add `broker: BrokerConfig = BrokerConfig()` to `AppConfig`.

### 6. `config.example.yaml` — Add broker section

```yaml
broker:
  provider: alpaca   # schwab or alpaca
  paper: true        # Alpaca paper trading (use api-paper keys)
```

### 7. `trader/broker/schwab.py` — Implement BrokerClient ABC

Make the existing stub class extend `BrokerClient`. No logic changes — just adds the `(BrokerClient)` base class so both brokers share the interface.

### 8. `trader/broker/auth.py` — Add Alpaca auth path

Alpaca uses API key/secret (no OAuth flow needed). Add:
- `alpaca_auth_status()` — verify keys work by hitting `/v2/account`
- Update `run_oauth_flow()` to check `cfg.broker.provider` and skip OAuth for Alpaca

### 9. `trader/broker/orders.py` — Broker-agnostic order builders

Update order builder functions to return a broker-neutral dict spec. The broker client's `place_order()` translates it to Schwab or Alpaca format.

### 10. `trader/data/schwab_rest.py` / `trader/data/schwab_stream.py`

Make these extend `DataClient` ABC. No logic changes — just adds the base class.

### 11. `trader/web/api/quotes.py` — Use data client factory

Replace direct yfinance calls with `get_data_client().get_price_history()`, falling back to yfinance when no broker data client is configured.

### 12. `trader/web/api/settings.py` — Expose Alpaca key status

Add `alpaca_api_key_set` and `alpaca_secret_key_set` booleans to `SecretsView`. Add broker provider to settings GET/POST.

### 13. `trader/web/api/stream.py` — Use data client for live ticks

Replace mock ticker with `get_data_client().start_stream()` when broker is configured.

### 14. `trader/llm/analysis.py` — Use broker factory

Change `from trader.broker.schwab import get_position` to `from trader.broker.factory import get_broker`, then call `get_broker().get_position(ticker)`.

### 15. `trader/cli.py` — Add `auth status` for Alpaca

Update `auth_login` to handle Alpaca (just validates keys, no OAuth). Update `auth_status` to show Alpaca connection status.

### 16. `pyproject.toml` — Add alpaca-py dependency

Add `"alpaca-py>=0.33"` to dependencies.

### 17. `env.example` — Add Alpaca keys

```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
```

---

## Implementation Order

1. **Add `alpaca-py` dep + config changes** (pyproject.toml, config.py, config.example.yaml, env.example)
2. **Create `trader/broker/base.py`** — ABC definitions
3. **Create `trader/broker/factory.py`** — broker/data client factory
4. **Create `trader/broker/alpaca.py`** — Alpaca broker client (account, positions, orders)
5. **Create `trader/data/alpaca_data.py`** — Alpaca data client (bars, quotes, streaming)
6. **Update existing Schwab files** to extend ABCs (schwab.py, schwab_rest.py, schwab_stream.py)
7. **Update auth.py** — Alpaca key validation path
8. **Update orders.py** — broker-neutral order specs
9. **Wire up web API** (quotes.py, settings.py, stream.py) to use factories
10. **Wire up LLM** (analysis.py) to use broker factory
11. **Update CLI** (cli.py) for Alpaca auth flow
12. **Update README.md** — Alpaca quickstart section

---

## Verification

1. `uv sync` — confirm alpaca-py installs
2. `uv run trader auth status` — should show Alpaca connection status after pasting keys
3. `uv run trader serve` — dashboard should load with Alpaca data
4. `uv run trader analyze TSLA --with-position` — should pull Alpaca position if one exists
5. Paper trade: place a limit order via CLI, confirm it appears in Alpaca dashboard
6. Run existing tests: `uv run pytest` — nothing should break

---

## Alpaca Account Setup

1. Sign up at [alpaca.markets](https://alpaca.markets) — instant, free
2. Go to Paper Trading → API Keys → Generate
3. Paste `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` into the dashboard Settings panel (or `.env`)
4. Start paper trading immediately
5. When ready for live: generate live API keys, set `broker.paper: false` in config.yaml
