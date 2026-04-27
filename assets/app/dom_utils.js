// DOM/네트워크 유틸. 외부에서 사용하는 작은 헬퍼들.
import { appState } from './state.js?v=20260427-1';

export function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

export function apiErrorMessage(data) {
  if (!data || data.ok !== false) return '';
  return data.errorInfo?.message || data.errorMessage || data.error || '서버 오류가 발생했습니다.';
}

export function safeStockCode(code) {
  const value = String(code || '').trim();
  return /^\d{6}$/.test(value) ? value : '';
}

export async function fetchJson(url, options) {
  const resp = await fetch(url, options);
  let data;
  try {
    data = await resp.json();
  } catch (e) {
    const message = resp.ok ? '응답을 해석할 수 없습니다.' : `HTTP ${resp.status}`;
    throw new Error(message);
  }
  if (!resp.ok) {
    throw new Error(apiErrorMessage(data) || data?.errorMessage || data?.error || `HTTP ${resp.status}`);
  }
  return data;
}

export function fmt(n) {
  const value = Number(n);
  return Number.isFinite(value) ? value.toLocaleString('ko-KR') : '—';
}

export function stateMessageHtml(message, tone = 'empty', label) {
  const labels = {
    loading: '조회 중',
    empty: '결과 없음',
    error: '오류',
  };
  const safeTone = Object.prototype.hasOwnProperty.call(labels, tone) ? tone : 'empty';
  const role = safeTone === 'error' ? 'alert' : 'status';
  return `
    <div class="state-message state-message-${safeTone}" role="${role}">
      <span class="state-message-label">${escHtml(label || labels[safeTone])}</span>
      <span class="state-message-text">${escHtml(message)}</span>
    </div>`;
}

export function setElementState(el, message, tone = 'empty', label) {
  if (!el) return;
  el.innerHTML = stateMessageHtml(message, tone, label);
}

export function setConditionsTableState(message, tone = 'loading', label) {
  const tbody = document.getElementById('conditionsTbody');
  if (!tbody) return;
  tbody.innerHTML = `<tr class="state-row"><td colspan="8">${stateMessageHtml(message, tone, label)}</td></tr>`;
}

export function setSearchResultsOpen(open) {
  const resultsEl = document.getElementById('searchResults');
  const inputEl = document.getElementById('searchInput');
  if (resultsEl) resultsEl.classList.toggle('show', open);
  if (inputEl) inputEl.setAttribute('aria-expanded', open ? 'true' : 'false');
}

export function setSearchResultsBusy(busy) {
  const resultsEl = document.getElementById('searchResults');
  if (resultsEl) resultsEl.setAttribute('aria-busy', busy ? 'true' : 'false');
}

export function hideSearchResults() {
  setSearchResultsBusy(false);
  setSearchResultsOpen(false);
}

export function showSearchLoading(message) {
  const resultsEl = document.getElementById('searchResults');
  if (!resultsEl) return;
  setElementState(resultsEl, message, 'loading');
  setSearchResultsBusy(true);
  setSearchResultsOpen(true);
}

export function showSearchMessage(message, tone = 'empty') {
  const resultsEl = document.getElementById('searchResults');
  if (!resultsEl) return;
  setElementState(resultsEl, message, tone);
  setSearchResultsBusy(false);
  setSearchResultsOpen(true);
}

export function showSearchError(message) {
  showSearchMessage(message, 'error');
}

export function showRuntimeError(error) {
  console.error('Unexpected app error', error);
  if (appState.ui.activePage === 'warning') {
    showSearchError('예상치 못한 오류가 발생했습니다. 새로고침 후 다시 시도하세요.');
  }
}
