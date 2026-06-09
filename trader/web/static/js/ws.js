// ws.js — WebSocket client for live ticks + alerts.

(function () {
  const status = document.getElementById("ws-status");
  let ws;
  let reconnectAttempts = 0;

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/stream`);

    ws.onopen = () => {
      status.textContent = "● live";
      status.className = "text-xs text-green-400";
      reconnectAttempts = 0;
    };

    ws.onmessage = (evt) => {
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }
      if (msg.type === "tick") handleTick(msg);
      else if (msg.type === "alert") handleAlert(msg);
    };

    ws.onclose = () => {
      status.textContent = "○ disconnected";
      status.className = "text-xs text-amber-400";
      const delay = Math.min(30_000, 1000 * 2 ** reconnectAttempts++);
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      try { ws.close(); } catch {}
    };
  }

  function handleTick(msg) {
    // Update watchlist quote tag if visible
    const el = document.querySelector(`[data-ticker-price="${msg.ticker}"]`);
    if (el) {
      el.dataset.lastPrice = msg.price;
    }
  }

  function handleAlert(msg) {
    const feed = document.getElementById("alerts-feed");
    if (!feed) return;
    const li = document.createElement("li");
    const ts = new Date(msg.ts * 1000).toLocaleTimeString();
    li.className = `alert-row ${msg.direction || ""}`;
    li.innerHTML = `<span class="text-slate-500">${ts}</span> <strong>${msg.ticker}</strong> ${msg.message}`;
    feed.prepend(li);
    while (feed.children.length > 50) feed.removeChild(feed.lastChild);

    // In-page toast
    showToast(`${msg.ticker}: ${msg.message}`);
  }

  function showToast(text) {
    const t = document.createElement("div");
    t.className = "fixed top-4 right-4 bg-cyan-900 border border-cyan-500 px-4 py-3 rounded shadow-lg z-50";
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 5000);
  }

  connect();
})();
