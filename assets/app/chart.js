// 인라인 SVG 가격 차트 렌더와 종목 동기화.
import {
  apiErrorMessage,
  escHtml,
  fetchJson,
  fmt,
  safeStockCode,
} from './dom_utils.js?v=20260426-6';
import { appState, isCurrentChart } from './state.js?v=20260426-6';
import { renderChartLegend } from './warning_render.js?v=20260426-6';

// 경고 탭 인라인 SVG 차트 — NAVER 일별 주가 + 3개 임계선
// TV 무료 embed는 한국 소형주 차트 렌더가 막혀 AAPL로 fallback되므로 사용하지 않음.
export function renderInlineChart(priceData, stockCode, stockName) {
  const container = document.getElementById('tvChartWarning');
  const section = document.getElementById('sec-chart');
  if (!container) return;
  const chartCode = safeStockCode(stockCode);
  if (!chartCode) return;
  if (!priceData || !Array.isArray(priceData.prices) || priceData.prices.length === 0) {
    if (section) section.style.display = 'none';
    return;
  }
  if (section) section.style.display = '';

  const t = priceData.thresholds || {};
  const prices = priceData.prices;
  const W = 1260, H = 320;
  const padL = 72, padR = 16, padT = 16, padB = 32;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  // Y 범위: 가격 + 임계선 모두 포함
  const yValues = prices.map(p => p.close);
  const thresholds = [t.thresh1, t.thresh2, t.max15].filter(v => typeof v === 'number' && isFinite(v));
  const allY = [...yValues, ...thresholds];
  const yMin = Math.min(...allY) * 0.98;
  const yMax = Math.max(...allY) * 1.02;
  const yScale = v => padT + (1 - (v - yMin) / (yMax - yMin)) * innerH;
  const xScale = i => padL + (i / Math.max(prices.length - 1, 1)) * innerW;

  // Y축 눈금 (5단계)
  const yTicks = [];
  for (let i = 0; i <= 4; i++) {
    const v = yMin + (yMax - yMin) * (i / 4);
    yTicks.push({ v, y: yScale(v) });
  }

  // 가격 라인 path
  const linePts = prices.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(1)},${yScale(p.close).toFixed(1)}`).join('');
  // 영역 채우기 (line → 오른쪽 아래 → 왼쪽 아래 → 닫기)
  const areaPts = linePts + ` L${xScale(prices.length - 1).toFixed(1)},${(padT + innerH).toFixed(1)} L${xScale(0).toFixed(1)},${(padT + innerH).toFixed(1)} Z`;

  // 현재가(마지막 포인트)
  const lastIdx = prices.length - 1;
  const lastX = xScale(lastIdx);
  const lastY = yScale(prices[lastIdx].close);
  const delta = prices.length >= 2 ? prices[lastIdx].close - prices[lastIdx - 1].close : 0;
  const lastColor = delta >= 0 ? 'var(--tm-up)' : 'var(--tm-dn)';

  // 15일 최고가 표시
  let max15Marker = '';
  if (typeof t.max15 === 'number' && t.max15Date) {
    const idx = prices.findIndex(p => p.date === t.max15Date);
    if (idx >= 0) {
      const mx = xScale(idx);
      const my = yScale(prices[idx].close);
      max15Marker = `<circle cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="3" fill="var(--tm-ok)" stroke="var(--tm-bg)" stroke-width="1"/>`;
    }
  }

  // X축 라벨 — 시작·중간·끝 3개
  const xLabels = [];
  const pickIdxs = [0, Math.floor(prices.length / 2), prices.length - 1];
  pickIdxs.forEach(i => {
    const d = prices[i]?.date;
    if (d) xLabels.push({ x: xScale(i), label: String(d).slice(5) });
  });

  const fmtNum = n => Number(n).toLocaleString('ko-KR');

  // 임계선 3개
  const lines = [];
  if (typeof t.thresh1 === 'number') {
    const y = yScale(t.thresh1);
    lines.push(`<line x1="${padL}" y1="${y}" x2="${padL + innerW}" y2="${y}" stroke="#FFFFFF" stroke-width="1" stroke-dasharray="4 3" opacity="0.65"/>`);
    lines.push(`<text x="${padL + innerW - 4}" y="${y - 4}" fill="#FFFFFF" font-size="9" font-family="var(--mono)" text-anchor="end" opacity="0.85">① ${fmtNum(t.thresh1)}</text>`);
  }
  if (typeof t.thresh2 === 'number') {
    const y = yScale(t.thresh2);
    lines.push(`<line x1="${padL}" y1="${y}" x2="${padL + innerW}" y2="${y}" stroke="#F04452" stroke-width="1" stroke-dasharray="4 3" opacity="0.7"/>`);
    lines.push(`<text x="${padL + innerW - 4}" y="${y - 4}" fill="#F04452" font-size="9" font-family="var(--mono)" text-anchor="end" opacity="0.9">② ${fmtNum(t.thresh2)}</text>`);
  }
  if (typeof t.max15 === 'number') {
    const y = yScale(t.max15);
    lines.push(`<line x1="${padL}" y1="${y}" x2="${padL + innerW}" y2="${y}" stroke="#4ADE80" stroke-width="1" stroke-dasharray="4 3" opacity="0.7"/>`);
    lines.push(`<text x="${padL + innerW - 4}" y="${y - 4}" fill="#4ADE80" font-size="9" font-family="var(--mono)" text-anchor="end" opacity="0.9">③ ${fmtNum(t.max15)}</text>`);
  }

  // Y축 눈금 라벨
  const yAxisLabels = yTicks.map(tk => `
    <line x1="${padL}" y1="${tk.y}" x2="${padL + innerW}" y2="${tk.y}" stroke="var(--tm-hairline)" stroke-width="0.5" opacity="0.6"/>
    <text x="${padL - 8}" y="${tk.y + 3}" fill="var(--tm-text-mute)" font-size="9" font-family="var(--mono)" text-anchor="end">${fmtNum(Math.round(tk.v))}</text>`).join('');

  // X축 라벨
  const xAxisLabels = xLabels.map(l => `
    <text x="${l.x}" y="${H - 10}" fill="var(--tm-text-mute)" font-size="9" font-family="var(--mono)" text-anchor="middle">${escHtml(l.label)}</text>`).join('');

  container.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="chart-fill-${chartCode}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.12"/>
          <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>
        </linearGradient>
      </defs>
      ${yAxisLabels}
      ${lines.join('')}
      <path d="${areaPts}" fill="url(#chart-fill-${chartCode})"/>
      <path d="${linePts}" fill="none" stroke="#FFFFFF" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
      ${max15Marker}
      <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="3.5" fill="${lastColor}" stroke="var(--tm-bg)" stroke-width="1.5"/>
      ${xAxisLabels}
    </svg>
  `;
  appState.chart.code = chartCode;
  container.dataset.chartCode = chartCode;
  container.setAttribute('aria-label', `${stockName || chartCode} 시세와 임계가 차트`);
}

// 종목명으로 차트 동기화 — stock-code 조회 후 stock-price 받아 SVG 렌더
export async function syncTvChartByName(stockName) {
  if (!stockName) return;
  const chartRequestId = ++appState.chart.requestId;
  try {
    const codeData = await fetchJson(`/api/stock-code?name=${encodeURIComponent(stockName)}`);
    if (!isCurrentChart(chartRequestId)) return;
    if (apiErrorMessage(codeData) || !codeData.items || codeData.items.length === 0) return;
    const code = safeStockCode(codeData.items[0].code);
    if (!code) return;
    if (appState.chart.code === code) return;
    const priceData = await fetchJson(`/api/stock-price?code=${encodeURIComponent(code)}`);
    if (!isCurrentChart(chartRequestId)) return;
    if (apiErrorMessage(priceData) || priceData.error) return;
    renderInlineChart(priceData, code, stockName);
    if (priceData.thresholds) renderChartLegend(priceData.thresholds, priceData);
  } catch (e) { /* 네트워크/서버 오류는 조용히 무시 */ }
}
