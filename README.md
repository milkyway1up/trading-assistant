# Trading Assistant

Personal swing-trading assistant for a Schwab cash account. Runs locally on your Mac.

- **Browser dashboard** at `localhost:8765` with TradingView-style candlestick charts (Daily / 4H / 1H / 15m), watchlist, indicators, and live alerts.
- **CLI** for scanning setups, running LLM analysis (`trader analyze TSLA`), generating weekly prep docs (`trader prep`), submitting orders, and journal management.
- **Schwab API** for live data + order execution (cash account; PDT-free).
- **Anthropic Claude** for thesis generation, weekly research, and exit grading.
- **Trade journal** auto-populates from Schwab order history; Claude grades each closed trade against the entry thesis.

> ⚠ **This is a personal tool.** Always paper-trade your strategies first. The risk guard blocks the most common small-account mistakes (oversizing, too-wide stops, exceeding settled cash) but you are responsible for every trade.

---

## Quickstart

### 1. Install dependencies

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone / cd into this repo
cd ~/Desktop/mydocuments/github/trading-assistant

# Sync deps
uv sync
```

### 2. Configure secrets

```bash
cp env.example .env
cp config.example.yaml config.yaml
```

Edit `.env`:
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com). Required for LLM features.
- `SCHWAB_APP_KEY`, `SCHWAB_APP_SECRET` — from [developer.schwab.com](https://developer.schwab.com) after your app is approved (1–3 days). Required for live data + orders.

Edit `config.yaml`:
- `watchlist` — tickers to track
- `risk.*` — position sizing caps
- `alerts.rules` — your alert conditions

### 3. Run it

```bash
# LLM-only (works without Schwab):
uv run trader analyze AAPL
uv run trader prep

# After Schwab approval — initial OAuth dance (browser-based, ~30 sec):
uv run trader auth login

# Launch dashboard:
uv run trader serve
# → open http://localhost:8765
```

---

## Schwab account setup (one-time, do this first — has 1-3 day lead time)

1. **Open a Schwab cash account** at [schwab.com](https://www.schwab.com). Free, $0 minimum. **Pick a CASH account, not margin** — small accounts should avoid the PDT rule.
2. Once funded with even $1, register at [developer.schwab.com](https://developer.schwab.com) → "Individual Developer".
3. Create a new app:
   - Name: anything (e.g. "Personal Trading Assistant")
   - Product: **Trader API – Individual**
   - Callback URL: `https://127.0.0.1:8182`
4. Wait for approval (typically 1–3 business days).
5. When approved, copy the App Key + Secret into `.env`.
6. Run `uv run trader auth login` — opens a browser, you log in to Schwab, paste the redirect URL back into the prompt. Token is saved to `~/.config/trader/schwab_tokens.json`.
7. **Refresh tokens expire every 7 days** — the dashboard will warn you when re-auth is needed. Just re-run `trader auth login`.

---

## CLI reference

| Command | What it does |
|---|---|
| `trader serve` | Launches the web dashboard at `http://localhost:8765` |
| `trader auth login` | Schwab OAuth flow (browser-based) |
| `trader auth status` | Show token expiry |
| `trader analyze TSLA` | Claude reads news + bars and produces a structured thesis |
| `trader prep` | Generates a weekly research markdown doc in `prep/` |
| `trader scan` | Runs all setup detectors across the universe; ranks results |
| `trader order TSLA buy --risk 2% --entry 245 --stop 240 --target 260 --type bracket` | Preview + confirm + submit a bracket order |
| `trader journal sync` | Pull latest Schwab transactions into the journal |
| `trader journal annotate <id>` | Add reason/tags/notes to a trade |
| `trader journal stats --since 30d` | Win rate, R-multiple, expectancy, mistakes |
| `trader journal grade <id>` | Have Claude grade a closed trade against its entry thesis |
| `trader backtest <strategy> --ticker SPY` | Run a strategy on historical data |

---

## Project layout

```
trader/
├── cli.py                  # typer CLI entrypoint
├── config.py               # pydantic-settings
├── data/                   # Schwab REST/WS + yfinance fallback
├── indicators/             # pandas-ta wrappers + S/R levels
├── setups/                 # swing-trade setup detectors (breakout, flag, pullback, ...)
├── scanner/                # universe + ranked setup scan
├── alerts/                 # rule engine + audio/desktop/browser notifiers
├── broker/                 # Schwab client + auth + orders + risk_guard + settlement
├── sizing/                 # position-size calculator
├── llm/                    # Anthropic client + analysis + prep + grading
├── backtest/               # vectorbt wrapper + sample strategies
├── journal/                # SQLAlchemy models + Schwab sync + analytics
└── web/                    # FastAPI server + dashboard HTML/JS
```

---

## Out of scope

- Fidelity automation (no usable API)
- Crypto, futures, complex options strategies
- Mobile app or remote access (localhost only — Schwab tokens live behind it)
- Fully autonomous trading (every order requires confirm)
