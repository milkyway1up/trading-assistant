// analyze.js — Claude analysis modal.

let lastAnalysis = null;
let lastAnalyzedTicker = null;

function renderThesis(body, data) {
  if (data.error) {
    body.innerHTML = `<div class="text-red-400">${data.error}</div>`;
    return;
  }
  const r = data.result || data;
  lastAnalysis = r;
  const lvls = (r.key_levels || []).map((l) => `<li>${typeof l === "object" ? `${l.label || ""} <span class="text-slate-400">${l.price ?? ""}</span>` : l}</li>`).join("");
  const cats = (r.catalysts || []).map((c) => `<li>${c}</li>`).join("");
  const risks = (r.risks || []).map((c) => `<li>${c}</li>`).join("");
  const conf = r.confidence != null ? `<span class="text-cyan-400">${r.confidence}/10</span>` : "—";
  body.innerHTML = `
    <div class="space-y-4">
      <div>
        <div class="text-xs uppercase text-slate-500">Thesis</div>
        <div class="mt-1 whitespace-pre-wrap">${r.thesis || "—"}</div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <div class="text-xs uppercase text-slate-500">Bias / horizon</div>
          <div class="mt-1">${r.bias || "—"} · ${r.time_horizon || "—"}</div>
        </div>
        <div>
          <div class="text-xs uppercase text-slate-500">Confidence</div>
          <div class="mt-1">${conf}</div>
        </div>
        <div>
          <div class="text-xs uppercase text-slate-500">Entry zone</div>
          <div class="mt-1">${r.entry_zone || r.ideal_entry || "—"}</div>
        </div>
        <div>
          <div class="text-xs uppercase text-slate-500">Stop / target</div>
          <div class="mt-1">${r.stop ?? "—"} / ${r.target ?? "—"}</div>
        </div>
      </div>
      ${cats ? `<div><div class="text-xs uppercase text-slate-500">Catalysts</div><ul class="list-disc list-inside mt-1 space-y-0.5">${cats}</ul></div>` : ""}
      ${lvls ? `<div><div class="text-xs uppercase text-slate-500">Key levels</div><ul class="list-disc list-inside mt-1 space-y-0.5">${lvls}</ul></div>` : ""}
      ${risks ? `<div><div class="text-xs uppercase text-slate-500">Risks</div><ul class="list-disc list-inside mt-1 space-y-0.5 text-amber-300">${risks}</ul></div>` : ""}
      <div class="pt-2 border-t border-slate-800">
        <button id="analyze-trade-btn"
          class="px-3 py-1 rounded bg-amber-500 text-black text-sm font-bold hover:bg-amber-400 disabled:opacity-50"
          ${(r.ideal_entry == null && r.entry_zone == null) ? "disabled title='No entry level returned'" : ""}
        >Trade This →</button>
      </div>
    </div>
  `;
  const tradeBtn = document.getElementById("analyze-trade-btn");
  if (tradeBtn) {
    tradeBtn.addEventListener("click", () => openOrderFromAnalysisResult(r));
  }
}

function openOrderFromAnalysisResult(r) {
  if (!window.openOrderFromAnalysis) return;
  let entry = r.ideal_entry;
  if (entry == null && r.entry_zone != null) {
    if (typeof r.entry_zone === "number") {
      entry = r.entry_zone;
    } else if (typeof r.entry_zone === "string") {
      const parts = r.entry_zone.replace(/\$/g, "").replace(/,/g, "").split(/[-–—]/);
      const nums = parts.map(p => parseFloat(p)).filter(n => !isNaN(n));
      if (nums.length) entry = nums.reduce((a, b) => a + b, 0) / nums.length;
    }
  }
  const bias = (r.bias || r.trend || "").toLowerCase();
  const side = bias.includes("down") || bias.includes("bear") || bias.includes("short") ? "sell" : "buy";
  window.openOrderFromAnalysis({
    ticker: lastAnalyzedTicker || r.ticker,
    side,
    entry,
    stop: r.stop ?? r.stop_level,
    target: r.target,
    confidence: r.confidence,
    thesis: r.thesis,
    time_horizon_days: r.time_horizon_days,
  });
}

async function runAnalyze(ticker) {
  const body = document.getElementById("analyze-body");
  document.getElementById("analyze-ticker").textContent = ticker;
  document.getElementById("analyze-modal").classList.remove("hidden");
  lastAnalyzedTicker = ticker;
  lastAnalysis = null;
  body.innerHTML = `<div class="text-slate-500">Asking Claude about ${ticker}… (this can take 20–40s)</div>`;
  try {
    const res = await fetch(`/api/analyze/${encodeURIComponent(ticker)}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      body.innerHTML = `<div class="text-red-400">${data.detail || "analysis failed"}</div>`;
      return;
    }
    renderThesis(body, data);
  } catch (e) {
    body.innerHTML = `<div class="text-red-400">${e.message}</div>`;
  }
}

window.initAnalyze = function () {
  document.getElementById("analyze-btn").addEventListener("click", () => {
    const t = window.getActiveTicker ? window.getActiveTicker() : "SPY";
    runAnalyze(t);
  });
  document.getElementById("analyze-close").addEventListener("click", () => {
    document.getElementById("analyze-modal").classList.add("hidden");
  });
};
