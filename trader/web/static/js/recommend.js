// recommend.js — top-bar Recommend button: ask Claude for entry/stop/target
// and pop the order ticket pre-filled.

async function runRecommend() {
  const btn = document.getElementById("recommend-btn");
  const ticker = window.getActiveTicker ? window.getActiveTicker() : null;
  if (!ticker) return;
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Thinking…";
  try {
    const res = await fetch(`/api/recommend/${encodeURIComponent(ticker)}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(`Recommend failed: ${data.detail || res.status}`);
      return;
    }
    if (data.entry == null || data.stop == null) {
      const conf = data.confidence != null ? `${data.confidence}/10` : "—";
      alert(`No clean entry from Claude (confidence ${conf}).\n\n` +
            `Thesis: ${data.thesis || "—"}\n\n` +
            `Open Analyze for the full breakdown.`);
      return;
    }
    if (window.openOrderFromAnalysis) window.openOrderFromAnalysis(data);
  } catch (e) {
    alert("Recommend failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

window.initRecommend = function () {
  const btn = document.getElementById("recommend-btn");
  if (btn) btn.addEventListener("click", runRecommend);
};
