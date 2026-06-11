# Plan: Claude-Rated Setups

## Context

The scanner detects technical setups (pullback, breakout, flag, etc.) and scores them with a pattern-quality confidence %. But this score only measures how cleanly the price matches the pattern — it doesn't factor in news, earnings, macro, or whether the move is already over. Claude's `/analyze` endpoint does consider all of that and returns a 1-10 confidence score, but the two systems are disconnected.

**Goal:** Add an "Analyze top setups" button that sends the top N setups to Claude for a holistic 1-10 rating. The rated setups display inline in the sidebar so the user can see at a glance which setups Claude thinks are actually worth trading.

---

## Current state

- **Scanner** (`trader/scanner/runner.py`) → returns `{ticker, setup, entry, stop, target, confidence, reason}`
- **LLM analysis** (`trader/llm/analysis.py`) → `analyze_ticker(ticker)` fetches 90d daily + 10d hourly bars + news, sends to Claude, returns `{confidence: 1-10, thesis, catalysts, risks, ...}`
- **LLM client** (`trader/llm/client.py`) → shells out to `claude` CLI, uses Pro/Max subscription
- **Setups API** (`trader/web/api/setups.py`) → `GET /api/setups/today` returns ranked list
- **Analyze API** (`trader/web/api/analyze.py`) → `POST /api/analyze/{ticker}` returns full thesis
- **Setups JS** (`trader/web/static/js/setups.js`) → renders sidebar, has "trade" buttons

---

## Changes

### 1. `trader/llm/analysis.py` — add `rate_setup()` function

New lightweight function that sends the setup context + ticker data to Claude and asks for just a 1-10 rating with a one-line reason. Much cheaper than a full `analyze_ticker()` call.

```python
SETUP_RATER_SYSTEM = """You rate swing-trade setups from 1-10.
You receive a scanner-detected setup with entry/stop/target plus 30 days of
daily bars and recent news. Return ONLY valid JSON:

{"rating": 7, "reason": "Clean pullback to EMA20 but earnings in 3 days adds risk"}

Rating scale:
- 8-10: High conviction. Clean pattern, supportive news/macro, good R:R.
- 5-7: Tradeable if disciplined. Setup is there but has caveats.
- 3-4: Marginal. Would need to improve before entry.
- 1-2: Avoid. Pattern is there technically but context kills it.

Be skeptical. 8+ should be rare. Factor in: news already priced in, earnings
proximity, sector weakness, overhead resistance, volume confirmation, whether
the broader market (SPY) supports the direction."""

def rate_setup(ticker: str, setup: dict) -> dict:
    """Quick Claude rating of a single setup. Returns {rating: int, reason: str}."""
    # Fetch last 30d bars + news (lighter than full analyze_ticker)
    context = _fetch_context_light(ticker)  # new helper, 30d only
    context["setup"] = setup

    result = call_claude(
        system=SETUP_RATER_SYSTEM,
        user=f"Rate this setup:\n```json\n{_compact_json(context)}\n```",
        json_response=True,
        max_tokens=200,
    )
    return result
```

Also add `_fetch_context_light(ticker)` — same as `_fetch_context` but only 30 days of daily bars and no hourly bars, to keep the prompt small and fast.

### 2. `trader/web/api/setups.py` — add `POST /api/setups/rate` endpoint

New endpoint that takes the top N setups and rates them via Claude:

```python
@router.post("/setups/rate")
async def rate_setups(top: int = 4) -> dict:
    """Rate the top N setups from today's scan using Claude.
    Returns {rated: [{ticker, setup, scanner_confidence, claude_rating, reason, ...}]}
    """
    from trader.scanner.runner import run_scan
    from trader.llm.analysis import rate_setup

    candidates = run_scan()[:top]
    rated = []
    for s in candidates:
        try:
            rating = rate_setup(s["ticker"], s)
            s["claude_rating"] = rating.get("rating")
            s["claude_reason"] = rating.get("reason", "")
        except Exception as e:
            s["claude_rating"] = None
            s["claude_reason"] = f"Rating failed: {e}"
        rated.append(s)

    # Re-sort by Claude rating (highest first), fallback to scanner confidence
    rated.sort(key=lambda s: (s.get("claude_rating") or 0, s.get("confidence", 0)), reverse=True)
    return {"rated": rated}
```

### 3. `trader/web/static/js/setups.js` — add "Rate top" button + display ratings

Add a button next to "scan" that triggers Claude rating:

```html
<button id="setups-rate" class="text-xs text-amber-400 hover:underline">rate top 4</button>
```

When clicked:
- Shows "rating..." state on the top 4 setups
- Calls `POST /api/setups/rate?top=4`
- Updates each setup row with a Claude badge: `🟢 8/10` or `🔴 3/10` with the reason as tooltip
- Color coding: green (8-10), amber (5-7), red (1-4)

```js
async function rateTopSetups() {
  const btn = document.getElementById("setups-rate");
  btn.textContent = "rating…";
  btn.disabled = true;
  try {
    const res = await fetch("/api/setups/rate?top=4", { method: "POST" });
    const data = await res.json();
    const rated = data.rated || [];
    // Update the existing setup list items with Claude ratings
    rated.forEach((s) => {
      const li = document.querySelector(`[data-setup-ticker="${s.ticker}"]`);
      if (!li) return;
      const badge = li.querySelector(".claude-badge") || document.createElement("span");
      badge.className = "claude-badge text-xs ml-1 " + ratingColor(s.claude_rating);
      badge.textContent = s.claude_rating != null ? `${s.claude_rating}/10` : "—";
      badge.title = s.claude_reason || "";
      // Insert badge if new
      if (!li.querySelector(".claude-badge")) {
        li.querySelector(".font-bold").after(badge);
      }
    });
  } catch (e) {
    console.error("Rate failed:", e);
  } finally {
    btn.textContent = "rate top 4";
    btn.disabled = false;
  }
}
```

### 4. `trader/web/templates/dashboard.html` — add rate button to setups header

In the setups section of the left sidebar, add the rate button alongside scan:

```html
<div class="px-3 py-2 flex items-center justify-between">
  <span class="text-xs uppercase text-slate-500">Setups</span>
  <div class="flex gap-2">
    <button id="setups-rate" class="text-xs text-amber-400 hover:underline">rate</button>
    <button id="setups-refresh" class="text-xs text-cyan-400 hover:underline">scan</button>
  </div>
</div>
```

---

## Files to modify

| File | Change |
|------|--------|
| `trader/llm/analysis.py` | Add `SETUP_RATER_SYSTEM` prompt, `_fetch_context_light()`, `rate_setup()` |
| `trader/llm/prompts.py` | Optionally move `SETUP_RATER_SYSTEM` here to keep prompts together |
| `trader/web/api/setups.py` | Add `POST /api/setups/rate` endpoint |
| `trader/web/static/js/setups.js` | Add `rateTopSetups()`, wire "rate" button, display badges |
| `trader/web/templates/dashboard.html` | Add "rate" button next to "scan" in setups header |

---

## Cost / performance

- Each `rate_setup()` call sends ~30 daily bars + news (~1K tokens input, ~50 tokens output)
- 4 setups = 4 sequential Claude calls ≈ 10-15 seconds total, minimal cost on Pro/Max
- Could parallelize with asyncio.gather but sequential is simpler and avoids rate limits
- The "rate" button is manual (not auto-triggered) so the user controls when to spend the time

---

## Verification

1. `uv run trader serve`, open dashboard
2. Click "scan" — setups appear in sidebar
3. Click "rate" — shows "rating..." then badges appear (e.g., `8/10`, `4/10`)
4. Hover a badge — tooltip shows Claude's one-line reason
5. Verify the highest-rated setup actually makes sense (check chart + news)
6. Click "trade" on a high-rated setup — order form pre-fills as before
