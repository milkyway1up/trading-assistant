// journal.js — trades list, stats, sync, annotate, grade.

let trades = [];
let selectedId = null;

function fmtNum(n, d = 2) { return n == null ? "—" : n.toFixed(d); }
function fmtMoney(n) { return n == null ? "—" : `$${n.toFixed(2)}`; }
function fmtPnL(n) {
  if (n == null) return "—";
  const cls = n >= 0 ? "text-green-400" : "text-red-400";
  return `<span class="${cls}">${n >= 0 ? "+" : ""}$${n.toFixed(2)}</span>`;
}
function fmtDate(s) { return s ? s.slice(0, 10) : "—"; }

async function loadTrades() {
  const setup = document.getElementById("journal-filter-setup").value;
  const closed = document.getElementById("journal-closed-only").checked;
  const params = new URLSearchParams();
  if (setup) params.set("setup", setup);
  if (closed) params.set("closed_only", "true");
  params.set("limit", "200");
  const res = await fetch(`/api/journal/trades?${params}`);
  const data = await res.json();
  trades = data.trades || [];
  renderTradesTable();
}

function renderTradesTable() {
  const tbody = document.getElementById("trades-body");
  if (!trades.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="px-3 py-4 text-slate-500">no trades yet — click <em>Sync from broker</em> to pull recent fills.</td></tr>`;
    return;
  }
  tbody.innerHTML = trades.map((t) => `
    <tr class="hover:bg-slate-800 cursor-pointer border-t border-slate-800/50 ${t.id === selectedId ? "bg-slate-800" : ""}" data-id="${t.id}">
      <td class="px-3 py-2 text-slate-500">${t.id}</td>
      <td class="px-3 py-2 font-bold">${t.ticker}</td>
      <td class="px-3 py-2">${t.side}</td>
      <td class="px-3 py-2 text-slate-400">${t.setup_type || "—"}</td>
      <td class="px-3 py-2">${t.quantity ?? "—"}</td>
      <td class="px-3 py-2">${fmtMoney(t.entry_price)}<div class="text-slate-500">${fmtDate(t.entry_time)}</div></td>
      <td class="px-3 py-2">${fmtMoney(t.exit_price)}<div class="text-slate-500">${fmtDate(t.exit_time)}</div></td>
      <td class="px-3 py-2">${fmtPnL(t.realized_pnl)}</td>
      <td class="px-3 py-2">${fmtNum(t.r_multiple, 2)}</td>
      <td class="px-3 py-2 ${t.llm_grade ? "text-cyan-400 font-bold" : "text-slate-500"}">${t.llm_grade || "—"}</td>
    </tr>
  `).join("");
  tbody.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.addEventListener("click", () => selectTrade(parseInt(tr.dataset.id, 10)));
  });
}

function selectTrade(id) {
  selectedId = id;
  renderTradesTable();
  const t = trades.find((x) => x.id === id);
  if (!t) return;
  const detail = document.getElementById("trade-detail");
  const closed = t.exit_price != null;
  detail.innerHTML = `
    <div class="flex justify-between">
      <span class="font-bold text-cyan-400">${t.ticker}</span>
      <span class="text-slate-400">${t.side} · ${t.quantity ?? "—"} sh</span>
    </div>
    <div class="text-xs text-slate-400">
      entry ${fmtMoney(t.entry_price)} ${fmtDate(t.entry_time)}<br/>
      exit ${fmtMoney(t.exit_price)} ${fmtDate(t.exit_time)}<br/>
      P&L ${fmtPnL(t.realized_pnl)} · R ${fmtNum(t.r_multiple, 2)}
    </div>
    <div>
      <label class="block text-xs text-slate-400">Setup</label>
      <input id="annotate-setup" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs" value="${t.setup_type ?? ""}" />
    </div>
    <div>
      <label class="block text-xs text-slate-400">Thesis at entry</label>
      <textarea id="annotate-thesis" rows="3" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs">${t.thesis_at_entry ?? ""}</textarea>
    </div>
    <div>
      <label class="block text-xs text-slate-400">Exit reason</label>
      <input id="annotate-exit-reason" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs" value="${t.exit_reason ?? ""}" />
    </div>
    <div>
      <label class="block text-xs text-slate-400">Notes</label>
      <textarea id="annotate-notes" rows="2" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs">${t.notes ?? ""}</textarea>
    </div>
    <div class="flex gap-2">
      <button id="annotate-save" class="flex-1 px-3 py-1 rounded bg-cyan-700 hover:bg-cyan-600 text-xs">Save</button>
      <button id="grade-btn" class="flex-1 px-3 py-1 rounded border border-slate-700 hover:bg-slate-800 text-xs ${closed ? "" : "opacity-50 cursor-not-allowed"}" ${closed ? "" : "disabled"}>Grade with Claude</button>
    </div>
    ${t.llm_grade ? `
      <div class="border-t border-slate-700 pt-2 mt-2 text-xs">
        <div><span class="text-slate-500">Grade:</span> <span class="text-cyan-400 font-bold">${t.llm_grade}</span></div>
        ${t.llm_lesson ? `<div class="mt-1"><span class="text-slate-500">Lesson:</span> ${t.llm_lesson}</div>` : ""}
        ${t.llm_tags ? `<div class="mt-1"><span class="text-slate-500">Tags:</span> ${t.llm_tags}</div>` : ""}
      </div>
    ` : ""}
    <div id="annotate-status" class="text-xs text-slate-500"></div>
  `;
  document.getElementById("annotate-save").addEventListener("click", () => saveAnnotation(t.id));
  if (closed) document.getElementById("grade-btn").addEventListener("click", () => gradeTrade(t.id));
}

async function saveAnnotation(id) {
  const body = {
    setup_type: document.getElementById("annotate-setup").value || null,
    thesis_at_entry: document.getElementById("annotate-thesis").value || null,
    exit_reason: document.getElementById("annotate-exit-reason").value || null,
    notes: document.getElementById("annotate-notes").value || null,
  };
  const status = document.getElementById("annotate-status");
  status.textContent = "saving…";
  const res = await fetch(`/api/journal/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    status.textContent = data.detail || "save failed";
    return;
  }
  status.textContent = `saved ${data.updated.join(", ") || "—"}`;
  await loadTrades();
  selectTrade(id);
}

async function gradeTrade(id) {
  const status = document.getElementById("annotate-status");
  status.textContent = "asking Claude (may take 30s)…";
  const res = await fetch(`/api/journal/${id}/grade`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    status.textContent = data.detail || "grade failed";
    return;
  }
  status.textContent = "graded";
  await loadTrades();
  selectTrade(id);
}

async function loadStats() {
  const res = await fetch("/api/journal/stats?since_days=30");
  const data = await res.json();
  const el = document.getElementById("journal-stats");
  if (data.error || !res.ok) {
    el.innerHTML = `<div class="text-red-400">${data.error || data.detail || "stats failed"}</div>`;
    return;
  }
  const rows = [
    ["Trades", data.count],
    ["Wins", data.wins],
    ["Losses", data.losses],
    ["Win rate", data.win_rate != null ? `${(data.win_rate * 100).toFixed(0)}%` : "—"],
    ["Avg R", fmtNum(data.avg_r, 2)],
    ["Expectancy", data.expectancy != null ? `$${data.expectancy.toFixed(2)}` : "—"],
    ["Total P&L", data.total_pnl != null ? fmtPnL(data.total_pnl) : "—"],
  ];
  el.innerHTML = rows.map(([k, v]) => `
    <div class="flex justify-between"><span class="text-slate-400">${k}</span><span>${v ?? "—"}</span></div>
  `).join("");

  if (data.by_setup && Object.keys(data.by_setup).length) {
    const setupRows = Object.entries(data.by_setup).map(([k, v]) => {
      const wr = v.win_rate != null ? `${(v.win_rate * 100).toFixed(0)}%` : "—";
      return `<div class="flex justify-between text-xs"><span class="text-slate-400">${k} (${v.count})</span><span>${wr} · ${fmtNum(v.avg_r, 2)}R</span></div>`;
    }).join("");
    el.innerHTML += `<div class="border-t border-slate-700 mt-2 pt-2"><div class="text-xs uppercase text-slate-500 mb-1">By setup</div>${setupRows}</div>`;
  }
}

async function syncFromBroker() {
  const btn = document.getElementById("journal-sync");
  btn.disabled = true;
  btn.textContent = "syncing…";
  try {
    const res = await fetch("/api/journal/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ since_days: 30 }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "sync failed");
    } else {
      btn.textContent = `synced (${data.added ?? 0} new)`;
      await loadTrades();
      await loadStats();
    }
  } finally {
    btn.disabled = false;
    setTimeout(() => { btn.textContent = "Sync from broker"; }, 2500);
  }
}

window.initJournal = function () {
  document.getElementById("journal-sync").addEventListener("click", syncFromBroker);
  document.getElementById("journal-filter-setup").addEventListener("change", loadTrades);
  document.getElementById("journal-closed-only").addEventListener("change", loadTrades);
  loadTrades();
  loadStats();
};
