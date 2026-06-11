// setups.js — fetches /api/setups/today, renders the left-rail list,
// and (on demand) sends the top N to Claude for a 1-10 rating.

let currentSetups = [];

function escapeAttr(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function ratingColor(r) {
  if (r == null) return "text-slate-500";
  if (r >= 8) return "text-green-400";
  if (r >= 5) return "text-amber-400";
  return "text-red-400";
}

function renderSetupRow(s, i) {
  const conf = s.confidence != null ? `${(s.confidence * 100).toFixed(0)}%` : "—";
  const rr = s.risk_reward != null ? `${s.risk_reward.toFixed(1)}R` : "";
  const reason = escapeAttr(s.reason || "");
  const setupName = s.setup || s.setup_type || "";
  const ratingBadge = s.claude_rating != null
    ? `<span class="claude-badge ${ratingColor(s.claude_rating)} font-bold" title="${escapeAttr(s.claude_reason || "")}">${s.claude_rating}/10</span>`
    : "";
  return `
    <li class="px-3 py-1 cursor-pointer hover:bg-slate-800 border-b border-slate-800/30"
        data-setup-idx="${i}"
        data-setup-ticker="${escapeAttr(s.ticker)}"
        title="${reason}">
      <div class="flex justify-between items-center">
        <span class="font-bold">${s.ticker}</span>
        <span class="flex items-center gap-2">
          ${ratingBadge}
          <span class="text-cyan-400">${conf}</span>
          <button
            class="setup-trade-btn text-xs text-cyan-400 hover:text-cyan-300 hover:underline"
            data-trade-idx="${i}"
            title="Pre-fill order ticket from this setup"
          >trade →</button>
        </span>
      </div>
      <div class="flex justify-between text-slate-400">
        <span>${setupName}</span>
        <span>${rr}</span>
      </div>
    </li>`;
}

function paintList() {
  const list = document.getElementById("setups-list");
  if (!currentSetups.length) {
    list.innerHTML = `<li class="px-3 py-1 text-slate-500">no setups</li>`;
    return;
  }
  list.innerHTML = currentSetups.map(renderSetupRow).join("");

  list.querySelectorAll("[data-setup-idx]").forEach((li) => {
    li.addEventListener("click", (e) => {
      if (e.target.closest(".setup-trade-btn")) return;
      const s = currentSetups[parseInt(li.dataset.setupIdx, 10)];
      if (s && window.loadTicker) window.loadTicker(s.ticker);
    });
  });

  list.querySelectorAll(".setup-trade-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const s = currentSetups[parseInt(btn.dataset.tradeIdx, 10)];
      if (!s) return;
      if (window.loadTicker) window.loadTicker(s.ticker);
      if (window.openOrderFromSetup) window.openOrderFromSetup(s);
    });
  });
}

async function refreshSetups() {
  const list = document.getElementById("setups-list");
  list.innerHTML = `<li class="px-3 py-1 text-slate-500">scanning…</li>`;
  try {
    const res = await fetch("/api/setups/today?top=15");
    const data = await res.json();
    if (data.error) {
      list.innerHTML = `<li class="px-3 py-1 text-red-400">${data.error}</li>`;
      return;
    }
    currentSetups = data.setups || [];
    paintList();
  } catch (e) {
    list.innerHTML = `<li class="px-3 py-1 text-red-400">${e.message}</li>`;
  }
}

async function rateTopSetups() {
  const btn = document.getElementById("setups-rate");
  const originalLabel = btn.textContent;
  btn.textContent = "rating…";
  btn.disabled = true;

  // Show a placeholder badge on the top 4 rows
  document.querySelectorAll("#setups-list [data-setup-idx]").forEach((li, i) => {
    if (i >= 4) return;
    if (!li.querySelector(".claude-badge")) {
      const span = document.createElement("span");
      span.className = "claude-badge text-xs text-slate-500";
      span.textContent = "…";
      const anchor = li.querySelector(".text-cyan-400");
      if (anchor) anchor.before(span);
    }
  });

  try {
    const res = await fetch("/api/setups/rate?top=4", { method: "POST" });
    const data = await res.json();
    if (data.error) {
      btn.title = data.error;
      btn.textContent = "error";
      return;
    }
    const rated = data.rated || [];
    // Merge ratings into currentSetups, then re-sort: rated rows first, by rating desc
    const ratingByTicker = {};
    rated.forEach((r) => {
      ratingByTicker[r.ticker] = {
        rating: r.claude_rating,
        reason: r.claude_reason,
      };
    });
    currentSetups = currentSetups.map((s) => {
      const r = ratingByTicker[s.ticker];
      return r ? { ...s, claude_rating: r.rating, claude_reason: r.reason } : s;
    });
    currentSetups.sort((a, b) => {
      const ra = a.claude_rating ?? -1;
      const rb = b.claude_rating ?? -1;
      if (rb !== ra) return rb - ra;
      return (b.confidence ?? 0) - (a.confidence ?? 0);
    });
    paintList();
  } catch (e) {
    btn.title = e.message;
    btn.textContent = "error";
  } finally {
    setTimeout(() => {
      btn.textContent = originalLabel;
      btn.disabled = false;
      btn.title = "Send top setups to Claude for a 1-10 rating";
    }, 1500);
  }
}

window.initSetups = function () {
  document.getElementById("setups-refresh").addEventListener("click", refreshSetups);
  const rateBtn = document.getElementById("setups-rate");
  if (rateBtn) rateBtn.addEventListener("click", rateTopSetups);
  refreshSetups();
};
