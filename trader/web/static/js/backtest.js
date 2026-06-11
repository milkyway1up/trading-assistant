// backtest.js — discover strategies, run backtest, render metrics.

async function loadStrategies() {
  const sel = document.getElementById("bt-strategy");
  try {
    const res = await fetch("/api/backtest/strategies");
    const data = await res.json();
    const names = data.strategies || [];
    if (!names.length) {
      sel.innerHTML = `<option value="">no strategies found</option>`;
      return;
    }
    sel.innerHTML = names.map((n) => `<option value="${n}">${n}</option>`).join("");
  } catch (e) {
    sel.innerHTML = `<option value="">${e.message}</option>`;
  }
}

function fmtPct(n) { return n == null ? "—" : `${(n * 100).toFixed(2)}%`; }
function fmtNum(n, d = 2) { return n == null ? "—" : n.toFixed(d); }

function renderResults(r) {
  const el = document.getElementById("bt-results");
  const m = r.metrics || r;
  const tile = (label, value, cls = "") => `
    <div class="bg-slate-800 border border-slate-700 rounded p-3">
      <div class="text-xs uppercase text-slate-500">${label}</div>
      <div class="text-xl font-bold ${cls}">${value}</div>
    </div>
  `;

  const cagr = m.cagr ?? m.CAGR;
  const sharpe = m.sharpe ?? m.sharpe_ratio;
  const dd = m.max_drawdown ?? m.max_dd;
  const wr = m.win_rate;
  const totRet = m.total_return ?? m.cumulative_return;
  const exp = m.expectancy;
  const trades = m.num_trades ?? m.trades_count ?? m.trades;

  el.innerHTML = `
    <div class="text-xs text-slate-400 mb-3">
      <span class="font-bold text-cyan-400">${r.strategy || "—"}</span> ·
      ${r.ticker || "—"} · ${r.period || "—"}
    </div>
    <div class="grid grid-cols-4 gap-3">
      ${tile("Total return", fmtPct(totRet), totRet != null && totRet >= 0 ? "text-green-400" : "text-red-400")}
      ${tile("CAGR", fmtPct(cagr))}
      ${tile("Sharpe", fmtNum(sharpe, 2), sharpe != null && sharpe >= 1 ? "text-green-400" : "")}
      ${tile("Max drawdown", fmtPct(dd), "text-red-400")}
      ${tile("Win rate", fmtPct(wr))}
      ${tile("# Trades", trades ?? "—")}
      ${tile("Expectancy", exp != null ? `$${exp.toFixed(2)}` : "—")}
      ${tile("Final equity", m.final_equity != null ? `$${m.final_equity.toFixed(2)}` : "—")}
    </div>
    <details class="mt-4">
      <summary class="text-xs text-slate-500 cursor-pointer">Raw response</summary>
      <pre class="bg-slate-900 border border-slate-700 rounded p-3 text-xs mt-2 overflow-x-auto">${JSON.stringify(r, null, 2)}</pre>
    </details>
  `;
}

async function runBacktest() {
  const status = document.getElementById("bt-status");
  const btn = document.getElementById("bt-run");
  btn.disabled = true;
  status.textContent = "running…";
  const body = {
    strategy: document.getElementById("bt-strategy").value,
    ticker: document.getElementById("bt-ticker").value.trim().toUpperCase(),
    period: document.getElementById("bt-period").value,
    initial_cash: parseFloat(document.getElementById("bt-cash").value) || 10000,
  };
  try {
    const res = await fetch("/api/backtest/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      status.textContent = "";
      document.getElementById("bt-results").innerHTML = `<div class="text-red-400">${data.detail || "backtest failed"}</div>`;
      return;
    }
    status.textContent = "done";
    renderResults(data);
  } catch (e) {
    status.textContent = "";
    document.getElementById("bt-results").innerHTML = `<div class="text-red-400">${e.message}</div>`;
  } finally {
    btn.disabled = false;
  }
}

window.initBacktest = function () {
  loadStrategies();
  document.getElementById("bt-run").addEventListener("click", runBacktest);
};
