// analyze.js — Claude analysis modal.

function renderThesis(body, data) {
  if (data.error) {
    body.innerHTML = `<div class="text-red-400">${data.error}</div>`;
    return;
  }
  const r = data.result || data;
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
    </div>
  `;
}

async function runAnalyze(ticker) {
  const body = document.getElementById("analyze-body");
  document.getElementById("analyze-ticker").textContent = ticker;
  document.getElementById("analyze-modal").classList.remove("hidden");
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
