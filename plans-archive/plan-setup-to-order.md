# Plan: One-Click Trade from Setup

## Context

The scanner already detects setups (pullback, breakout, flag, etc.) with entry, stop, target, and risk/reward levels. The order form already supports preview + submit with risk guard validation. But they're disconnected — clicking a setup only loads the chart, and the order form opens blank. The user has to manually copy numbers.

**Goal:** Clicking a setup in the sidebar should pre-fill the order form with entry/stop/target, auto-calculate position size, and auto-preview — so the user just reviews and clicks Submit or closes the modal.

---

## What exists today

- **`trader/setups/*.py`** — each detector returns `{setup, ticker, entry, stop, target, risk_reward, confidence, reason}`
- **`trader/web/api/setups.py`** — `/api/setups/today` returns the ranked list
- **`trader/web/static/js/setups.js`** — renders setup list in sidebar, click loads chart only
- **`trader/web/static/js/orders.js`** — `openOrderModal()` clears all fields, has `previewOrder()` and `submitOrder()` wired up
- **`trader/web/api/orders.py`** — `/api/orders/preview` does risk guard checks + position sizing, `/api/orders/submit` places the order

---

## Changes

### 1. `trader/web/static/js/setups.js` — pass setup data to order modal

Currently each setup `<li>` only stores `data-setup-ticker`. Change to store the full setup object and call a new `openOrderFromSetup()` function on click.

```js
// Store full setup data on the element
li.dataset.setup = JSON.stringify(s);

li.addEventListener("click", () => {
  if (window.loadTicker) window.loadTicker(s.ticker);
  if (window.openOrderFromSetup) window.openOrderFromSetup(s);
});
```

### 2. `trader/web/static/js/orders.js` — add `openOrderFromSetup(setup)`

New function that pre-fills the order form from a setup object and auto-triggers preview:

```js
window.openOrderFromSetup = function(setup) {
  $("order-ticker").value = setup.ticker;
  $("order-side").value = "buy";  // setups are buy signals
  $("order-entry").value = setup.entry;
  $("order-stop").value = setup.stop;
  $("order-target").value = setup.target;
  $("order-risk").value = "1.0";  // default from config
  $("order-qty").value = "";      // let preview calculate from risk %
  $("order-type").value = "bracket";  // bracket = entry + stop + target
  $("order-modal").classList.remove("hidden");

  // Show setup context in the preview area while loading
  $("order-preview").innerHTML = `
    <div class="text-cyan-400 font-bold mb-1">${setup.setup} · ${(setup.confidence * 100).toFixed(0)}% confidence</div>
    <div class="text-slate-400 text-xs">${setup.reason || ""}</div>
    <div class="text-slate-500 mt-1">Auto-previewing…</div>
  `;

  // Auto-trigger preview after a short delay (lets the DOM update)
  setTimeout(() => previewOrder(), 100);
};
```

Also expose `previewOrder` to window scope (currently it's module-private):

```js
window.previewOrder = previewOrder;
```

### 3. `trader/web/static/js/setups.js` — add "Trade" button per setup

Add a small trade button alongside each setup entry so the user has a clear action affordance:

```html
<button class="text-xs text-cyan-400 hover:underline setup-trade-btn">trade</button>
```

Clicking "trade" opens the pre-filled order modal. Clicking the rest of the row still loads the chart.

### 4. Dashboard HTML — add setup reason tooltip or detail

In `dashboard.html`, the setups list items could show the reason on hover via a `title` attribute. No template changes needed — this is done in `setups.js` when rendering.

```js
title="${s.reason || ''}"
```

---

## Optional enhancements (same PR if quick)

### 5. Load default risk % from config

Instead of hardcoding `1.0`, fetch it from `/api/settings` on init:

```js
const settings = await fetch("/api/settings").then(r => r.json());
const defaultRisk = settings.config?.risk?.default_risk_pct || 1.0;
```

Use `defaultRisk` when pre-filling the risk field.

### 6. Sell setups (reversal detector)

The `reversal.py` detector may flag short/sell setups. When `setup.side` is present and equals `"sell"`, pre-fill the side accordingly. Currently all detectors imply buy, but the field is there for future use.

---

## Files to modify

| File | Change |
|------|--------|
| `trader/web/static/js/setups.js` | Store full setup JSON on elements, add "trade" button, call `openOrderFromSetup` on click |
| `trader/web/static/js/orders.js` | Add `window.openOrderFromSetup()`, expose `previewOrder`, pre-fill + auto-preview logic |

That's it — two files, no backend changes. The API already returns everything needed.

---

## Verification

1. Run `uv run trader serve`, open `http://localhost:8765`
2. Wait for scanner to populate setups in the sidebar (or click "scan")
3. Click a setup row — chart loads AND order modal opens pre-filled with entry/stop/target
4. Preview auto-runs showing position size, dollar risk, and risk guard status
5. Click Submit to place a paper bracket order, or close to skip
6. Verify the order appears in Alpaca's paper dashboard at app.alpaca.markets
