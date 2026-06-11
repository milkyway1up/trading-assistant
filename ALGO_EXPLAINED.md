# Algo Explained — How the Scanner Picks Setups & What Claude Reads

This is a complete walkthrough of how candidate trades end up in the **Setups** sidebar
of the dashboard, and what Claude actually sees when you click **Analyze**, **rate** the
top setups, generate a **weekly prep**, or **grade** a closed trade.

Everything below is grounded in the code. Line references point at the implementation
in case you want to tweak a threshold or the exact prompt.

---

## 1. The pick pipeline at a glance

```
                                                              ┌────────────────────┐
                                                              │ Setups sidebar UI  │
                                                              │ (sorted by         │
                                                              │  confidence × R:R) │
                                                              └─────────▲──────────┘
                                                                        │ JSON
                                                                        │
          ┌──────────────────┐    bars     ┌────────────────────┐    candidates
          │ universe.py      ├────────────►│ run_scan()         ├──────────────►
          │ S&P/QQQ + your   │             │ scanner/runner.py  │
          │ watchlist        │             │                    │
          └──────────────────┘             │ for each ticker:   │
                                           │   for each setup:  │
                                           │     detect(df)     │
                                           │ filter + sort      │
                                           └────────────────────┘
```

The scanner is **purely mechanical** — it doesn't know about news, earnings, sentiment, or
macro. It just looks at recent OHLCV and EMAs/RSI/ATR and asks each detector "is this
pattern present right now?" Claude is layered on top via the **rate** button to add the
context the scanner can't see.

---

## 2. The universe

`trader/scanner/universe.py:8` — the starter universe is hard-coded mega-caps:

> AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, AVGO, AMD, NFLX, CRM, ORCL, ADBE, QCOM,
> INTC, CSCO, JPM, V, MA, BAC, WFC, GS, MS, UNH, JNJ, LLY, PFE, MRK, ABBV, WMT, COST,
> HD, LOW, TGT, MCD, SBUX, NKE, XOM, CVX, COP, CAT, DE, BA, LMT, RTX, GE, DIS, T, VZ,
> CMCSA, SPY, QQQ, IWM, DIA

Your `watchlist` from `config.yaml` is **unioned** with this list (no duplicates). So
adding tickers in the Settings → Watchlist tab grows the scanned universe.

When the user adds it, the comment in `universe.py:6` says the plan is to swap the
hard-coded list for a maintained S&P 500 + NASDAQ 100 source (Wikipedia scrape or pinned
CSV) — that's tracked in the original Phase 2 plan.

---

## 3. Bars used for detection

`trader/scanner/runner.py:39 _fetch_bars()` — the scanner first asks the configured
broker (Alpaca by default) for daily bars; if the broker fails or doesn't implement bar
history, it falls back to `yfinance`.

The `lookback_days` query param on `/api/setups/today` (default **250**) is mapped to a
yfinance period string in `_lookback_to_period()`:

| `lookback_days` | period |
|---|---|
| ≤ 31 | 1mo |
| ≤ 91 | 3mo |
| ≤ 181 | 6mo |
| ≤ 366 | 1y |
| ≤ 732 | 2y |
| > 732 | 5y |

Two of the six detectors (`pullback`, `reversal`) need an EMA200 — they require **at
least 210 bars** to even run, so the default 250-day window is the floor.

---

## 4. The six detectors — exact rules

Each detector lives in `trader/setups/<name>.py` and exports a single
`detect(df) -> Optional[dict]`. They're pure functions of an OHLCV DataFrame; no I/O.
Every detector returns the same dict shape:

```python
{
  "setup": "<name>",
  "ticker": "...",          # filled in by run_scan
  "entry": <float>,
  "stop": <float>,
  "target": <float>,
  "risk_reward": <float>,
  "confidence": <0.0..1.0>,
  "reason": "<one-line explanation>",
}
```

### 4.1 `breakout` — 20-day high break with volume

`trader/setups/breakout.py`

| Test | Threshold |
|---|---|
| Today's close > 20-day high (prior 20 bars, excluding today) | required |
| Today's volume > 1.3 × 20-day avg volume | required |

**Levels:**
- **Entry** = today's close
- **Stop** = `max(5-day low, entry × 0.96)` — the tighter of "below the recent pivot" or "4% below entry"
- **Target** = `entry × 1.08` (~8% — typical first leg after a breakout)
- **Confidence** = `min(1.0, 0.5 + (vol_ratio - 1.3) × 0.2)` — base 0.5, scales up with volume excess

**Reason example:** `"Closed above 20-day high 245.30 on 2.1× avg volume"`

### 4.2 `flag` (returns `setup="bull_flag"`) — pole + tight consolidation + breakout

`trader/setups/flag.py`

Looks at three contiguous windows in the last 30 bars: pre-pole (bars −30 to −10), pole
(−10 to −7), consolidation (−7 to −1), today (−1).

| Test | Threshold |
|---|---|
| Pole gain (open of bar −10 → close of bar −7) | ≥ 8% |
| Consolidation range as % of high | ≤ 8% |
| Avg consolidation volume | < avg pre-pole volume |
| Today's close | > consolidation high |

**Levels:**
- **Entry** = today's close
- **Stop** = consolidation low
- **Target** = entry + (entry − stop) × **2.5** (R:R = 2.5)
- **Confidence** = `min(1.0, 0.55 + pole_gain)` — bigger pole, higher confidence

**Reason example:** `"Bull flag breakout: 12.3% pole, 4.7% tight consolidation"`

### 4.3 `pullback` — uptrend pullback to EMA20/50

`trader/setups/pullback.py` — uses the `add_indicators()` helper (RSI14, EMA20/50/200,
ATR14).

| Test | Threshold |
|---|---|
| EMA50 > EMA200 (long-term uptrend) | required |
| RSI(14) | 40 ≤ rsi ≤ 55 (cooled but not broken) |
| Price within 2% of EMA20 **or** EMA50 | required |
| Today closes green AND > yesterday's close (first bounce off the EMA) | required |

**Levels:**
- **Entry** = today's close
- **Stop** = `min(EMA50, close − 1.5 × ATR14)` — the looser of "below EMA50" or "1.5 ATRs below close"
- **Target** = entry + (entry − stop) × **2.0**
- **Confidence** = `0.6 + (50 − |rsi − 47.5|) × 0.005` — peaks when RSI is at 47.5 (centre of the 40–55 band)

**Reason example:** `"Pullback to EMA20 in uptrend, RSI 46"`

### 4.4 `earnings_runner` — post-earnings continuation

`trader/setups/earnings_runner.py`

Looks for a recent gap-up earnings bar in the last 4 trading days:

| Test | Threshold |
|---|---|
| Some bar in last 4 days where (open − prior close) / prior close | > 5% |
| That bar's close | > its open (green close on earnings day) |
| Today's close | > earnings-day high |
| Days since earnings bar | 1–3 |

**Levels:**
- **Entry** = today's close
- **Stop** = earnings-day low
- **Target** = entry + (entry − stop) × **2.0**
- **Confidence** = fixed **0.6**

**Reason example:** `"Post-earnings continuation, day +2, breaking earnings-day high 312.45"`

### 4.5 `reversal` — oversold bounce in long-term uptrend

`trader/setups/reversal.py`

| Test | Threshold |
|---|---|
| RSI(14) | < 35 |
| Close | > EMA200 |
| Today closes above yesterday's high (first sign of bounce) | required |

**Levels:**
- **Entry** = today's close
- **Stop** = 10-day low
- **Target** = entry + (entry − stop) × **1.8** (lower than other setups — counter-trend trades)
- **Confidence** = `0.55 + (35 − rsi) × 0.01` — lower RSI = higher confidence

**Reason example:** `"Oversold reversal in uptrend, RSI 28, price > EMA200"`

### 4.6 `relative_strength` — outperforming SPY at 20-day high

`trader/setups/relative_strength.py` — needs SPY bars too; the runner fetches SPY once
and passes it to each per-ticker scan.

| Test | Threshold |
|---|---|
| (ticker 20d return) − (SPY 20d return) | ≥ 5% |
| Today's close | > 20-day high (excluding today) |

**Levels:**
- **Entry** = today's close
- **Stop** = `max(10-day low, entry × 0.93)` — the tighter of "below recent pivot" or "7% below entry"
- **Target** = entry × 1.10
- **Confidence** = `min(1.0, 0.55 + outperf × 2)` — bigger outperformance, higher confidence

**Reason example:** `"Outperformed SPY by 8.4% over 20d, at new 20d high"`

---

## 5. Ranking + filtering

After every detector has run on every ticker (`scanner/runner.py:run_scan`):

1. **Min-confidence filter** — drops candidates below `min_confidence` (default 0.5 from
   the API). Tweak via the `min_confidence=` query param.
2. **Sort key** is `(confidence, risk_reward)` **descending** — confidence wins ties get
   broken by R:R.
3. The dashboard fetches `top=15` and renders them in the sidebar.

That's it. **No weighting between setup types**, no penalty for a stock that just had
news, no awareness of earnings dates, no sector or macro layer. The scanner is a fast
pattern matcher; everything contextual is delegated to the Claude layer below.

---

## 6. The Claude layer — what gets sent and what's asked for

There are **four distinct Claude entry points** in the app, each with its own system
prompt. All of them go through `trader.llm.client.call_claude`, which shells out to the
`claude` CLI so it uses your Pro/Max subscription instead of API keys.

| UI affordance | Endpoint | System prompt | Output shape |
|---|---|---|---|
| **rate** button (top of Setups list) | `POST /api/setups/rate?top=N` | `SETUP_RATER_SYSTEM` | `{rating: 1-10, reason: str}` per setup |
| **Analyze** button (top right of chart) | `POST /api/analyze/{ticker}` | `ANALYST_SYSTEM` | full thesis JSON |
| **Generate weekly prep** button (`/prep`) | `POST /api/prep` | `PREP_SYSTEM` | markdown document |
| **Grade with Claude** button (per closed trade in `/journal`) | `POST /api/journal/{id}/grade` | `GRADE_SYSTEM` | `{grade: A-F, lesson, tags, ...}` |

All four prompts live in **`trader/llm/prompts.py`**. They're written long and stable so
prompt-caching has something to grab onto.

### 6.1 Setup rater (the new "rate" button)

**Trigger:** clicking **rate** in the Setups sidebar header. Sequentially rates the top
N (default 4) candidates, then re-sorts the list by Claude's rating.

**Context sent to Claude per setup** (from `trader/llm/analysis.py:_fetch_context_light`):

- The full setup dict (ticker, pattern type, entry/stop/target, R:R, scanner confidence, reason)
- **Last 30 trading days** of daily OHLCV bars (date/open/high/low/close/volume)
- Up to **5 most recent news headlines** for the ticker (title, publisher, published)
- Last price + as-of timestamp

That's all — no hourly bars, no fundamentals, no analyst estimates. Lightweight by
design (~1K input tokens, ~50 output tokens) so 4 calls finish in ~10–15s.

**System prompt — `SETUP_RATER_SYSTEM`** (from `trader/llm/prompts.py:3`):

```
You rate scanner-detected swing-trade setups from 1-10.

You receive a single setup (ticker, pattern type, entry/stop/target, R:R, scanner
confidence) along with ~30 days of daily bars and any recent news headlines. You
return ONLY valid JSON — no prose, no code fences:

{"rating": 7, "reason": "Clean pullback to EMA20 but earnings in 3 days adds risk"}

Rating scale:
- 8-10: High conviction. Clean pattern, supportive news/macro, good R:R, no glaring red flags.
- 5-7:  Tradeable if disciplined. Setup is there but has caveats worth naming.
- 3-4:  Marginal. Would need to improve (better entry, tighter stop, news clears) before entry.
- 1-2:  Avoid. Pattern is technically present but context kills it.

Be skeptical. 8+ should be rare. Factor in:
- News already priced in (move already happened)
- Earnings within 5 trading days (binary risk)
- Sector weakness or SPY trending against the direction
- Overhead resistance close to entry
- Volume confirmation (or absence)
- RSI > 70 daily — this is a chase, not a fresh entry
- Penny stocks, low-volume names, biotech binary plays (cap at 4)

`reason` must be one sentence (under ~25 words), specific, not generic.
```

**User message format:** `Rate this setup:\n\`\`\`json\n<context_with_setup>\n\`\`\``

**Why this matters:** the scanner gives you a clean technical pattern. The rater asks
Claude to demote setups where the context is bad — earnings tomorrow, news already
out, RSI overbought, tape moving against you. That's the gap the badges close.

### 6.2 Full analyst (`Analyze` button on the dashboard chart)

**Context sent** (from `trader/llm/analysis.py:_fetch_context`):

- Last **90 trading days** of daily OHLCV bars
- Last **10 trading days** of hourly bars
- Up to **8 recent news headlines** (with summaries, truncated to 300 chars each)
- Last price + market cap + as-of timestamp
- Optionally, your current broker position in the ticker (when invoked with `with_position=True`)

**System prompt — `ANALYST_SYSTEM`** (from `trader/llm/prompts.py:29`):

```
You are a disciplined swing-trading analyst assisting a retail trader with a small
account (typically <$10K) using a Schwab cash account. The trader holds positions
for 2–10 trading days on average.

Your job is to read recent price action + news for a single ticker and produce a
structured trading thesis. You are NOT a hype machine — you actively call out when a
setup is mediocre, when news is already priced in, or when the risk-reward is poor.

ANALYTICAL FRAMEWORK
1. Trend context — Is the stock in a daily uptrend (above EMA50 > EMA200), downtrend, or range?
2. Setup quality — What pattern is forming? Pullback, breakout, flag, reversal, none?
3. Catalyst — Is there a specific reason for movement (earnings, news, sector flow)?
   If yes, name it specifically. If no, lower confidence.
4. Key levels — Identify near-term support/resistance, recent pivot highs/lows.
5. Entry zone — Where does an A+ entry sit? Be specific (not "around 245").
6. Stop placement — Where does the thesis fail? A wide stop = bad setup, not bigger size.
7. Target — Where is reasonable resistance / measured move? Be conservative.
8. Time horizon — How long until thesis plays out (days)?
9. Risk-reward — At least 2:1; ideally 3:1+. Below 2:1, lower confidence.
10. Suggested size — As % of account. Maximum 25% per position. Default 10–15% on
    high-conviction; 5% if confidence is low.

OUTPUT FORMAT — return ONLY valid JSON, no prose, no code fences:

{
  "ticker": "SYMBOL",
  "trend": "uptrend|downtrend|range|transitioning",
  "setup": "pullback|breakout|flag|reversal|none",
  "thesis": "1-3 sentence rationale, specific.",
  "catalysts": ["specific catalyst 1", "specific catalyst 2"],
  "risks": ["specific risk 1", "specific risk 2"],
  "ideal_entry": 245.50,
  "stop_level": 240.00,
  "target": 258.00,
  "risk_reward": 2.5,
  "time_horizon_days": 5,
  "suggested_size_pct": 12.5,
  "confidence": 6
}

DISCIPLINE RULES
- If the setup is poor, return confidence ≤3 and say so in `thesis`. Do NOT manufacture
  a setup that isn't there.
- If news is stale (> 3 trading days old) or already priced in, lower confidence.
- If implied move from earnings/news exceeds your target zone, the move may be over.
- Penny stocks (under $5), low-volume names, biotech binary plays: confidence ≤4.
- If RSI is > 70 on daily, this is not a fresh entry — at most a chase. Confidence ≤4.
- Confidence calibration: 8+ should be rare. 5–6 is "tradeable if disciplined". <5 = pass.
```

The thesis modal in the dashboard renders the JSON it returns: `thesis`,
`bias/horizon`, `confidence`, `entry_zone`, stop/target, catalysts, key levels, risks.

### 6.3 Weekly prep (`/prep` page → "Generate weekly prep")

**Context sent:**
- Top 20 setups from the scanner
- Earnings calendar for the coming week (yfinance)
- Macro events (Fed, CPI, etc.)
- Your current open positions
- Last 30 days of journal stats

**System prompt — `PREP_SYSTEM`** (from `trader/llm/prompts.py:80`):

Asks for a markdown doc with sections: macro/calendar, top-5 watch, earnings to track,
open positions review, lessons from last 30 days, notes. Discipline rules forbid hype,
require quoting actual numbers, and call out overtrading from journal stats.

### 6.4 Trade grader (closed trades in `/journal` → "Grade with Claude")

**Context sent:**
- `thesis_at_entry` (whatever was annotated when the trade was opened)
- entry/exit prices, sizes, dates
- Daily bars from 3 days before entry through 5 days after exit
- Final P&L, R-multiple

**System prompt — `GRADE_SYSTEM`** (from `trader/llm/prompts.py:124`):

Returns `{grade: A-F, thesis_played_out, exit_quality, what_went_right, what_went_wrong,
lesson, tags}`. The rubric explicitly de-couples grade from P&L: a losing trade taken
on a valid thesis with a clean stop-out is a B; a winning trade taken by chasing past
entry is a C at best.

The grade/lesson/tags get stored on the `Trade` row (`llm_grade`, `llm_lesson`,
`llm_tags`) and surface in the journal stats over time.

---

## 7. Tuning what gets picked

If you want to bias picks differently:

- **Tighten the universe** — edit `trader/scanner/universe.py:8` to remove names you
  never trade.
- **Drop a setup** — comment out the entry in `_DEFAULT_SETUPS` at
  `trader/scanner/runner.py:15`. The relative-strength scan is wired separately and
  always runs when SPY bars are available.
- **Raise the bar** — `min_confidence` query param defaults to 0.5; bump to 0.65 for a
  quieter list. Each detector's confidence formula is in its file.
- **Change the volume filter** in `breakout.py:18` (`avg_vol_20 * 1.3`) — easier
  threshold = more candidates, looser quality.
- **Change pole/consolidation thresholds** in `flag.py:21,27` — `pole_gain >= 0.08` and
  `cons_range_pct <= 0.08` are the two knobs that control how strict the pattern is.
- **Replace SPY** as the relative-strength benchmark by editing
  `scanner/runner.py:108` (e.g. swap to QQQ for tech-only RS).
- **Re-tune Claude** — every prompt is in `trader/llm/prompts.py`. The rater + analyst
  are designed to push back, not cheerlead — keep the discipline rules if you tweak the
  framework.

---

## 8. Honest limits

- **No earnings-aware filter.** A setup the day before earnings will still surface from
  the scanner; the rater is the only thing that knows to demote it.
- **No sector aggregation.** If 5 mega-cap tech names all hit a breakout because QQQ
  ripped, the scanner reports 5 candidates with no awareness they're correlated.
- **News from `yfinance` is delayed and shallow.** Headlines + 300 chars of summary,
  not full text. Fine for "is there a story", not for nuance.
- **The scanner runs synchronously per request.** A full S&P-500 scan would take
  minutes; the hard-coded 50-name universe is what keeps `/api/setups/today` snappy.
- **Confidence is uncalibrated.** Each detector's formula is a heuristic. The Claude
  rater is the post-hoc sanity check; don't trust the scanner's `confidence` as a
  probability.
- **Backtests don't exist for these setups yet.** The win-rate / expectancy numbers
  surface in the journal once you've actually traded, not before.
