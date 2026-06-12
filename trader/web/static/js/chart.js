// chart.js — lightweight-charts setup, timeframe switching, EMA + RSI + Ichimoku overlays.

let mainChart, candleSeries, ema20Series, ema50Series, ema200Series, volumeSeries, volumeSmaSeries;
let tenkanSeries, kijunSeries, spanASeries, spanBSeries, chikouSeries;
let rsiChart, rsiSeries;
let activeTicker = "SPY";
let activeTimeframe = "1d";
let ichimokuVisible = true;
let lastBars = [];

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
  volumeUp: "#22c55eaa",
  volumeDown: "#ef4444aa",
  volumeSma: "#60a5fa",
  rsi: "#06b6d4",
  rsiBand: "#475569",
  tenkan: "#2962FF",
  kijun: "#B71C1C",
  spanA: "rgba(0, 150, 136, 0.6)",
  spanB: "rgba(239, 83, 80, 0.6)",
  spanAFill: "rgba(0, 150, 136, 0.15)",
  spanBFill: "rgba(239, 83, 80, 0.15)",
  chikou: "#4CAF50",
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

  // Ichimoku cloud — drawn first (under the candles) using two area series so the
  // shaded fills sit at the bottom of the z-order. Fill color flips depending on
  // whether Span A is above or below Span B (we paint twice and let lightweight-
  // charts mask the lower band).
  // Area series fill DOWN from the line to chart bottom. Fading bottomColor
  // to fully transparent keeps the tint near the cloud lines without painting
  // the entire bottom half of the chart.
  spanBSeries = mainChart.addAreaSeries({
    topColor: CHART_COLORS.spanBFill,
    bottomColor: "rgba(239, 83, 80, 0)",
    lineColor: CHART_COLORS.spanB,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  spanASeries = mainChart.addAreaSeries({
    topColor: CHART_COLORS.spanAFill,
    bottomColor: "rgba(0, 150, 136, 0)",
    lineColor: CHART_COLORS.spanA,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });

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

  tenkanSeries = mainChart.addLineSeries({
    color: CHART_COLORS.tenkan, lineWidth: 1, title: "Tenkan",
    priceLineVisible: false, lastValueVisible: false,
  });
  kijunSeries = mainChart.addLineSeries({
    color: CHART_COLORS.kijun, lineWidth: 1, title: "Kijun",
    priceLineVisible: false, lastValueVisible: false,
  });
  chikouSeries = mainChart.addLineSeries({
    color: CHART_COLORS.chikou, lineWidth: 1, lineStyle: 2, title: "Chikou",
    priceLineVisible: false, lastValueVisible: false,
  });

  volumeSeries = mainChart.addHistogramSeries({
    color: CHART_COLORS.volume,
    priceFormat: { type: "volume" },
    priceScaleId: "vol",
    scaleMargins: { top: 0.85, bottom: 0 },
  });
  volumeSmaSeries = mainChart.addLineSeries({
    color: CHART_COLORS.volumeSma,
    lineWidth: 1,
    priceScaleId: "vol",
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });

  rsiChart = makeChart(rsiEl);
  rsiSeries = rsiChart.addLineSeries({ color: CHART_COLORS.rsi, lineWidth: 2, title: "RSI(14)" });

  mainChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
    if (range) rsiChart.timeScale().setVisibleRange(range);
  });
}

function ema(values, period) {
  const k = 2 / (period + 1);
  const out = [];
  let prev = null;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (prev == null) prev = v;
    else prev = v * k + prev * (1 - k);
    out.push(prev);
  }
  return out;
}

function sma(values, period) {
  const out = Array(values.length).fill(null);
  if (values.length < period) return out;
  let sum = 0;
  for (let i = 0; i < period; i++) sum += values[i];
  out[period - 1] = sum / period;
  for (let i = period; i < values.length; i++) {
    sum += values[i] - values[i - period];
    out[i] = sum / period;
  }
  return out;
}

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

// Ichimoku — returns {tenkan, kijun, spanA, spanB, chikou} as arrays aligned to bars,
// plus `forwardTimes` (displaced timestamps for Span A/B) so they project ahead of the
// last bar by `displacement` periods.
function ichimoku(bars, tenkanP = 9, kijunP = 26, spanBP = 52, displacement = 26) {
  const n = bars.length;
  const tenkan = Array(n).fill(null);
  const kijun = Array(n).fill(null);
  const spanARaw = Array(n).fill(null);
  const spanBRaw = Array(n).fill(null);
  const chikou = Array(n).fill(null);

  function midpoint(idx, period) {
    let hi = -Infinity, lo = Infinity;
    const start = Math.max(0, idx - period + 1);
    if (idx - start + 1 < period) return null;
    for (let i = start; i <= idx; i++) {
      if (bars[i].high > hi) hi = bars[i].high;
      if (bars[i].low < lo) lo = bars[i].low;
    }
    return (hi + lo) / 2;
  }

  for (let i = 0; i < n; i++) {
    tenkan[i] = midpoint(i, tenkanP);
    kijun[i] = midpoint(i, kijunP);
    spanBRaw[i] = midpoint(i, spanBP);
    if (tenkan[i] != null && kijun[i] != null) {
      spanARaw[i] = (tenkan[i] + kijun[i]) / 2;
    }
    // Chikou is the close shifted backward by `displacement` bars.
    if (i + displacement < n) {
      chikou[i + displacement] = null; // initialize, set below
    }
  }
  for (let i = 0; i < n; i++) {
    if (i - displacement >= 0) chikou[i - displacement] = bars[i].close;
  }

  // Build displaced spanA/spanB series with synthesized future timestamps.
  // lightweight-charts requires monotonically-increasing timestamps, so we
  // extend by inferring the bar interval from the last few bars.
  const spanA = [];
  const spanB = [];
  let interval = null;
  if (n >= 2) {
    const t0 = typeof bars[n - 1].time === "number" ? bars[n - 1].time : Date.parse(bars[n - 1].time) / 1000;
    const t1 = typeof bars[n - 2].time === "number" ? bars[n - 2].time : Date.parse(bars[n - 2].time) / 1000;
    interval = t0 - t1;
    if (!isFinite(interval) || interval <= 0) interval = 86400; // fallback: 1 day
  }
  for (let i = 0; i < n; i++) {
    const tIdx = i + displacement;
    let t;
    if (tIdx < n) {
      t = bars[tIdx].time;
    } else if (interval && typeof bars[n - 1].time === "number") {
      t = bars[n - 1].time + (tIdx - (n - 1)) * interval;
    } else if (interval && typeof bars[n - 1].time === "string") {
      // Daily timeframe: time is "YYYY-MM-DD". Skip future projection — chart still
      // shows the cloud built from past spanA/B values up to the last bar.
      continue;
    } else {
      continue;
    }
    if (spanARaw[i] != null) spanA.push({ time: t, value: spanARaw[i] });
    if (spanBRaw[i] != null) spanB.push({ time: t, value: spanBRaw[i] });
  }

  return { tenkan, kijun, spanA, spanB, chikou };
}

function setSeriesIfData(series, data) {
  try { series.setData(data); } catch (e) { /* ignore */ }
}

function applyIchimokuVisibility() {
  const visible = ichimokuVisible;
  [tenkanSeries, kijunSeries, spanASeries, spanBSeries, chikouSeries].forEach((s) => {
    if (s) s.applyOptions({ visible });
  });
  const btn = document.getElementById("toggle-ichimoku");
  if (btn) {
    if (visible) btn.classList.add("bg-slate-800", "border-cyan-500");
    else btn.classList.remove("bg-slate-800", "border-cyan-500");
  }
}

async function _loadTicker(ticker, timeframe) {
  activeTicker = ticker;
  activeTimeframe = timeframe;
  document.getElementById("active-ticker").textContent = ticker;

  const res = await fetch(`/api/bars/${ticker}?timeframe=${timeframe}`);
  const data = await res.json();
  const bars = data.bars || [];
  if (!bars.length) return;
  lastBars = bars;

  candleSeries.setData(bars);
  volumeSeries.setData(bars.map((b) => ({
    time: b.time,
    value: b.volume,
    color: b.close >= b.open ? CHART_COLORS.volumeUp : CHART_COLORS.volumeDown,
  })));

  const closes = bars.map((b) => b.close);
  const volumes = bars.map((b) => b.volume);
  const e20 = ema(closes, 20);
  const e50 = ema(closes, 50);
  const e200 = ema(closes, 200);
  ema20Series.setData(bars.map((b, i) => ({ time: b.time, value: e20[i] })));
  ema50Series.setData(bars.map((b, i) => ({ time: b.time, value: e50[i] })));
  ema200Series.setData(bars.map((b, i) => ({ time: b.time, value: e200[i] })));

  const volSma = sma(volumes, 20);
  setSeriesIfData(volumeSmaSeries,
    bars.map((b, i) => volSma[i] != null ? { time: b.time, value: volSma[i] } : null).filter(Boolean));

  // Ichimoku
  const ich = ichimoku(bars);
  setSeriesIfData(tenkanSeries,
    bars.map((b, i) => ich.tenkan[i] != null ? { time: b.time, value: ich.tenkan[i] } : null).filter(Boolean));
  setSeriesIfData(kijunSeries,
    bars.map((b, i) => ich.kijun[i] != null ? { time: b.time, value: ich.kijun[i] } : null).filter(Boolean));
  setSeriesIfData(spanASeries, ich.spanA);
  setSeriesIfData(spanBSeries, ich.spanB);
  setSeriesIfData(chikouSeries,
    bars.map((b, i) => ich.chikou[i] != null ? { time: b.time, value: ich.chikou[i] } : null).filter(Boolean));
  applyIchimokuVisibility();

  const rsiVals = rsi(closes, 14);
  rsiSeries.setData(
    bars
      .map((b, i) => rsiVals[i] != null ? { time: b.time, value: rsiVals[i] } : null)
      .filter(Boolean)
  );

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
      _loadTicker(activeTicker, btn.dataset.tf);
    });
  });
}

function wireWatchlist() {
  document.querySelectorAll(".watch-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".watch-item").forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      _loadTicker(item.dataset.ticker, activeTimeframe);
    });
  });
}

function wireIchimokuToggle() {
  const btn = document.getElementById("toggle-ichimoku");
  if (!btn) return;
  btn.addEventListener("click", () => {
    ichimokuVisible = !ichimokuVisible;
    applyIchimokuVisibility();
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
  wireIchimokuToggle();
  _loadTicker(opts.defaultTicker, "1d");
  refreshWatchlistQuotes(opts.watchlist);
  setInterval(() => refreshWatchlistQuotes(opts.watchlist), 30_000);
};

window.loadTicker = (ticker) => _loadTicker(ticker, activeTimeframe);
window.getActiveTicker = () => activeTicker;
