# Plan: Short Selling Support

## Context

All current setup detectors (pullback, breakout, flag, reversal, relative_strength) only generate **buy** signals. The order form has a sell dropdown but it's only for closing longs. Alpaca paper trading fully supports short selling — shares are borrowed automatically on sell orders when you don't hold the position.

**Goal:** Add bearish setup detectors that emit `side: "sell"` setups, wire stop/target logic to work inverted for shorts, and let the existing trade flow (setup → order form → preview → submit) handle shorts end-to-end.

---

## Current state

- **Setup detectors** (`trader/setups/*.py`) — each `detect(df)` returns `{setup, entry, stop, target, risk_reward, confidence, reason}`. No `side` field — everything is implicitly a buy.
- **Scanner** (`trader/scanner/runner.py`) — runs detectors, sets `ticker`, sorts by confidence.
- **Order form** (`trader/web/static/js/orders.js`) — `openOrderFromSetup()` reads `setup.side` and defaults to `"buy"` if absent. Already handles the field.
- **Risk guard** (`trader/broker/risk_guard.py`) — checks position %, risk %, stop distance %. Side-agnostic math.
- **Sizing** (`trader/sizing/calculator.py`) — `position_size(equity, risk_pct, entry, stop)` uses `abs(entry - stop)`. Already works for shorts where stop > entry.
- **Alpaca broker** (`trader/broker/alpaca.py`) — `place_order()` passes `side` directly to Alpaca SDK. Shorts work out of the box on paper.
- **Claude rater** (`trader/llm/prompts.py`) — `SETUP_RATER_SYSTEM` says "rate swing-trade setups 1-10" but doesn't mention direction. Needs a note about short setups.

---

## Changes

### 1. `trader/setups/breakdown.py` — NEW: Bearish breakdown detector

Mirror of `breakout.py` but inverted: close below 20-day low on elevated volume.

```python
def detect(df: pd.DataFrame) -> Optional[dict]:
    """Detect a breakdown: close below 20-day low on > 1.3× avg volume."""
    if df.empty or len(df) < 21:
        return None
    last = df.iloc[-1]
    prior_20 = df.iloc[-21:-1]
    prior_low = float(prior_20["Low"].min())
    avg_vol_20 = float(prior_20["Volume"].mean())

    if float(last["Close"]) < prior_low and float(last["Volume"]) > avg_vol_20 * 1.3:
        entry = float(last["Close"])
        recent_high = float(prior_20["High"].tail(5).max())
        stop = min(recent_high, entry * 1.04)  # stop above entry
        target = entry * 0.92  # ~8% drop target
        rr = (entry - target) / (stop - entry) if stop > entry else 0
        return {
            "setup": "breakdown",
            "side": "sell",
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "risk_reward": round(rr, 2),
            "confidence": min(1.0, 0.5 + (float(last["Volume"]) / avg_vol_20 - 1.3) * 0.2),
            "reason": f"Broke below 20-day low {prior_low:.2f} on "
                      f"{last['Volume']/avg_vol_20:.1f}× avg volume",
        }
    return None
```

### 2. `trader/setups/bear_flag.py` — NEW: Bearish flag detector

Mirror of `flag.py`: sharp down move (pole), 3-7 day tight consolidation on declining volume, then breakdown below the lower consolidation bound.

```python
def detect(df: pd.DataFrame) -> Optional[dict]:
    """Bear flag: sharp drop, tight consolidation, then continuation break lower."""
    if df.empty or len(df) < 30:
        return None
    last = df.iloc[-1]
    consolidation = df.iloc[-7:-1]
    pole = df.iloc[-10:-7]

    pole_drop = (float(pole["Open"].iloc[0]) - float(pole["Close"].iloc[-1])) / float(pole["Open"].iloc[0])
    if pole_drop < 0.08:
        return None

    cons_high = float(consolidation["High"].max())
    cons_low = float(consolidation["Low"].min())
    cons_range_pct = (cons_high - cons_low) / cons_high
    if cons_range_pct > 0.08:
        return None

    pre_pole = df.iloc[-30:-10]
    avg_pre_vol = float(pre_pole["Volume"].mean())
    avg_cons_vol = float(consolidation["Volume"].mean())
    if avg_cons_vol >= avg_pre_vol:
        return None

    if float(last["Close"]) >= cons_low:
        return None

    entry = float(last["Close"])
    stop = cons_high
    target = entry - (stop - entry) * 2.5
    rr = (entry - target) / (stop - entry) if stop > entry else 0
    return {
        "setup": "bear_flag",
        "side": "sell",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": min(1.0, 0.55 + pole_drop),
        "reason": f"Bear flag breakdown: {pole_drop*100:.1f}% pole, "
                  f"{cons_range_pct*100:.1f}% tight consolidation",
    }
```

### 3. `trader/setups/overbought_reversal.py` — NEW: Overbought rejection

Mirror of `reversal.py` but inverted: RSI > 70 in downtrend (EMA50 < EMA200), today closes below yesterday's low.

```python
def detect(df: pd.DataFrame) -> Optional[dict]:
    """Overbought reversal in downtrend: RSI>70, EMA50 < EMA200,
    today closes below yesterday's low (first sign of rejection)."""
    if df.empty or len(df) < 210:
        return None

    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    prev = enriched.iloc[-2]

    rsi = last.get("rsi_14")
    ema_50 = last.get("ema_50")
    ema_200 = last.get("ema_200")
    atr = last.get("atr_14")
    close = float(last["Close"])

    for v in (rsi, ema_50, ema_200, atr):
        if v is None or v != v:
            return None

    if rsi <= 65:
        return None
    if ema_50 >= ema_200:
        return None  # not a downtrend
    if close >= float(prev["Low"]):
        return None

    entry = close
    stop = float(df.iloc[-10:]["High"].max())
    target = entry - (stop - entry) * 1.8
    rr = (entry - target) / (stop - entry) if stop > entry else 0
    return {
        "setup": "overbought_reversal",
        "side": "sell",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_reward": round(rr, 2),
        "confidence": 0.55 + (rsi - 65) * 0.01,
        "reason": f"Overbought rejection in downtrend, RSI {rsi:.0f}, EMA50 < EMA200",
    }
```

### 4. `trader/setups/relative_weakness.py` — NEW: Relative weakness vs SPY

Mirror of `relative_strength.py`: underperformed SPY by >= 5% over 20 days AND making a new 20-day low.

```python
def detect(df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None,
           lookback: int = 20, min_underperf: float = 0.05) -> Optional[dict]:
    """Flag if ticker underperformed SPY by >= min_underperf and at new 20d low."""
    # ... (same structure as relative_strength but inverted)
    return {
        "setup": "relative_weakness",
        "side": "sell",
        "entry": round(entry, 2),
        "stop": ...,
        "target": ...,
        ...
    }
```

### 5. `trader/scanner/runner.py` — Register new detectors

```python
from trader.setups import (
    breakout, breakdown, flag, bear_flag, pullback,
    earnings_runner, reversal, overbought_reversal,
    relative_strength, relative_weakness,
)

_DEFAULT_SETUPS: list[tuple[str, SetupFn]] = [
    # Long setups
    ("breakout", breakout.detect),
    ("flag", flag.detect),
    ("pullback", pullback.detect),
    ("earnings_runner", earnings_runner.detect),
    ("reversal", reversal.detect),
    # Short setups
    ("breakdown", breakdown.detect),
    ("bear_flag", bear_flag.detect),
    ("overbought_reversal", overbought_reversal.detect),
]
```

Also add `relative_weakness` alongside the existing `relative_strength` call in `scan_ticker()`:

```python
if spy_df is not None:
    for rs_fn, rs_name in [
        (relative_strength.detect, "relative_strength"),
        (relative_weakness.detect, "relative_weakness"),
    ]:
        try:
            rs = rs_fn(df, spy_df)
            if rs:
                rs["ticker"] = ticker
                rs.setdefault("setup", rs_name)
                out.append(rs)
        except Exception:
            pass
```

### 6. `trader/web/static/js/setups.js` — Show side indicator

Add a short/long badge to setup rows so the user can tell at a glance:

```js
const sideBadge = s.side === "sell"
  ? '<span class="text-red-400 text-[10px] uppercase font-bold">short</span>'
  : '<span class="text-green-400 text-[10px] uppercase font-bold">long</span>';
```

Insert it next to the setup name in `renderSetupRow()`.

### 7. `trader/web/static/js/orders.js` — No changes needed

`openOrderFromSetup()` already reads `setup.side` and falls back to `"buy"`:
```js
$("order-side").value = (setup.side === "sell") ? "sell" : "buy";
```

### 8. `trader/llm/prompts.py` — Update SETUP_RATER_SYSTEM

Add a note that setups can be long (buy) or short (sell), and the rater should evaluate shorts with the same rigor — considering borrow availability, short squeeze risk, upcoming catalysts that could cause a gap up, etc.

Add to the system prompt:
```
Setups may be long (buy) or short (sell). For shorts, additionally consider:
- Short squeeze risk (high short interest, small float)
- Upcoming catalysts that could gap the stock up (earnings, FDA, etc.)
- Whether the stock is "hard to borrow" (small cap, low float)
- Trend strength — shorting into a strong uptrend is dangerous
```

---

## Files to create

| File | Description |
|------|-------------|
| `trader/setups/breakdown.py` | Bearish breakdown below 20-day low on volume |
| `trader/setups/bear_flag.py` | Bear flag continuation pattern |
| `trader/setups/overbought_reversal.py` | Overbought rejection in downtrend |
| `trader/setups/relative_weakness.py` | Underperformer vs SPY at new lows |

## Files to modify

| File | Change |
|------|--------|
| `trader/scanner/runner.py` | Import + register 4 new short detectors |
| `trader/web/static/js/setups.js` | Add long/short badge to setup rows |
| `trader/llm/prompts.py` | Add short-specific guidance to `SETUP_RATER_SYSTEM` |

---

## How shorts work on Alpaca

- **Paper trading:** Shorts work out of the box. Sell an asset you don't hold → Alpaca opens a short position.
- **Bracket orders:** Same OTO structure. For a short: entry is a sell limit, stop-loss is a buy stop (above entry), take-profit is a buy limit (below entry). The existing `bracket()` order builder passes side through — Alpaca handles the rest.
- **Margin:** Shorts require margin. Paper accounts have 4× day-trade buying power. Live accounts need RegT margin (2× overnight).
- **Risk guard:** Already works — it checks `abs(entry - stop)` for stop distance and position % is the same regardless of direction.

---

## Verification

1. `uv run trader serve`, open dashboard
2. Click "scan" — should now see both long and short setups with badges
3. Short setups show `side: "sell"`, stop above entry, target below entry
4. Click "trade" on a short setup → order form pre-fills with side=sell, entry/stop/target inverted correctly
5. Preview shows correct risk math (dollar risk = stop - entry for shorts)
6. Submit a paper short → verify position shows as negative quantity in Alpaca dashboard
7. Click "rate" → Claude rates shorts with appropriate skepticism about squeeze risk etc.
