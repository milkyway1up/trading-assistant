// setups.js — fetches /api/setups/today, renders the left-rail list.

function escapeAttr(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
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
    const setups = data.setups || [];
    if (!setups.length) {
      list.innerHTML = `<li class="px-3 py-1 text-slate-500">no setups</li>`;
      return;
    }
    list.innerHTML = setups.map((s, i) => {
      const conf = s.confidence != null ? `${(s.confidence * 100).toFixed(0)}%` : "—";
      const rr = s.risk_reward != null ? `${s.risk_reward.toFixed(1)}R` : "";
      const reason = escapeAttr(s.reason || "");
      const setupName = s.setup || s.setup_type || "";
      return `
        <li class="px-3 py-1 cursor-pointer hover:bg-slate-800 border-b border-slate-800/30"
            data-setup-idx="${i}"
            title="${reason}">
          <div class="flex justify-between items-center">
            <span class="font-bold">${s.ticker}</span>
            <span class="flex items-center gap-2">
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
    }).join("");

    // Row click → load chart only
    list.querySelectorAll("[data-setup-idx]").forEach((li) => {
      li.addEventListener("click", (e) => {
        if (e.target.closest(".setup-trade-btn")) return; // handled separately
        const s = setups[parseInt(li.dataset.setupIdx, 10)];
        if (s && window.loadTicker) window.loadTicker(s.ticker);
      });
    });

    // Trade button → load chart + open prefilled order modal
    list.querySelectorAll(".setup-trade-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const s = setups[parseInt(btn.dataset.tradeIdx, 10)];
        if (!s) return;
        if (window.loadTicker) window.loadTicker(s.ticker);
        if (window.openOrderFromSetup) window.openOrderFromSetup(s);
      });
    });
  } catch (e) {
    list.innerHTML = `<li class="px-3 py-1 text-red-400">${e.message}</li>`;
  }
}

window.initSetups = function () {
  document.getElementById("setups-refresh").addEventListener("click", refreshSetups);
  refreshSetups();
};
