# Trading Assistant

Personal swing-trading assistant. Runs locally on **macOS, Windows, or Linux**.

- **Browser dashboard** at `localhost:8765` with TradingView-style candlestick charts (Daily / 4H / 1H / 15m), watchlist, indicators, and live alerts.
- **In-app Settings panel** — paste API keys, edit watchlist, tune risk caps without touching `.env` or YAML files.
- **CLI** for scanning setups, running LLM analysis (`trader analyze TSLA`), generating weekly prep docs (`trader prep`), submitting orders, and journal management.
- **Two broker backends, same UI:**
  - **Alpaca** (default) — instant signup, free paper trading, fractional shares. Trade today.
  - **Schwab cash account** — live data + order execution once the developer.schwab.com app is approved (1–3 business days). PDT-free.
  - Switched via one line in `config.yaml`: `broker.provider: alpaca` or `schwab`.
- **Claude (via Claude Code CLI)** for thesis generation, weekly research, and exit grading — uses your Claude.ai Pro/Max subscription, not separate API credits.
- **Trade journal** auto-populates from broker order history; Claude grades each closed trade against the entry thesis.

> ⚠ **This is a personal tool.** Always paper-trade your strategies first. The risk guard blocks the most common small-account mistakes (oversizing, too-wide stops, exceeding settled cash) but you are responsible for every trade.

---

## Quickstart

### 1. Install Claude Code

`trader analyze`, `trader prep`, and `trader journal grade` shell out to the Claude Code CLI — that lets the tool reuse your Claude.ai Pro/Max subscription instead of paying separately for Anthropic API credits.

- **macOS / Linux**: install per [claude.com/claude-code](https://claude.com/claude-code).
- **Windows**: native installer at [claude.com/claude-code](https://claude.com/claude-code).

Then sign in with your **personal** Anthropic account (the one your subscription is on):

```bash
claude /login
```

Verify it works: `claude -p "say hello"` should print a reply.

> If your Claude Code is configured against a corporate proxy (e.g., a work-issued LiteLLM endpoint), the trading assistant strips the relevant `ANTHROPIC_*` env vars from its subprocesses so it always uses your personal `claude /login` session.

### 2. Install uv + clone the repo

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/milkyway1up/trading-assistant.git
cd trading-assistant
uv sync
```

**Windows (PowerShell):**
```powershell
irm https://astral.sh/uv/install.ps1 | iex
git clone https://github.com/milkyway1up/trading-assistant.git
cd trading-assistant
uv sync
```

### 3. Run it

```bash
# Launch dashboard in a browser tab
uv run trader serve
# → open http://localhost:8765

# Or launch as a native window (no browser tab):
uv run trader desktop
```

Then click the ⚙ icon in the header to:
- Paste your Schwab API keys (when approval lands)
- Edit your watchlist
- Tune risk caps

### 4. Smoke-test the LLM path

```bash
uv run trader analyze SPY
```

Should print a structured JSON thesis. Cost is metered against your Claude subscription, not API credits.

### 5. (Optional, macOS only) Build a standalone `.app`

```bash
uv sync --group app
uv run python setup_app.py py2app
# → dist/Trading Assistant.app
```

Drag `dist/Trading Assistant.app` to `/Applications`. Double-click to launch — no terminal, no `uv run`.

---

## Alpaca account setup (instant — start here)

Alpaca is the **default broker**. No approval wait, free paper trading from minute one, same SDK switches to live trading later.

1. Sign up at [alpaca.markets](https://alpaca.markets) — instant, no funding required to start paper trading.
2. In the Alpaca dashboard: **Paper Trading → API Keys → Generate**.
3. Open Settings (⚙) in the trading assistant dashboard and paste the **Alpaca API Key + Secret Key**.
4. Run `uv run trader auth status` — should show `status: ok` with your account equity.
5. Trade away. Paper-trading orders go through the same code path as live orders; the only difference is `broker.paper: true` in `config.yaml`.

**Going live (later):**
- Generate **Live Trading** API keys in Alpaca.
- Replace the paper keys in Settings.
- Flip `broker.paper: false` in `config.yaml`.

---

## Schwab account setup (optional, 1–3 day lead time)

Skip this section if you're sticking with Alpaca. Set `broker.provider: schwab` in `config.yaml` once you've completed the steps below.

1. **Open a Schwab cash account** at [schwab.com](https://www.schwab.com). Free, $0 minimum. **Pick a CASH account, not margin** — small accounts should avoid the PDT rule.
2. Once funded with even $1, register at [developer.schwab.com](https://developer.schwab.com) → "Individual Developer".
3. Create a new app:
   - Name: anything (e.g. "Personal Trading Assistant")
   - Product: **Trader API – Individual**
   - Callback URL: `https://127.0.0.1:8182`
4. Wait for approval (typically 1–3 business days).
5. When approved, paste the App Key + Secret into the dashboard's Settings panel (⚙).
6. Run `uv run trader auth login` — opens a browser, you log in to Schwab, paste the redirect URL back into the prompt. Token is saved to `~/.config/trader/schwab_tokens.json`.
7. **Refresh tokens expire every 7 days** — the dashboard will warn you when re-auth is needed. Just re-run `trader auth login`.

---

## Platform notes

### macOS

Everything works out of the box. If you're behind a corporate TLS proxy (Zscaler etc.), `trader/utils/ssl_setup.py` exports the macOS keychain to a PEM bundle so `yfinance` can validate `https://query1.finance.yahoo.com` correctly.

### Windows

- **WebView2 runtime**: required for `trader desktop`. Preinstalled on Windows 10/11 since 2022. If `trader desktop` errors on first launch:
  ```powershell
  winget install Microsoft.EdgeWebView2Runtime
  ```
- **Audio alerts** use SAPI (built into Windows) for text-to-speech and `winsound.MessageBeep` for the alert sound.
- **Desktop notifications** use the native `Windows.UI.Notifications` toast API via PowerShell — no extra modules required.

### Linux

- **Desktop notifications** use `notify-send` (libnotify, ships with most desktop environments).
- **Text-to-speech** tries `spd-say` then `espeak` then `espeak-ng`. Install one of them if you want spoken alerts (`sudo apt install speech-dispatcher` or `sudo apt install espeak`).
- **Sound playback** uses `paplay` (PulseAudio) then `aplay` (ALSA).

If a backend is missing on any platform, alerts degrade silently — no crashes — and other channels (browser toasts, the alerts feed in the dashboard) still fire.

---

## CLI reference

| Command | What it does |
|---|---|
| `trader serve` | Launches the web dashboard at `http://localhost:8765` |
| `trader desktop` | Same dashboard, but in a native window (no browser tab) |
| `trader auth login` | Authenticate the configured broker (Alpaca: validates keys; Schwab: OAuth browser flow) |
| `trader auth status` | Show broker auth state (account snapshot for Alpaca, token expiry for Schwab) |
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

## Configuration

Two files, both editable from the in-app Settings panel:

### `.env` (secrets)
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` — Alpaca paper or live keys
- `SCHWAB_APP_KEY`, `SCHWAB_APP_SECRET`, `SCHWAB_CALLBACK_URL` — Schwab developer app credentials (only if `broker.provider: schwab`)
- `SLACK_WEBHOOK_URL` — optional, for Slack alert delivery
- `ANTHROPIC_API_KEY` — **unused by default** (LLM path goes through Claude Code CLI). Reserved for a future SDK fallback.

### `config.yaml` (preferences)
- `watchlist` — tickers to track
- `broker.provider` — `alpaca` (default) or `schwab`
- `broker.paper` — Alpaca only; `true` = paper trading, `false` = live
- `risk.*` — position sizing caps (max risk per trade %, max position %, max stop distance %, default risk %)
- `llm.model` — which Claude model to invoke (default `claude-sonnet-4-6`)
- `alerts.rules` — your alert conditions (DSL evaluated each new bar)
- `audio.*`, `notifications.*` — alert channel toggles

`config.example.yaml` is the canonical template — `config.yaml` is git-ignored so user-specific settings don't leak.

---

## Project layout

```
trader/
├── cli.py                  # typer CLI entrypoint
├── desktop.py              # pywebview launcher (cross-platform)
├── config.py               # pydantic-settings + secret/config mutators
├── data/                   # Alpaca + Schwab REST/WS + yfinance fallback (DataClient ABC)
├── indicators/             # pandas-ta wrappers + S/R levels
├── setups/                 # swing-trade setup detectors (breakout, flag, pullback, ...)
├── scanner/                # universe + ranked setup scan
├── alerts/                 # rule engine + cross-platform audio/desktop/browser notifiers
├── broker/                 # BrokerClient ABC + Alpaca + Schwab + auth + orders + risk_guard + settlement + factory
├── sizing/                 # position-size calculator
├── llm/                    # Claude Code CLI wrapper + analysis + prep + grading
├── backtest/               # vectorbt wrapper + sample strategies
├── journal/                # SQLAlchemy models + Schwab sync + analytics
├── utils/                  # ssl_setup (macOS keychain export for corporate TLS)
└── web/                    # FastAPI server + dashboard HTML/JS + Settings panel
```

---

## How the LLM integration works

`trader analyze`, `trader prep`, and `trader journal grade` all call the same wrapper in `trader/llm/client.py`, which shells out to:

```
claude -p <prompt> --append-system-prompt <our_system> --output-format json --max-turns 1 --model <cfg.llm.model>
```

That:
- **Bills against your Claude subscription** (`claude /login`'d account), not the Anthropic API
- **Sidesteps corporate TLS proxies** that would otherwise block direct calls to `api.anthropic.com` — Claude Code already manages its own TLS path
- **Strips inherited `ANTHROPIC_*` env vars** from the subprocess so a corporate proxy config can't shadow your personal session
- **Returns structured JSON** which the wrapper parses, then unwraps any inner code-fenced JSON the model produced

The system prompts (analyst, weekly prep, exit grading) live in `trader/llm/prompts.py` — they're tuned to be skeptical, force structured output, and call out poor setups instead of manufacturing a thesis where there isn't one.

---

## Out of scope

- Fidelity automation (no usable API)
- Crypto, futures, complex options strategies
- Mobile app or remote access (localhost only — Schwab tokens live behind it)
- Fully autonomous trading (every order requires confirm)
- Multi-user / multi-account
