// setups.js — fetches /api/setups/today, renders the left-rail list.

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
    list.innerHTML = setups.map((s) => {
      const conf = s.confidence != null ? `${(s.confidence * 100).toFixed(0)}%` : "—";
      const rr = s.risk_reward != null ? `${s.risk_reward.toFixed(1)}R` : "";
      return `
        <li class="px-3 py-1 cursor-pointer hover:bg-slate-800 border-b border-slate-800/30"
            data-setup-ticker="${s.ticker}">
          <div class="flex justify-between">
            <span class="font-bold">${s.ticker}</span>
            <span class="text-cyan-400">${conf}</span>
          </div>
          <div class="flex justify-between text-slate-400">
            <span>${s.setup || s.setup_type || ""}</span>
            <span>${rr}</span>
          </div>
        </li>`;
    }).join("");

    list.querySelectorAll("[data-setup-ticker]").forEach((li) => {
      li.addEventListener("click", () => {
        const t = li.dataset.setupTicker;
        if (window.loadTicker) window.loadTicker(t);
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
