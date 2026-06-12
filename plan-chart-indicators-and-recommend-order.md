# Plan: Chart Indicators (Ichimoku Cloud + Volume Coloring) & Recommend Order from Watchlist

## Context

The chart currently shows candlesticks, EMA(20/50/200), volume bars (single gray color), and RSI(14). The user wants two enhancements inspired by their TradingView setup:

1. **Ichimoku Cloud** — the blue/purple shaded "Kumo" cloud that shows support/resistance zones and trend direction at a glance.
2. **Colored volume bars** — volume bars tinted green/red based on candle direction (already partially done — bars have `+66` alpha suffix on up/down colors, but the visual impact is subtle).
3. **"Recommend Order" from watchlist** — when viewing any ticker (not just scanner setups), a button to run Claude analysis and optionally rate, then pre-fill the order form with Claude's recommended entry/stop/target.

The chart uses [lightweight-charts](https://github.com/nickolaj-jepsen/lightweight-charts) v4 (TradingView's open-source library). Ichimoku Cloud can be rendered as two line series with an `areaRange` between them (or two stacked area series). All indicator math is done client-side in `chart.js`.

---

## Part 1: Ichimoku Cloud Overlay

### What is Ichimoku?

Five lines, computed from highs/lows over rolling windows:
- **Tenkan-sen (Conversion):** (9-period high + 9-period low) / 2
- **Kijun-sen (Base):** (26-period high + 26-period low) / 2
- **Senkou Span A (Leading Span A):** (Tenkan + Kijun) / 2, plotted 26 periods ahead
- **Senkou Span B (Leading Span B):** (52-period high + 52-period low) / 2, plotted 26 periods ahead
- **Chikou Span (Lagging):** Close, plotted 26 periods behind

The "cloud" (Kumo) is the shaded area between Senkou Span A and Senkou Span B.

### Files to Modify

#### `trader/web/static/js/chart.js`

1. **Add Ichimoku calculation function:**
   ```javascript
   function ichimoku(bars, tenkanPeriod = 9, kijunPeriod = 26, senkouBPeriod = 52, displacement = 26) {
     // For each bar, compute midpoint of highest-high and lowest-low over the period
     function midpoint(bars, idx, period) {
       let hi = -Infinity, lo = Infinity;
       for (let i = Math.max(0, idx - period + 1); i <= idx; i++) {
         hi = Math.max(hi, bars[i].high);
         lo = Math.min(lo, bars[i].low);
       }
       return (hi + lo) / 2;
     }
     // Return arrays: tenkan[], kijun[], spanA[], spanB[], chikou[]
     // spanA and spanB are displaced forward by `displacement` bars
     // chikou is displaced backward by `displacement` bars
   }
   ```

2. **Add Ichimoku series to `initCharts()`:**
   - `tenkanSeries` — thin blue line (Conversion Line)
   - `kijunSeries` — thin red line (Base Line)
   - `spanASeries` + `spanBSeries` — for the cloud fill
   - `chikouSeries` — dotted green line (Lagging Span)

3. **Cloud rendering approach (lightweight-charts v4):**
   - lightweight-charts doesn't have a native "cloud" / area-between series. Two approaches:
     - **Option A (simpler):** Use two `addLineSeries()` for Span A and Span B with low opacity. No fill between them — relies on line proximity to convey the cloud. Less visual impact.
     - **Option B (recommended):** Use `addCustomSeries()` (v4 plugin API) or render the cloud as a set of thin horizontal histogram bars on a separate price scale. Actually, the simplest real cloud: use **two area series** — one for Span A (fill down to 0) and one for Span B (fill down to 0), with the one "on top" visually masking the lower one. With careful colors (blue-up cloud, red-down cloud), this creates the cloud effect.
     - **Option C (best visual):** Use the [`lightweight-charts` cloud plugin](https://github.com/nickolaj-jepsen/lightweight-charts/tree/master/plugin-examples/area-between) — `createSeriesMarkers` or custom rendering. The `series-markers` approach won't work, but the library's plugin examples include an "Area Between" renderer that draws filled area between two line series. This gives the exact TradingView cloud look.

   **Recommendation:** Option C if the plugin is available in the version we're using. Fallback to Option B.

4. **Add toggle button** in the chart toolbar to show/hide Ichimoku cloud (some traders find it noisy):
   ```html
   <button id="toggle-ichimoku" class="tf-btn px-2 py-1 ...">Cloud</button>
   ```

5. **Color scheme:**
   - Bullish cloud (Span A > Span B): `rgba(0, 150, 136, 0.15)` — teal/green tint
   - Bearish cloud (Span A < Span B): `rgba(239, 83, 80, 0.15)` — red tint
   - Tenkan line: `#2962FF` (blue)
   - Kijun line: `#B71C1C` (deep red)
   - Chikou: `#4CAF50` (green, dotted)

6. **Update `_loadTicker()`** to compute and set Ichimoku data after loading bars.

### Data Requirements

No backend changes needed — Ichimoku is computed from OHLC data already fetched. However, need **at least 52 bars of lookback** before the cloud starts rendering, plus 26 bars of forward displacement. The current `/api/bars/{ticker}` endpoint already returns 250+ bars for daily timeframe.

For the 26-bar forward displacement of Senkou Spans, we need to generate future time values. lightweight-charts handles "future" timestamps if we provide them — just extrapolate the time axis by adding `displacement` increments of the timeframe interval.

---

## Part 2: Enhanced Volume Bars

### Current State

Volume bars already exist with green/red coloring (line 129-133 in chart.js), but with `+66` alpha suffix making them very translucent. The TradingView screenshot shows more vivid volume coloring.

### Files to Modify

#### `trader/web/static/js/chart.js`

1. **Increase volume bar opacity** — change from `#22c55e66` / `#ef444466` to `#22c55eaa` / `#ef4444aa` (or even full opacity with the `scaleMargins` already confining them to bottom 15%).

2. **Add volume moving average line** (20-period SMA of volume) overlaid on the volume histogram — this is the blue line visible in the TradingView screenshot. Helps distinguish unusual volume from normal:
   ```javascript
   volumeAvgSeries = mainChart.addLineSeries({
     color: "#60a5fa",  // blue
     lineWidth: 1,
     priceScaleId: "vol",
     lastValueVisible: false,
     priceLineVisible: false,
   });
   // Set data = SMA(20) of volume
   ```

---

## Part 3: "Recommend Order" from Watchlist Ticker

### Concept

When viewing any ticker from the watchlist (not just scanner-detected setups), the user wants to:
1. Click "Recommend Order" (or similar button)
2. Claude analyzes the ticker (uses existing `analyze_ticker()`)
3. Claude's recommended entry/stop/target pre-fill the order form
4. Optionally click "Rate" on the recommendation for a second opinion

This bridges the gap between the Analyze button (which shows a thesis panel) and the order form (which currently only auto-fills from scanner setups).

### Files to Modify

#### `trader/web/templates/dashboard.html`

1. **Add "Recommend" button** next to the existing "Analyze" button in the top bar:
   ```html
   <button id="recommend-btn"
     class="ml-2 px-2 py-1 rounded border border-slate-700 hover:bg-slate-800 text-amber-400 text-xs"
     title="Claude recommends entry/stop/target and opens order form"
   >Recommend</button>
   ```

2. **Alternatively, add to the analysis results panel.** After clicking Analyze and seeing the thesis, add a "Trade This" button that takes Claude's `ideal_entry`, `stop_level`, `target` from the analysis response and pipes them into `openOrderFromSetup()`.

#### `trader/web/static/js/orders.js`

1. **Add `openOrderFromAnalysis(analysis)` function:**
   ```javascript
   window.openOrderFromAnalysis = function(analysis) {
     // analysis = Claude's analyze_ticker response with ideal_entry, stop_level, target, etc.
     $("order-ticker").value = analysis.ticker;
     $("order-side").value = "buy"; // or infer from analysis.trend === "downtrend" → "sell"
     $("order-entry").value = analysis.ideal_entry ?? "";
     $("order-stop").value = analysis.stop_level ?? "";
     $("order-target").value = analysis.target ?? "";
     $("order-risk").value = defaultRiskPct;
     $("order-qty").value = "";
     $("order-type").value = "bracket";

     const conf = analysis.confidence != null ? `${analysis.confidence}/10` : "—";
     $("order-preview").innerHTML = `
       <div class="text-amber-400 font-bold mb-1">Claude Recommendation · ${conf}</div>
       <div class="text-slate-400 text-xs mb-1">${analysis.thesis || ""}</div>
       <div class="text-slate-500">Auto-previewing…</div>
     `;
     $("order-submit-btn").disabled = true;
     lastPreview = null;
     $("order-modal").classList.remove("hidden");
     setTimeout(() => previewOrder(), 100);
   };
   ```

#### `trader/web/static/js/analyze.js` (or wherever the Analyze button handler lives)

1. **Store last analysis result** in a module-level variable so the "Trade This" button can access it.

2. **Add "Trade This" button** to the analysis results panel:
   ```javascript
   // After rendering analysis results, add:
   const tradeBtn = document.createElement("button");
   tradeBtn.textContent = "Trade This →";
   tradeBtn.className = "mt-2 px-3 py-1 rounded bg-amber-500 text-black text-sm font-bold hover:bg-amber-400";
   tradeBtn.onclick = () => window.openOrderFromAnalysis(lastAnalysis);
   analysisPanel.appendChild(tradeBtn);
   ```

#### New: `trader/web/api/recommend.py` (optional — could reuse `/api/analyze`)

If we want a single endpoint that does analysis + returns order-ready fields in one call:

```python
@router.post("/recommend/{ticker}")
async def recommend_order(ticker: str):
    """Run Claude analysis and return order-ready recommendation."""
    analysis = await loop.run_in_executor(None, analyze_ticker, ticker, True)
    return {
        "ticker": ticker,
        "side": "sell" if analysis.get("trend") == "downtrend" else "buy",
        "entry": analysis.get("ideal_entry"),
        "stop": analysis.get("stop_level"),
        "target": analysis.get("target"),
        "risk_reward": analysis.get("risk_reward"),
        "confidence": analysis.get("confidence"),
        "thesis": analysis.get("thesis"),
        "time_horizon_days": analysis.get("time_horizon_days"),
        "suggested_size_pct": analysis.get("suggested_size_pct"),
        "full_analysis": analysis,
    }
```

#### `trader/web/static/js/chart.js` or new `recommend.js`

1. **Wire the Recommend button:**
   ```javascript
   document.getElementById("recommend-btn").addEventListener("click", async () => {
     const ticker = window.getActiveTicker();
     const btn = document.getElementById("recommend-btn");
     btn.disabled = true;
     btn.textContent = "Thinking…";
     try {
       const res = await fetch(`/api/recommend/${ticker}`, { method: "POST" });
       const data = await res.json();
       if (data.entry) {
         window.openOrderFromAnalysis(data);
       } else {
         alert(`Claude says confidence ${data.confidence}/10 — no clean entry. Check Analyze for details.`);
       }
     } catch (e) {
       alert("Recommend failed: " + e.message);
     } finally {
       btn.disabled = false;
       btn.textContent = "Recommend";
     }
   });
   ```

2. **Optional: "Rate This" button on the recommendation** — after the order form opens from a recommendation, add a small "Rate" link that sends the recommendation as a setup to the existing `rate_setup()` for a second opinion.

---

## Part 4: Candle Click → Custom Order Entry (stretch goal)

Allow clicking directly on a candle in the chart to use that candle's price as entry, and drag to set stop/target visually. This is a TradingView-style UX.

### Approach

1. **Subscribe to crosshair move / click events** on the lightweight-charts instance.
2. On candle click, capture the bar's close price as a candidate entry.
3. Show a small floating tooltip: "Use $X as entry?" with a button.
4. Clicking it opens the order modal with that price pre-filled as entry.
5. Optional future: click-drag from entry to stop/target for visual trade planning.

### Files to Modify

#### `trader/web/static/js/chart.js`

```javascript
mainChart.subscribeCrosshairMove((param) => {
  // Show tooltip on hover with "click to set entry" hint
});

mainChart.subscribeClick((param) => {
  if (param.time && param.seriesData) {
    const candle = param.seriesData.get(candleSeries);
    if (candle) {
      showEntryTooltip(candle.close, param.point);
    }
  }
});
```

This is lower priority than Parts 1-3 and can be a follow-up.

---

## Implementation Order

1. **Ichimoku calculation + series** in `chart.js` (pure client-side math)
2. **Cloud rendering** — try the area-between plugin approach first
3. **Toggle button** for cloud visibility
4. **Volume bar opacity + volume SMA overlay**
5. **`/api/recommend/{ticker}` endpoint** (or reuse `/api/analyze`)
6. **"Recommend" button** in top bar + wiring
7. **`openOrderFromAnalysis()`** in orders.js
8. **"Trade This" button** on analysis panel
9. **(Stretch) Candle click → entry** interaction

---

## Verification

1. Load a daily chart — Ichimoku cloud should appear with blue/red shading, Tenkan/Kijun lines visible
2. Toggle cloud off — only EMAs + candles remain
3. Volume bars should be more vivid with a blue SMA(20) line over them
4. Click "Recommend" on a watchlist ticker → Claude runs → order form opens with pre-filled entry/stop/target
5. Click "Analyze" → see thesis → click "Trade This" → order form opens with same values
6. Verify the order preview calculates position size correctly from the recommended levels
