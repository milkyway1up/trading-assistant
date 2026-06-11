// chart.js — lightweight-charts setup, timeframe switching, EMA + RSI overlays.

let mainChart, candleSeries, ema20Series, ema50Series, ema200Series, volumeSeries;
let rsiChart, rsiSeries, rsiOverboughtLine, rsiOversoldLine;
let activeTicker = "SPY";
let activeTimeframe = "1d";

const CHART_COLORS = {
  background: "#0f172a",
  grid: "#1e293b",
  text: "#94a3b8",
  up: "#22c55e",
  down: "#ef4444",
  ema20: "#fbbf24",
  ema50: "#a78bfa",
  ema200: "#f472b6",
  volume: "#475569",
  rsi: "#06b6d4",
  rsiBand: "#475569",
};

function makeChart(el, opts = {}) {
  return LightweightCharts.createChart(el, {
    autoSize: true,
    layout: {
      background: { color: CHART_COLORS.background },
      textColor: CHART_COLORS.text,
    },
    grid: {
      vertLines: { color: CHART_COLORS.grid },
      horzLines: { color: CHART_COLORS.grid },
    },
    timeScale: { timeVisible: true, secondsVisible: false },
    rightPriceScale: { borderColor: CHART_COLORS.grid },
    crosshair: { mode: 0 },
    ...opts,
  });
}

function initCharts() {
  const chartEl = document.getElementById("chart");
  const rsiEl = document.getElementById("rsi-chart");

  mainChart = makeChart(chartEl);
  candleSeries = mainChart.addCandlestickSeries({
    upColor: CHART_COLORS.up,
    downColor: CHART_COLORS.down,
    borderUpColor: CHART_COLORS.up,
    borderDownColor: CHART_COLORS.down,
    wickUpColor: CHART_COLORS.up,
    wickDownColor: CHART_COLORS.down,
  });

  ema20Series = mainChart.addLineSeries({ color: CHART_COLORS.ema20, lineWidth: 1, title: "EMA20" });
  ema50Series = mainChart.addLineSeries({ color: CHART_COLORS.ema50, lineWidth: 1, title: "EMA50" });
  ema200Series = mainChart.addLineSeries({ color: CHART_COLORS.ema200, lineWidth: 1, title: "EMA200" });

  volumeSeries = mainChart.addHistogramSeries({
    color: CHART_COLORS.volume,
    priceFormat: { type: "volume" },
    priceScaleId: "vol",
    scaleMargins: { top: 0.85, bottom: 0 },
  });

  rsiChart = makeChart(rsiEl);
  rsiSeries = rsiChart.addLineSeries({ color: CHART_COLORS.rsi, lineWidth: 2, title: "RSI(14)" });

  // Sync time scales
  mainChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
    if (range) rsiChart.timeScale().setVisibleRange(range);
  });

  // autoSize handles resize — no manual handler needed.
}

// EMA implementation (client-side; backend will provide pre-computed for perf later)
function ema(values, period) {
  const k = 2 / (period + 1);
  const out = [];
  let prev = null;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (prev == null) {
      prev = v;
    } else {
      prev = v * k + prev * (1 - k);
    }
    out.push(prev);
  }
  return out;
}

// Wilder's RSI
function rsi(closes, period = 14) {
  if (closes.length < period + 1) return Array(closes.length).fill(null);
  const out = Array(closes.length).fill(null);
  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gains += diff;
    else losses -= diff;
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

async function loadTicker(ticker, timeframe) {
  activeTicker = ticker;
  activeTimeframe = timeframe;
  document.getElementById("active-ticker").textContent = ticker;

  const res = await fetch(`/api/bars/${ticker}?timeframe=${timeframe}`);
  const data = await res.json();
  const bars = data.bars || [];
  if (!bars.length) return;

  candleSeries.setData(bars);
  volumeSeries.setData(bars.map((b) => ({
    time: b.time,
    value: b.volume,
    color: b.close >= b.open ? CHART_COLORS.up + "66" : CHART_COLORS.down + "66",
  })));

  const closes = bars.map((b) => b.close);
  const e20 = ema(closes, 20);
  const e50 = ema(closes, 50);
  const e200 = ema(closes, 200);
  ema20Series.setData(bars.map((b, i) => ({ time: b.time, value: e20[i] })));
  ema50Series.setData(bars.map((b, i) => ({ time: b.time, value: e50[i] })));
  ema200Series.setData(bars.map((b, i) => ({ time: b.time, value: e200[i] })));

  const rsiVals = rsi(closes, 14);
  rsiSeries.setData(
    bars
      .map((b, i) => rsiVals[i] != null ? { time: b.time, value: rsiVals[i] } : null)
      .filter(Boolean)
  );

  // Update quote tag
  const last = bars[bars.length - 1];
  const prev = bars[bars.length - 2] || last;
  const chgPct = ((last.close - prev.close) / prev.close * 100).toFixed(2);
  const tag = document.getElementById("active-quote");
  tag.textContent = `$${last.close.toFixed(2)}  ${chgPct >= 0 ? "+" : ""}${chgPct}%  (${data.source})`;
  tag.className = chgPct >= 0 ? "text-green-400 text-sm" : "text-red-400 text-sm";

  mainChart.timeScale().fitContent();
}

function wireTimeframeButtons() {
  document.querySelectorAll(".tf-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tf-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadTicker(activeTicker, btn.dataset.tf);
    });
  });
}

function wireWatchlist() {
  document.querySelectorAll(".watch-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".watch-item").forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      loadTicker(item.dataset.ticker, activeTimeframe);
    });
  });
}

async function refreshWatchlistQuotes(watchlist) {
  await Promise.all(watchlist.map(async (t) => {
    try {
      const res = await fetch(`/api/quote/${t}`);
      const q = await res.json();
      const el = document.querySelector(`[data-ticker-price="${t}"]`);
      if (el) {
        const sign = q.change_pct >= 0 ? "+" : "";
        el.textContent = `${sign}${q.change_pct.toFixed(2)}%`;
        el.className = q.change_pct >= 0 ? "text-xs text-green-400" : "text-xs text-red-400";
      }
    } catch (e) { /* ignore */ }
  }));
}

window.initDashboard = function (opts) {
  initCharts();
  wireTimeframeButtons();
  wireWatchlist();
  loadTicker(opts.defaultTicker, "1d");
  refreshWatchlistQuotes(opts.watchlist);
  setInterval(() => refreshWatchlistQuotes(opts.watchlist), 30_000);
};

window.loadTicker = (ticker) => loadTicker(ticker, activeTimeframe);
window.getActiveTicker = () => activeTicker;
