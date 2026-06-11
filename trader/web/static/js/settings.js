// settings.js — modal-driven editor for .env secrets and config.yaml.

let _initialConfig = null;
let _initialSecretStatus = null;

function showStatus(msg, kind = "info") {
  const el = document.getElementById("settings-status");
  el.textContent = msg;
  el.className = "text-xs " + (
    kind === "error" ? "text-red-400" :
    kind === "success" ? "text-green-400" :
    "text-slate-500"
  );
}

async function loadSettings() {
  const res = await fetch("/api/settings");
  if (!res.ok) {
    showStatus("Failed to load settings", "error");
    return;
  }
  const data = await res.json();
  _initialConfig = data.config;
  _initialSecretStatus = data.secrets;

  // Render secret-set indicators (don't pre-fill the inputs themselves)
  for (const [k, v] of Object.entries(data.secrets)) {
    if (k === "schwab_callback_url") {
      const input = document.querySelector(`[data-secret="schwab_callback_url"]`);
      if (input) input.value = v || "";
      continue;
    }
    const status = document.querySelector(`[data-secret-status="${k}"]`);
    if (status) {
      status.textContent = v ? "set" : "not set";
      status.className = "text-xs self-center w-16 " + (v ? "text-green-400" : "text-slate-500");
    }
  }

  // Watchlist
  document.getElementById("watchlist-input").value =
    (data.config.watchlist || []).join("\n");

  // Risk
  for (const [k, v] of Object.entries(data.config.risk || {})) {
    const input = document.querySelector(`[data-risk="${k}"]`);
    if (input) input.value = v;
  }

  // Broker
  const broker = data.config.broker || {};
  document.querySelectorAll('[data-broker="provider"]').forEach((el) => {
    el.checked = el.value === (broker.provider || "alpaca");
  });
  const paperEl = document.querySelector('[data-broker="paper"]');
  if (paperEl) paperEl.checked = !!broker.paper;
}

function readSecretsForm() {
  const out = {};
  document.querySelectorAll("[data-secret]").forEach((el) => {
    const key = el.dataset.secret;
    const val = el.value;
    if (key === "schwab_callback_url") {
      // Always send (it's not really a secret); empty string clears.
      if (val !== (_initialSecretStatus?.schwab_callback_url ?? "")) {
        out[key] = val;
      }
    } else {
      // Only send if user typed something — never overwrite with empty by accident.
      if (val) out[key] = val;
    }
  });
  return out;
}

function readConfigForm() {
  const out = {};
  const tickers = document.getElementById("watchlist-input").value
    .split(/[\s,]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);
  if (JSON.stringify(tickers) !== JSON.stringify(_initialConfig?.watchlist ?? [])) {
    out.watchlist = tickers;
  }

  const risk = {};
  document.querySelectorAll("[data-risk]").forEach((el) => {
    const key = el.dataset.risk;
    const val = parseFloat(el.value);
    if (!Number.isNaN(val) && val !== (_initialConfig?.risk?.[key] ?? null)) {
      risk[key] = val;
    }
  });
  if (Object.keys(risk).length) out.risk = { ..._initialConfig.risk, ...risk };

  // Broker
  const provider = document.querySelector('[data-broker="provider"]:checked')?.value;
  const paper = document.querySelector('[data-broker="paper"]')?.checked;
  const initialBroker = _initialConfig?.broker || {};
  if (provider && (provider !== initialBroker.provider || paper !== !!initialBroker.paper)) {
    out.broker = { ...initialBroker, provider, paper: !!paper };
  }

  return out;
}

async function saveSettings() {
  showStatus("Saving…");
  const secretBody = readSecretsForm();
  const configBody = readConfigForm();

  const tasks = [];
  if (Object.keys(secretBody).length) {
    tasks.push(fetch("/api/settings/secrets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(secretBody),
    }));
  }
  if (Object.keys(configBody).length) {
    tasks.push(fetch("/api/settings/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(configBody),
    }));
  }

  if (!tasks.length) {
    showStatus("No changes", "info");
    return;
  }

  try {
    const responses = await Promise.all(tasks);
    for (const r of responses) {
      if (!r.ok) {
        const err = await r.text();
        showStatus(`Save failed: ${err}`, "error");
        return;
      }
    }
    showStatus("Saved. Reload to apply watchlist changes.", "success");
    await loadSettings();  // refresh status indicators
    // Clear password inputs so they don't linger in DOM
    document.querySelectorAll('[data-secret][type="password"]').forEach((el) => el.value = "");
  } catch (e) {
    showStatus(`Save failed: ${e.message}`, "error");
  }
}

function switchTab(name) {
  document.querySelectorAll(".settings-tab").forEach((b) => {
    const active = b.dataset.tab === name;
    b.classList.toggle("text-cyan-400", active);
    b.classList.toggle("border-cyan-500", active);
    b.classList.toggle("border-transparent", !active);
    b.classList.toggle("text-slate-400", !active);
  });
  document.querySelectorAll("[data-pane]").forEach((p) => {
    p.classList.toggle("hidden", p.dataset.pane !== name);
  });
}

function openModal() {
  document.getElementById("settings-modal").classList.remove("hidden");
  loadSettings();
  showStatus("");
}

function closeModal() {
  document.getElementById("settings-modal").classList.add("hidden");
}

window.initSettings = function () {
  document.getElementById("settings-btn").addEventListener("click", openModal);
  document.getElementById("settings-close").addEventListener("click", closeModal);
  document.getElementById("settings-cancel").addEventListener("click", closeModal);
  document.getElementById("settings-save").addEventListener("click", saveSettings);
  document.querySelectorAll(".settings-tab").forEach((b) => {
    b.addEventListener("click", () => switchTab(b.dataset.tab));
  });
  // Click outside modal closes it
  document.getElementById("settings-modal").addEventListener("click", (e) => {
    if (e.target.id === "settings-modal") closeModal();
  });
  // Esc closes
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !document.getElementById("settings-modal").classList.contains("hidden")) {
      closeModal();
    }
  });
};
