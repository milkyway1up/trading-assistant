# Plan: Dual Alpaca Accounts (Paper + Live) with Visual Safety Indicator

## Context

The app currently holds a single set of Alpaca API keys and a `broker.paper: true/false` toggle. The user wants **both** paper and live accounts accessible simultaneously with a quick swap, and a **strong visual indicator** so there's zero ambiguity about which account is active. Accidentally placing a real-money trade thinking you're on paper is a bad day.

**Key Alpaca fact:** Paper and live accounts use entirely separate API keys generated at different endpoints. You cannot reuse paper keys for live or vice versa. The user needs to generate live keys separately from their Alpaca dashboard.

---

## Part 1: Config — Store Both Key Sets

### `trader/config.py`

Add a second set of Alpaca secrets:

```python
class Secrets(BaseSettings):
    # Paper account keys
    alpaca_paper_api_key: str = ""
    alpaca_paper_secret_key: str = ""
    # Live account keys
    alpaca_live_api_key: str = ""
    alpaca_live_secret_key: str = ""
    # Legacy single-key fields (migrate on first load)
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
```

Update `_ENV_KEYS` to include the new key names.

**Migration:** If the old `alpaca_api_key`/`alpaca_secret_key` are set but the new split keys aren't, auto-copy them into the paper keys (since the default was `paper: true`). Log a deprecation warning.

### `BrokerConfig`

Change from a boolean toggle to an explicit mode:

```python
class BrokerConfig(BaseModel):
    provider: Literal["schwab", "alpaca"] = "alpaca"
    mode: Literal["paper", "live"] = "paper"  # replaces `paper: bool`
```

### `.env` example

```
ALPACA_PAPER_API_KEY=PK...
ALPACA_PAPER_SECRET_KEY=...
ALPACA_LIVE_API_KEY=AK...
ALPACA_LIVE_SECRET_KEY=...
```

---

## Part 2: Factory — Pick Keys by Mode

### `trader/broker/factory.py`

```python
def get_broker() -> BrokerClient:
    cfg = get_config()
    secrets = get_secrets()
    
    if cfg.broker.provider == "alpaca":
        is_paper = cfg.broker.mode == "paper"
        api_key = secrets.alpaca_paper_api_key if is_paper else secrets.alpaca_live_api_key
        secret = secrets.alpaca_paper_secret_key if is_paper else secrets.alpaca_live_secret_key
        
        # Fallback to legacy single keys
        if not api_key:
            api_key = secrets.alpaca_api_key
            secret = secrets.alpaca_secret_key
        
        return AlpacaBrokerClient(api_key=api_key, secret_key=secret, paper=is_paper)
```

---

## Part 3: Settings UI — Separate Key Inputs

### `dashboard.html` — Settings modal, API Keys tab

Replace the single "Alpaca API Key" / "Alpaca Secret Key" fields with two grouped sections:

```html
<div class="border-t border-slate-700 pt-3 mt-2">
  <div class="text-xs uppercase tracking-wide mb-2 flex items-center gap-2">
    <span class="text-green-400 font-bold">● Paper Account</span>
  </div>
  <p class="text-xs text-slate-500 mb-2">
    Generate at alpaca.markets → Paper Trading → API Keys
  </p>
  <div class="space-y-2">
    <div>
      <label class="block text-xs text-slate-400 mb-1">Paper API Key</label>
      <input data-secret="alpaca_paper_api_key" type="password" placeholder="PK…"
        class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm" />
    </div>
    <div>
      <label class="block text-xs text-slate-400 mb-1">Paper Secret Key</label>
      <input data-secret="alpaca_paper_secret_key" type="password" placeholder="paper secret"
        class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm" />
    </div>
  </div>
</div>

<div class="border-t border-slate-700 pt-3 mt-2">
  <div class="text-xs uppercase tracking-wide mb-2 flex items-center gap-2">
    <span class="text-red-400 font-bold">● Live Account</span>
  </div>
  <p class="text-xs text-slate-500 mb-2">
    Generate at alpaca.markets → Live Trading → API Keys. Real money.
  </p>
  <div class="space-y-2">
    <div>
      <label class="block text-xs text-slate-400 mb-1">Live API Key</label>
      <input data-secret="alpaca_live_api_key" type="password" placeholder="AK…"
        class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm" />
    </div>
    <div>
      <label class="block text-xs text-slate-400 mb-1">Live Secret Key</label>
      <input data-secret="alpaca_live_api_key" type="password" placeholder="live secret"
        class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm" />
    </div>
  </div>
</div>
```

### Settings modal, Broker tab

Replace the `paper: true/false` checkbox with a toggle that clearly shows mode:

```html
<div class="text-xs text-slate-400 mb-2 uppercase tracking-wide">Trading Mode</div>
<div class="flex gap-3">
  <label class="flex items-center gap-2 cursor-pointer px-3 py-2 rounded border-2" id="mode-paper-label">
    <input type="radio" name="broker_mode" value="paper" />
    <div>
      <div class="text-sm font-bold text-green-400">Paper</div>
      <div class="text-xs text-slate-500">Simulated money, no risk</div>
    </div>
  </label>
  <label class="flex items-center gap-2 cursor-pointer px-3 py-2 rounded border-2" id="mode-live-label">
    <input type="radio" name="broker_mode" value="live" />
    <div>
      <div class="text-sm font-bold text-red-400">Live</div>
      <div class="text-xs text-slate-500">Real money</div>
    </div>
  </label>
</div>
```

---

## Part 4: Visual Safety — Color the Entire App Based on Mode

This is the most important part. The user must **never** mistake live for paper.

### Header Bar Color

- **Paper mode:** Header background stays dark (`bg-slate-900`) with a **green** left accent border and green "PAPER" badge
- **Live mode:** Header gets a **dark red tint** (`bg-red-950`) with a red left accent border and red "LIVE" badge that pulses subtly

### Implementation in `dashboard.html` / `account.js`

The `/api/account` endpoint already returns `account.paper` (boolean). Use this to set the visual state:

```javascript
function applyAccountMode(isPaper) {
  const header = document.querySelector("header");
  const badge = document.getElementById("mode-badge");
  const body = document.body;
  
  if (isPaper) {
    header.classList.remove("bg-red-950", "border-l-4", "border-red-500");
    header.classList.add("border-l-4", "border-green-500");
    badge.textContent = "PAPER";
    badge.className = "text-xs font-bold px-2 py-0.5 rounded bg-green-900 text-green-300";
    body.classList.remove("ring-2", "ring-red-500/20");
  } else {
    header.classList.remove("border-green-500");
    header.classList.add("bg-red-950", "border-l-4", "border-red-500");
    badge.textContent = "LIVE";
    badge.className = "text-xs font-bold px-2 py-0.5 rounded bg-red-900 text-red-300 animate-pulse";
    body.classList.add("ring-2", "ring-red-500/20");
  }
}
```

### Mode Badge in Header

Add between the nav and the ticker display:

```html
<span id="mode-badge" class="text-xs font-bold px-2 py-0.5 rounded bg-green-900 text-green-300">PAPER</span>
```

### Order Form Confirmation Gate (Live Only)

When in live mode, the order submit button should require a **double-click** or show a confirmation:

```javascript
// In orders.js, before submitting in live mode:
if (!accountIsPaper) {
  const confirmed = confirm(
    `⚠️ LIVE TRADING\n\nYou are about to ${side} ${qty} shares of ${ticker} with real money.\n\nContinue?`
  );
  if (!confirmed) return;
}
```

### Right Rail Account Section

Color the account panel border based on mode:
- Paper: `border-l-2 border-green-500`
- Live: `border-l-2 border-red-500` + equity/P&L in slightly larger font

### CSS Variables Approach (cleaner)

Set a CSS custom property on `<body>` and reference it:

```javascript
document.body.dataset.tradingMode = isPaper ? "paper" : "live";
```

```css
/* In app.css */
[data-trading-mode="live"] header { background: rgb(69 10 10); }
[data-trading-mode="live"] #order-submit-btn { background: rgb(185 28 28); }
[data-trading-mode="live"] .mode-accent { border-color: rgb(239 68 68); }
[data-trading-mode="paper"] .mode-accent { border-color: rgb(34 197 94); }
```

---

## Part 5: Quick Account Switcher

### Header Dropdown

Add a small dropdown next to the mode badge for quick switching without going into settings:

```html
<div class="relative" id="account-switcher">
  <button id="mode-badge" class="text-xs font-bold px-2 py-0.5 rounded cursor-pointer">PAPER</button>
  <div id="mode-dropdown" class="hidden absolute top-full left-0 mt-1 bg-slate-800 border border-slate-700 rounded shadow-lg z-50 text-xs w-40">
    <button data-switch-mode="paper" class="w-full text-left px-3 py-2 hover:bg-slate-700 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-green-400"></span> Paper Trading
    </button>
    <button data-switch-mode="live" class="w-full text-left px-3 py-2 hover:bg-slate-700 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-red-400"></span> Live Trading
    </button>
  </div>
</div>
```

Clicking "Live Trading" when currently on paper should:
1. Check that live keys are configured (if not, prompt to add them in Settings)
2. Show a confirmation: "Switch to LIVE trading? Orders will use real money."
3. POST to `/api/settings/config` with `{"broker": {"mode": "live"}}`
4. Call `reset_clients()` on the backend
5. Refresh account data and apply the visual mode change

Switching back to paper should be instant (no confirmation needed — paper is the safe direction).

---

## Part 6: API Changes

### `trader/web/api/settings.py`

Update `SecretsView` and `SecretsUpdate` with the new key names:

```python
class SecretsView(BaseModel):
    alpaca_paper_api_key_set: bool
    alpaca_paper_secret_key_set: bool
    alpaca_live_api_key_set: bool
    alpaca_live_secret_key_set: bool
    # ... rest unchanged
```

### `trader/web/api/account.py`

Already returns `account.paper` from the broker — no changes needed. The frontend reads this to set visual mode.

### New endpoint: `POST /api/broker/switch`

Convenience endpoint that switches mode + resets clients in one call:

```python
@router.post("/broker/switch")
async def switch_mode(mode: Literal["paper", "live"] = Query(...)):
    if mode == "live":
        secrets = get_secrets()
        if not secrets.alpaca_live_api_key:
            raise HTTPException(400, "Live API keys not configured. Add them in Settings → API Keys.")
    
    save_config({"broker": {"provider": "alpaca", "mode": mode}})
    reset_clients()
    
    # Return fresh account data
    return await get_account()
```

---

## Implementation Order

1. **Config changes** — new secret fields, `mode` replaces `paper`, migration logic
2. **Factory update** — pick keys by mode
3. **Settings UI** — split key inputs (paper / live sections)
4. **Broker tab** — paper/live radio toggle
5. **Mode badge** in header + `applyAccountMode()` JS
6. **CSS variables** for mode-aware colors
7. **Account switcher dropdown** in header
8. **`/api/broker/switch` endpoint**
9. **Order confirmation gate** for live mode
10. **Test:** switch between paper/live, verify colors change, verify correct account data loads

---

## Alpaca Key Generation (for the user)

### Paper Keys (you probably already have these)
1. Log in at [alpaca.markets](https://alpaca.markets)
2. Go to **Paper Trading** (left sidebar)
3. Click **API Keys** → **Generate**
4. Copy the API Key (starts with `PK`) and Secret Key

### Live Keys (new — requires separate generation)
1. Same Alpaca login
2. Go to **Live Trading** (left sidebar)  
3. Click **API Keys** → **Generate**
4. Copy the API Key (starts with `AK`) and Secret Key
5. **Note:** Your Alpaca account must be approved for live trading (KYC/identity verification). Paper is instant, but live may take 1-2 business days if not already approved.

---

## Verification

1. Paste paper keys → badge shows green "PAPER", header has green accent
2. Paste live keys → switch via dropdown → confirmation dialog → badge turns red "LIVE" with pulse, header tints red
3. Place an order in live mode → extra confirmation dialog with "real money" warning
4. Switch back to paper → instant, no confirmation, green returns
5. Resize window → mode badge still visible and not clipped
6. Reload page → mode persists from `config.yaml`, correct colors load
