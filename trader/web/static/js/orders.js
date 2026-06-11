// orders.js — order ticket modal: preview + submit.

let lastPreview = null;

function $(id) { return document.getElementById(id); }

function openOrderModal() {
  const ticker = window.getActiveTicker ? window.getActiveTicker() : "SPY";
  $("order-ticker").value = ticker;
  $("order-side").value = "buy";
  $("order-entry").value = "";
  $("order-stop").value = "";
  $("order-target").value = "";
  $("order-risk").value = "1.0";
  $("order-qty").value = "";
  $("order-type").value = "limit";
  $("order-preview").innerHTML = `<div class="text-slate-500">Fill in entry + stop, then click Preview.</div>`;
  $("order-submit-btn").disabled = true;
  $("order-status").textContent = "";
  lastPreview = null;
  $("order-modal").classList.remove("hidden");
}

function closeOrderModal() {
  $("order-modal").classList.add("hidden");
}

function readOrderForm() {
  const num = (id) => {
    const v = $(id).value;
    return v === "" ? null : parseFloat(v);
  };
  return {
    ticker: $("order-ticker").value.trim().toUpperCase(),
    side: $("order-side").value,
    entry: num("order-entry"),
    stop: num("order-stop"),
    target: num("order-target"),
    risk_pct: num("order-risk"),
    qty: $("order-qty").value === "" ? null : parseInt($("order-qty").value, 10),
    type: $("order-type").value,
  };
}

function renderPreview(p) {
  if (!p.ok) {
    const fails = (p.failures || []).map((f) => `<li class="text-red-400">• ${f}</li>`).join("");
    $("order-preview").innerHTML = `
      <div class="text-red-400 font-bold mb-1">Risk guard blocked this order</div>
      <ul class="space-y-0.5">${fails || `<li>—</li>`}</ul>
      <div class="mt-2 text-slate-400">qty=${p.qty ?? "—"} · order value=${p.order_value != null ? "$" + p.order_value.toFixed(2) : "—"}</div>
    `;
    $("order-submit-btn").disabled = true;
    return;
  }
  const rr = p.risk_reward != null ? p.risk_reward.toFixed(2) : "—";
  const cls = (n, good) => good ? "text-green-400" : n != null ? "text-amber-400" : "text-slate-400";
  $("order-preview").innerHTML = `
    <div class="grid grid-cols-2 gap-x-4 gap-y-0.5">
      <div class="text-slate-400">Quantity</div><div class="font-bold">${p.qty}</div>
      <div class="text-slate-400">Order value</div><div>$${(p.order_value || 0).toFixed(2)}</div>
      <div class="text-slate-400">Dollar risk</div><div class="text-amber-400">$${(p.dollar_risk || 0).toFixed(2)}</div>
      <div class="text-slate-400">Risk %</div><div>${(p.risk_pct_actual || 0).toFixed(2)}%</div>
      <div class="text-slate-400">Position %</div><div>${(p.position_pct || 0).toFixed(1)}%</div>
      <div class="text-slate-400">Risk : Reward</div><div class="${rr !== "—" && parseFloat(rr) >= 1.5 ? "text-green-400" : "text-amber-400"}">1 : ${rr}</div>
      <div class="text-slate-400">Equity</div><div>$${(p.equity || 0).toFixed(2)}</div>
      <div class="text-slate-400">Settled cash</div><div>$${(p.settled_cash || 0).toFixed(2)}</div>
    </div>
  `;
  $("order-submit-btn").disabled = false;
}

async function previewOrder() {
  const body = readOrderForm();
  $("order-status").textContent = "previewing…";
  try {
    const res = await fetch("/api/orders/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      $("order-preview").innerHTML = `<div class="text-red-400">${data.detail || "preview failed"}</div>`;
      $("order-submit-btn").disabled = true;
      $("order-status").textContent = "";
      return;
    }
    lastPreview = data;
    renderPreview(data);
    $("order-status").textContent = "preview ok";
  } catch (e) {
    $("order-preview").innerHTML = `<div class="text-red-400">${e.message}</div>`;
    $("order-status").textContent = "";
  }
}

async function submitOrder() {
  if (!lastPreview || !lastPreview.ok) return;
  if (!confirm("Place this order?")) return;
  const body = readOrderForm();
  $("order-status").textContent = "submitting…";
  $("order-submit-btn").disabled = true;
  try {
    const res = await fetch("/api/orders/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      $("order-status").textContent = "rejected";
      $("order-preview").innerHTML = `<div class="text-red-400">${data.detail || "submit failed"}</div>`;
      return;
    }
    $("order-status").textContent = `submitted · order id ${data.order_id ?? "—"}`;
    setTimeout(closeOrderModal, 1500);
  } catch (e) {
    $("order-status").textContent = `error: ${e.message}`;
  }
}

window.initOrders = function () {
  $("order-btn").addEventListener("click", openOrderModal);
  $("order-close").addEventListener("click", closeOrderModal);
  $("order-preview-btn").addEventListener("click", previewOrder);
  $("order-submit-btn").addEventListener("click", submitOrder);
};
