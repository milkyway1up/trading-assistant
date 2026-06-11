// account.js — polls /api/account, populates right-rail Account + Positions panels.

function fmtMoney(n) {
  if (n == null || isNaN(n)) return "—";
  const s = Math.abs(n) >= 1000
    ? n.toLocaleString(undefined, { maximumFractionDigits: 0 })
    : n.toFixed(2);
  return `$${s}`;
}

function fmtSigned(n) {
  if (n == null || isNaN(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${fmtMoney(n)}`;
}

async function refreshAccount() {
  let data;
  try {
    const res = await fetch("/api/account");
    data = await res.json();
  } catch (e) {
    document.getElementById("account-status").textContent = "offline";
    document.getElementById("account-status").className = "text-red-400";
    return;
  }

  const status = document.getElementById("account-status");
  if (!data.connected) {
    status.textContent = "no broker";
    status.className = "text-amber-400";
    status.title = data.error || "configure a broker in Settings → Broker";
    document.getElementById("account-equity").textContent = "—";
    document.getElementById("settled-cash").textContent = "—";
    document.getElementById("buying-power").textContent = "—";
    document.getElementById("day-pnl").textContent = "—";
    document.getElementById("positions-list").innerHTML =
      `<li class="text-slate-500">${data.error ? "broker error" : "—"}</li>`;
    return;
  }

  status.textContent = "live";
  status.className = "text-green-400";
  status.title = "";

  const acct = data.account || {};
  document.getElementById("account-equity").textContent = fmtMoney(acct.equity);
  document.getElementById("settled-cash").textContent = fmtMoney(acct.settled_cash ?? acct.cash);
  document.getElementById("buying-power").textContent = fmtMoney(acct.buying_power);

  const dp = document.getElementById("day-pnl");
  const pl = data.day_pl;
  dp.textContent = fmtSigned(pl);
  dp.className = pl == null ? "" : pl >= 0 ? "text-green-400" : "text-red-400";

  const list = document.getElementById("positions-list");
  const positions = data.positions || [];
  if (!positions.length) {
    list.innerHTML = `<li class="text-slate-500">no open positions</li>`;
    return;
  }
  list.innerHTML = positions.map((p) => {
    const upl = p.unrealized_pl;
    const cls = upl == null ? "text-slate-400" : upl >= 0 ? "text-green-400" : "text-red-400";
    const qty = p.qty ?? p.quantity ?? "";
    return `
      <li class="flex justify-between py-0.5 border-b border-slate-800/40 cursor-pointer hover:bg-slate-800"
          data-pos-ticker="${p.ticker || p.symbol}">
        <span><span class="font-bold">${p.ticker || p.symbol}</span> <span class="text-slate-500">${qty}</span></span>
        <span class="${cls}">${fmtSigned(upl)}</span>
      </li>`;
  }).join("");

  list.querySelectorAll("[data-pos-ticker]").forEach((li) => {
    li.addEventListener("click", () => {
      const t = li.dataset.posTicker;
      if (window.loadTicker) window.loadTicker(t);
    });
  });
}

window.initAccount = function () {
  refreshAccount();
  setInterval(refreshAccount, 10_000);
};
