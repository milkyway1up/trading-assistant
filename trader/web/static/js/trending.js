// trending.js — fetches /api/trending, renders the social-momentum sidebar list,
// supports one-click add-to-watchlist and Claude pump-risk rating per ticker.

let currentTrending = [];

function tEscape(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function pumpColor(risk) {
  if (risk === "low") return "text-green-400";
  if (risk === "medium") return "text-amber-400";
  return "text-red-400";
}

function trendingRatingColor(r) {
  if (r == null) return "text-slate-500";
  if (r >= 8) return "text-green-400";
  if (r >= 5) return "text-amber-400";
  return "text-red-400";
}

function sourceBadge(label) {
  const colors = {
    WSB: "bg-rose-900/60 text-rose-300",
    RS: "bg-blue-900/60 text-blue-300",
    PS: "bg-amber-900/60 text-amber-300",
    DT: "bg-slate-700 text-slate-300",
    ST: "bg-cyan-900/60 text-cyan-300",
  };
  const cls = colors[label] || "bg-slate-700 text-slate-300";
  return `<span class="px-1 rounded ${cls} text-[10px] uppercase tracking-wide">${label}</span>`;
}

function renderTrendingRow(t, i) {
  const price = t.last_price != null ? `$${t.last_price.toFixed(2)}` : "—";
  const priceCls = t.is_penny ? "text-amber-400" : "text-slate-300";
  const delta = t.delta_pct != null
    ? `<span class="${t.delta_pct >= 0 ? "text-green-400" : "text-red-400"}">${t.delta_pct >= 0 ? "+" : ""}${t.delta_pct}%</span>`
    : "";
  const sources = (t.sources || []).map(sourceBadge).join("");
  const stBadge = t.stocktwits_trending ? sourceBadge("ST") : "";
  const ratingBadge = t.claude_rating != null
    ? `<span class="trending-claude-badge ${trendingRatingColor(t.claude_rating)} font-bold" title="${tEscape(t.claude_reason || "")}">${t.claude_rating}/10</span>`
    : "";
  const pumpBadge = t.pump_risk
    ? `<span class="${pumpColor(t.pump_risk)} text-[10px] uppercase" title="${tEscape(t.claude_reason || "")}">${t.pump_risk}</span>`
    : "";
  return `
    <li class="px-3 py-1 cursor-pointer hover:bg-slate-800 border-b border-slate-800/30"
        data-trending-idx="${i}"
        data-trending-ticker="${tEscape(t.ticker)}"
        title="${tEscape(t.name || t.ticker)}">
      <div class="flex justify-between items-center">
        <span class="font-bold">${t.ticker}</span>
        <span class="flex items-center gap-2">
          ${ratingBadge}
          ${pumpBadge}
          <span class="${priceCls}">${price}</span>
        </span>
      </div>
      <div class="flex justify-between items-center text-slate-400">
        <span class="flex items-center gap-1">${sources}${stBadge}</span>
        <span class="flex items-center gap-2">
          <span class="text-slate-500">${t.mentions}</span>
          ${delta}
          <button
            class="trending-rate-btn text-cyan-400 hover:text-cyan-300 hover:underline"
            data-rate-idx="${i}"
            title="Ask Claude — is this a pump?"
          >rate</button>
          <button
            class="trending-add-btn text-cyan-400 hover:text-cyan-300 hover:underline"
            data-add-ticker="${tEscape(t.ticker)}"
            title="Add to watchlist"
          >+watch</button>
        </span>
      </div>
    </li>`;
}

function paintTrending() {
  const list = document.getElementById("trending-list");
  if (!list) return;
  if (!currentTrending.length) {
    list.innerHTML = `<li class="px-3 py-1 text-slate-500">no trending tickers</li>`;
    return;
  }
  list.innerHTML = currentTrending.map(renderTrendingRow).join("");

  list.querySelectorAll("[data-trending-idx]").forEach((li) => {
    li.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      const t = currentTrending[parseInt(li.dataset.trendingIdx, 10)];
      if (t && window.loadTicker) window.loadTicker(t.ticker);
    });
  });

  list.querySelectorAll(".trending-add-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const ticker = btn.dataset.addTicker;
      const original = btn.textContent;
      btn.textContent = "…";
      btn.disabled = true;
      try {
        const res = await fetch("/api/settings/watchlist/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || res.statusText);
        btn.textContent = data.status === "exists" ? "✓already" : "✓added";
        btn.classList.add("text-green-400");
        btn.classList.remove("text-cyan-400");
      } catch (err) {
        btn.textContent = "fail";
        btn.title = err.message;
        btn.classList.add("text-red-400");
      } finally {
        setTimeout(() => {
          btn.textContent = original;
          btn.disabled = false;
          btn.title = "Add to watchlist";
          btn.classList.remove("text-green-400", "text-red-400");
          btn.classList.add("text-cyan-400");
        }, 2000);
      }
    });
  });

  list.querySelectorAll(".trending-rate-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.dataset.rateIdx, 10);
      const t = currentTrending[idx];
      if (!t) return;
      const original = btn.textContent;
      btn.textContent = "…";
      btn.disabled = true;
      try {
        const res = await fetch("/api/trending/rate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker: t.ticker, social: t }),
        });
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.detail || data.error || res.statusText);
        currentTrending[idx] = {
          ...t,
          claude_rating: data.rating,
          claude_reason: data.reason,
          pump_risk: data.pump_risk,
          claude_verdict: data.verdict,
        };
        paintTrending();
      } catch (err) {
        btn.textContent = "err";
        btn.title = err.message;
      } finally {
        setTimeout(() => {
          btn.textContent = original;
          btn.disabled = false;
          btn.title = "Ask Claude — is this a pump?";
        }, 1500);
      }
    });
  });
}

async function refreshTrending() {
  const list = document.getElementById("trending-list");
  if (!list) return;
  list.innerHTML = `<li class="px-3 py-1 text-slate-500">scanning…</li>`;
  try {
    const includePennies = document.getElementById("trending-pennies-toggle")?.checked ?? true;
    const includeStandard = document.getElementById("trending-standard-toggle")?.checked ?? true;
    const res = await fetch(`/api/trending?limit=20&include_pennies=${includePennies}&include_standard=${includeStandard}`);
    const data = await res.json();
    if (data.error) {
      list.innerHTML = `<li class="px-3 py-1 text-red-400">${tEscape(data.error)}</li>`;
      return;
    }
    currentTrending = data.trending || [];
    paintTrending();
  } catch (e) {
    list.innerHTML = `<li class="px-3 py-1 text-red-400">${tEscape(e.message)}</li>`;
  }
}

window.initTrending = function () {
  const refreshBtn = document.getElementById("trending-refresh");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshTrending);
  const pennyToggle = document.getElementById("trending-pennies-toggle");
  if (pennyToggle) pennyToggle.addEventListener("change", refreshTrending);
  const standardToggle = document.getElementById("trending-standard-toggle");
  if (standardToggle) standardToggle.addEventListener("change", refreshTrending);
  // Don't auto-fetch on dashboard load — these endpoints are external (rate limits).
  // User clicks "scan" to populate.
};
