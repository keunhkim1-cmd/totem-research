// 검색 / 가격 조회 / 결과 렌더 오케스트레이션.
import {
  apiErrorMessage,
  escHtml,
  fetchJson,
  hideSearchResults,
  safeStockCode,
  setConditionsTableState,
  setSearchResultsBusy,
  setSearchResultsOpen,
  showSearchError,
  showSearchLoading,
  showSearchMessage,
} from './dom_utils.js?v=20260427-5';
import { appState, isCurrentSearch, isCurrentWarning } from './state.js?v=20260427-5';
import {
  hideCautionCard,
  hideWarningCards,
  renderCaution,
  renderCautionNonPrice,
  renderCautionPartial,
  renderChartLegend,
  renderConditions,
  renderRules,
  renderSymHeader,
  renderTimeline,
  renderVerdict,
  showNotWarning,
} from './warning_render.js?v=20260427-5';
import { renderInlineChart, syncTvChartByName } from './chart.js?v=20260427-5';
import { addTradingDays, countTradingDays } from './calendar.js?v=20260427-5';

// ────────────────────────────────────────────────
// KRX KIND 검색
// ────────────────────────────────────────────────
export async function doSearch() {
  const inputEl = document.getElementById('searchInput');
  const query = inputEl.value.trim();
  if (!query) {
    showSearchMessage('종목명을 입력하세요.');
    inputEl.focus();
    return;
  }

  if (appState.serverBase === null) {
    showSearchMessage('로컬 서버가 필요합니다. 터미널에서 python3 serve.py 를 실행한 뒤 다시 시도하세요.');
    return;
  }

  const searchRequestId = ++appState.search.requestId;
  appState.warning.requestId += 1;

  // TV 차트는 즉시 동기화 (경고/주의 여부와 무관)
  syncTvChartByName(query);

  const btn = document.getElementById('searchBtn');

  btn.disabled = true;
  btn.textContent = '조회 중...';
  showSearchLoading('조회 중...');

  try {
    const url = `/api/warn-search?name=${encodeURIComponent(query)}`;
    const data = await fetchJson(url);
    if (!isCurrentSearch(searchRequestId)) return;

    const apiError = apiErrorMessage(data);
    if (apiError || data.error) {
      showSearchError(apiError || data.error);
      return;
    }

    const results = data.results || [];
    if (results.length === 0) {
      hideWarningCards();
      await checkCautionFallback(query, searchRequestId);
      return;
    }
    hideCautionCard();

    if (results.length === 1) {
      hideSearchResults();
      selectResult(results[0]);
      return;
    }

    renderSearchResults(results);
  } catch (e) {
    if (!isCurrentSearch(searchRequestId)) return;
    showSearchError(`서버 연결 오류: ${e.message}`);
  } finally {
    if (isCurrentSearch(searchRequestId)) {
      btn.disabled = false;
      btn.textContent = 'search';
    }
  }
}

export function renderSearchResults(results) {
  appState.search.results = results;
  const resultsEl = document.getElementById('searchResults');
  const levelClass = { '투자경고': 'level-warning', '투자위험': 'level-risk', '투자주의': 'level-attention' };

  const header = `<div class="search-results-header">${results.length}건의 지정 이력 — 항목을 클릭하면 자동 입력됩니다</div>`;

  const items = results.map((r, idx) => {
    const lc = levelClass[r.level] || 'level-warning';
    const optionLabel = `${r.stockName || '종목명 없음'} ${r.level || '지정 이력'} ${r.designationDate || '날짜 없음'} 선택`;
    return `
      <button type="button" class="result-item" data-idx="${idx}" aria-label="${escHtml(optionLabel)}">
        <div class="result-item-left">
          <span class="result-stock-name">${escHtml(r.stockName || '—')}</span>
          <span class="result-level-badge ${lc}">${escHtml(r.level)}</span>
        </div>
        <div class="result-date">${escHtml(r.designationDate)}</div>
      </button>`;
  }).join('');

  resultsEl.innerHTML = header + items;
  setSearchResultsBusy(false);
  setSearchResultsOpen(true);
}

export function selectResult(r) {
  const warningRequestId = ++appState.warning.requestId;
  hideCautionCard();
  const name = r.stockName || document.getElementById('searchInput').value;
  document.getElementById('stockName').value = name;
  document.getElementById('designationDate').value = r.designationDate;
  document.getElementById('warningType').value = r.level === '투자위험' ? 'risk' : 'warning_normal';
  hideSearchResults();

  // 사용자가 클릭한 종목으로 TV 차트 즉시 동기화
  syncTvChartByName(name);

  // 기준가 조회 → 해제 여부 판별 후 결과 표시
  checkAndDisplay(r, warningRequestId);
}

async function checkCautionFallback(query, searchRequestId) {
  showSearchLoading('조회 중...');
  try {
    const d = await fetchJson(`/api/caution-search?name=${encodeURIComponent(query)}`);
    if (!isCurrentSearch(searchRequestId)) return;
    const cautionError = apiErrorMessage(d);
    if (cautionError) {
      showSearchError(cautionError);
      hideCautionCard();
      return;
    }
    switch (d.status) {
      case 'ok':
        hideSearchResults();
        renderCaution(d);
        return;
      case 'non_price_reason':
        hideSearchResults();
        renderCautionNonPrice(d);
        return;
      case 'code_not_found':
      case 'price_error':
        hideSearchResults();
        renderCautionPartial(d);
        return;
      case 'not_caution':
      default:
        showSearchMessage('현재 투자경고/투자주의가 아님.');
        hideCautionCard();
        return;
    }
  } catch (e) {
    if (!isCurrentSearch(searchRequestId)) return;
    showSearchError(`서버 연결 오류: ${e.message}`);
    hideCautionCard();
  }
}

async function checkAndDisplay(r, warningRequestId) {
  const requestId = warningRequestId || ++appState.warning.requestId;
  await appState.holidaysReady;
  if (!isCurrentWarning(requestId)) return;

  const designationDate = new Date(r.designationDate + 'T00:00:00');
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const elapsed = countTradingDays(designationDate, today) - 1;

  // 10거래일 미경과 → 아직 경고 기간 내, 바로 표시
  if (elapsed < 10) {
    await calculate();
    if (!isCurrentWarning(requestId)) return;
    fetchPriceThresholds(r.stockName, requestId);
    return;
  }

  // 10거래일 경과 → 가격 조건으로 해제 여부 판별
  try {
    const codeData = await fetchJson(`/api/stock-code?name=${encodeURIComponent(r.stockName)}`);
    if (!isCurrentWarning(requestId)) return;
    if (apiErrorMessage(codeData) || codeData.error || !codeData.items || codeData.items.length === 0) {
      await calculate();
      if (!isCurrentWarning(requestId)) return;
      fetchPriceThresholds(r.stockName, requestId);
      return;
    }
    const code = safeStockCode(codeData.items[0].code);
    if (!code) {
      await calculate();
      if (!isCurrentWarning(requestId)) return;
      fetchPriceThresholds(r.stockName, requestId);
      return;
    }

    const priceData = await fetchJson(`/api/stock-price?code=${encodeURIComponent(code)}`);
    if (!isCurrentWarning(requestId)) return;
    if (apiErrorMessage(priceData) || priceData.error || priceData.thresholds?.error) {
      await calculate();
      if (!isCurrentWarning(requestId)) return;
      fetchPriceThresholds(r.stockName, requestId);
      return;
    }

    const t = priceData.thresholds;
    const allMet = t.cond1 && t.cond2 && t.cond3;

    if (!allMet) {
      // 10거래일 경과 + 조건 미충족 → 해제된 상태
      showNotWarning();
      return;
    }

    // 조건 모두 충족 → 아직 경고 유지 중, 전체 표시
    await calculate();
    if (!isCurrentWarning(requestId)) return;
    const item = codeData.items[0];
    renderSymHeader(r.stockName, code, item.market, document.getElementById('designationDate').value, t);
    renderConditions(t);
    const releaseDate = appState.warning.releaseDate || new Date();
    renderVerdict(t, releaseDate);
    renderChartLegend(t, priceData);
    renderInlineChart(priceData, code, r.stockName);

  } catch (e) {
    await calculate();
    if (!isCurrentWarning(requestId)) return;
    fetchPriceThresholds(r.stockName, requestId);
  }
}

// ────────────────────────────────────────────────
// 기준가 조회 → 터미널 섹션 스택에 렌더
// ────────────────────────────────────────────────
async function fetchPriceThresholds(stockName, warningRequestId) {
  const requestId = warningRequestId || ++appState.warning.requestId;
  setConditionsTableState('조회 중...', 'loading');

  try {
    const codeData = await fetchJson(`/api/stock-code?name=${encodeURIComponent(stockName)}`);
    if (!isCurrentWarning(requestId)) return;
    const codeError = apiErrorMessage(codeData);
    if (codeError || codeData.error || !codeData.items || codeData.items.length === 0) {
      setConditionsTableState(`종목코드를 찾을 수 없습니다: ${stockName}`, 'error');
      return;
    }
    const item = codeData.items[0];
    const code = safeStockCode(item.code);
    if (!code) {
      setConditionsTableState(`종목코드를 찾을 수 없습니다: ${stockName}`, 'error');
      return;
    }

    const priceData = await fetchJson(`/api/stock-price?code=${encodeURIComponent(code)}`);
    if (!isCurrentWarning(requestId)) return;
    const priceError = apiErrorMessage(priceData);
    if (priceError || priceData.error) {
      setConditionsTableState(priceError || priceData.error, 'error');
      return;
    }

    const t = priceData.thresholds;
    if (t.error) {
      setConditionsTableState(t.error, 'error');
      return;
    }

    const desigStr = document.getElementById('designationDate').value;
    renderSymHeader(stockName, code, item.market, desigStr, t);
    renderConditions(t);
    const releaseDate = appState.warning.releaseDate || new Date();
    renderVerdict(t, releaseDate);
    renderChartLegend(t, priceData);
    renderInlineChart(priceData, code, stockName);

  } catch (e) {
    if (!isCurrentWarning(requestId)) return;
    setConditionsTableState(`가격 조회 오류: ${e.message}`, 'error');
  }
}

// ────────────────────────────────────────────────
// 계산 → 터미널 섹션 스택 렌더
// ────────────────────────────────────────────────
export async function calculate() {
  await appState.holidaysReady;
  const stockName = document.getElementById('stockName').value.trim();
  const designationDateStr = document.getElementById('designationDate').value;
  const tradingStop = document.getElementById('tradingStop').value;
  const resumeDateStr = document.getElementById('resumeDate').value;

  if (!stockName) { showSearchError('종목명을 입력해주세요.'); return; }
  if (!designationDateStr) { showSearchError('지정일을 입력해주세요.'); return; }

  const designationDate = new Date(designationDateStr + 'T00:00:00');
  const today = new Date(); today.setHours(0, 0, 0, 0);

  let startDate;
  if (tradingStop === 'yes2') {
    if (!resumeDateStr) { showSearchError('매매거래 재개일을 입력해주세요.'); return; }
    startDate = new Date(resumeDateStr + 'T00:00:00');
  } else {
    startDate = new Date(designationDate);
  }

  const releaseDate = addTradingDays(startDate, 10);

  // Sym header (partial — price will fill via fetchPriceThresholds)
  renderSymHeader(stockName, null, null, designationDateStr, null);

  // Timeline
  renderTimeline(startDate, today, releaseDate);

  // Release date chip + cache for verdict
  const rc = document.getElementById('resultCard');
  const y = releaseDate.getFullYear();
  const m = String(releaseDate.getMonth() + 1).padStart(2, '0');
  const d = String(releaseDate.getDate()).padStart(2, '0');
  appState.warning.releaseDate = releaseDate;
  rc.dataset.releaseDate = `${y}-${m}-${d}`;

  // Rules
  renderRules(releaseDate);
  document.getElementById('sec-rules').style.display = '';

  rc.classList.add('show');
  rc.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
