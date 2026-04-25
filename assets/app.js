// ────────────────────────────────────────────────
// XSS 방어 유틸
// ────────────────────────────────────────────────
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

function apiErrorMessage(data) {
  if (!data || data.ok !== false) return '';
  return data.errorInfo?.message || data.errorMessage || data.error || '서버 오류가 발생했습니다.';
}

function safeStockCode(code) {
  const value = String(code || '').trim();
  return /^\d{6}$/.test(value) ? value : '';
}

async function fetchJson(url, options) {
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

const appState = {
  ui: {
    activePage: 'warning',
  },
  search: {
    requestId: 0,
    results: [],
  },
  warning: {
    requestId: 0,
    releaseDate: null,
  },
  chart: {
    requestId: 0,
    code: '',
  },
  patchNotes: {
    loaded: false,
  },
  fortune: {
    dateKey: '',
  },
  holidays: new Set(),
  serverBase: window.location.protocol === 'file:' ? null : '',
};

window.addEventListener('error', event => {
  showRuntimeError(event.error || event.message);
});

window.addEventListener('unhandledrejection', event => {
  showRuntimeError(event.reason || 'Unhandled promise rejection');
});

function isCurrentSearch(requestId) {
  return requestId === appState.search.requestId;
}

function isCurrentWarning(requestId) {
  return requestId === appState.warning.requestId;
}

function isCurrentChart(requestId) {
  return requestId === appState.chart.requestId;
}

function stateMessageHtml(message, tone = 'empty', label) {
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

function setElementState(el, message, tone = 'empty', label) {
  if (!el) return;
  el.innerHTML = stateMessageHtml(message, tone, label);
}

function setConditionsTableState(message, tone = 'loading', label) {
  const tbody = document.getElementById('conditionsTbody');
  if (!tbody) return;
  tbody.innerHTML = `<tr class="state-row"><td colspan="8">${stateMessageHtml(message, tone, label)}</td></tr>`;
}

function showRuntimeError(error) {
  console.error('Unexpected app error', error);
  if (appState.ui.activePage === 'warning') {
    showSearchError('예상치 못한 오류가 발생했습니다. 새로고침 후 다시 시도하세요.');
  }
}

function setSearchResultsOpen(open) {
  const resultsEl = document.getElementById('searchResults');
  const inputEl = document.getElementById('searchInput');
  if (resultsEl) resultsEl.classList.toggle('show', open);
  if (inputEl) inputEl.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function setSearchResultsBusy(busy) {
  const resultsEl = document.getElementById('searchResults');
  if (resultsEl) resultsEl.setAttribute('aria-busy', busy ? 'true' : 'false');
}

function hideSearchResults() {
  setSearchResultsBusy(false);
  setSearchResultsOpen(false);
}

function showSearchLoading(message) {
  const resultsEl = document.getElementById('searchResults');
  if (!resultsEl) return;
  setElementState(resultsEl, message, 'loading');
  setSearchResultsBusy(true);
  setSearchResultsOpen(true);
}

function showSearchMessage(message, tone = 'empty') {
  const resultsEl = document.getElementById('searchResults');
  if (!resultsEl) return;
  setElementState(resultsEl, message, tone);
  setSearchResultsBusy(false);
  setSearchResultsOpen(true);
}

function showSearchError(message) {
  showSearchMessage(message, 'error');
}

// ────────────────────────────────────────────────
// 페이지 전환
// ────────────────────────────────────────────────
function switchPage(page, el) {
  const targetPage = document.getElementById('page-' + page);
  if (!targetPage) return;
  const activeNav = el || document.querySelector(`[data-page="${page}"]`);
  appState.ui.activePage = page;

  document.querySelectorAll('.page-section').forEach(panel => {
    const active = panel === targetPage;
    panel.classList.toggle('active', active);
    panel.hidden = !active;
    panel.setAttribute('aria-hidden', active ? 'false' : 'true');
  });

  document.querySelectorAll('.nav-title, .nav-item').forEach(btn => {
    const active = btn === activeNav;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
    btn.tabIndex = active ? 0 : -1;
    if (active) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
  });

  document.body.classList.toggle('is-warning-active', page === 'warning');
  document.body.classList.toggle('is-terminal-active', page === 'warning' || page === 'about' || page === 'fortune' || page === 'patchnotes');
  if (page !== 'warning') hideSearchResults();
  if (page === 'fortune') renderFortune();
  if (page === 'patchnotes') renderPatchNotes();
}

// 초기 로드 시 경고 탭이 default active 이므로 body 클래스 반영
document.body.classList.add('is-warning-active', 'is-terminal-active');

const fortuneDeck = [
  {
    market: '소음이 조금 크게 들리는 날입니다. 첫 반응을 늦추고 숫자와 기분을 분리해 보세요.',
    risk: '피로도가 높으면 작은 변화도 크게 보일 수 있습니다. 화면을 오래 붙잡고 있는지 먼저 확인하세요.',
    memo: '관찰한 사실과 느낀 감정을 한 줄씩 나눠 적으면 생각의 온도가 내려갑니다.',
    avoid: '확인하지 않은 이야기를 기준으로 오늘의 리듬을 바꾸기.',
  },
  {
    market: '흐름보다 맥락이 잘 보이는 날입니다. 빠른 결론보다 차분한 비교가 어울립니다.',
    risk: '일정이 촘촘할수록 실수 확률이 올라갑니다. 중요한 확인은 한 번 쉬고 다시 보세요.',
    memo: '오늘의 좋은 기록은 짧고 건조한 문장입니다. 느낌표보다 근거를 남기는 쪽이 편합니다.',
    avoid: '졸리거나 급한 상태에서 여러 화면을 동시에 열어두기.',
  },
  {
    market: '분위기에 휩쓸리기 쉬운 날입니다. 크게 보이는 말일수록 출처와 시간을 따로 확인하세요.',
    risk: '새로운 정보보다 오래된 가정이 더 위험할 수 있습니다. 이미 알고 있다고 여긴 부분을 점검하세요.',
    memo: '메모의 첫 줄은 결론이 아니라 질문으로 시작해도 좋습니다. 오늘은 질문이 방향을 잡아줍니다.',
    avoid: '짧은 문구 하나로 하루 전체의 판단을 단정하기.',
  },
  {
    market: '숫자보다 사람들의 반응이 먼저 눈에 들어오는 날입니다. 반응과 사실을 같은 칸에 두지 마세요.',
    risk: '집중력이 끊기면 같은 내용을 반복해서 확인하게 됩니다. 확인 횟수보다 확인 품질을 보세요.',
    memo: '오늘의 메모는 세 줄이면 충분합니다. 본 것, 모르는 것, 내일 다시 볼 것을 나눠 적어보세요.',
    avoid: '불안해서 새로고침을 반복하거나, 확인 전 알림에 바로 반응하기.',
  },
  {
    market: '차분한 관찰이 잘 맞는 날입니다. 눈에 띄는 변화보다 반복되는 패턴을 천천히 보세요.',
    risk: '확신이 강해질수록 놓치는 항목이 생깁니다. 반대 근거를 하나만 찾아보는 습관이 도움이 됩니다.',
    memo: '운용역 메모: 오늘은 빠른 판단보다 깔끔한 정리가 더 남는 날. 기록의 형식을 먼저 맞춥니다.',
    avoid: '기분이 좋다는 이유로 확인 절차를 줄이기.',
  },
  {
    market: '정보의 양이 많아 보일 수 있습니다. 전부 해석하려 하기보다 오늘 볼 범위를 먼저 정하세요.',
    risk: '컨디션이 흔들리면 문장이 공격적으로 읽힐 수 있습니다. 강한 표현은 한 번 더 부드럽게 번역하세요.',
    memo: '운용역 메모: 새로움보다 일관성을 점검합니다. 같은 기준으로 다시 본 내용이 더 믿을 만합니다.',
    avoid: '정리되지 않은 링크를 계속 열어두고 집중력을 쪼개기.',
  },
];

function getKstDateInfo(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now).reduce((acc, part) => {
    if (part.type !== 'literal') acc[part.type] = part.value;
    return acc;
  }, {});
  const key = `${parts.year}-${parts.month}-${parts.day}`;
  return { key, label: `${parts.year}.${parts.month}.${parts.day}` };
}

function fortuneIndex(dateKey, size) {
  const [year, month, day] = dateKey.split('-').map(Number);
  const utcDays = Math.floor(Date.UTC(year, month - 1, day) / 86400000);
  return ((utcDays % size) + size) % size;
}

function renderFortune() {
  const container = document.getElementById('fortuneContent');
  const titleEl = document.getElementById('fortunePanelTitle');
  if (!container) return;
  const dateInfo = getKstDateInfo();
  if (appState.fortune.dateKey === dateInfo.key && container.innerHTML) return;
  const item = fortuneDeck[fortuneIndex(dateInfo.key, fortuneDeck.length)];
  const rows = [
    ['오늘의 시장 감각', item.market],
    ['리스크 체크', item.risk],
    ['운용역 메모', item.memo],
    ['피해야 할 행동', item.avoid],
  ];
  const [, month, day] = dateInfo.key.split('-');
  if (titleEl) titleEl.textContent = `${month}월 ${day}일 운세`;
  container.innerHTML = `
    <div class="fortune-list" role="list">
      ${rows.map(([label, text]) => `
        <article class="fortune-row" role="listitem">
          <div class="fortune-label">${escHtml(label)}</div>
          <p>${escHtml(text)}</p>
        </article>`).join('')}
    </div>
    <p class="fortune-note">재미용 컨디션 점검 문구입니다. 특정 자산이나 행동을 권하지 않습니다.</p>`;
  appState.fortune.dateKey = dateInfo.key;
}

// 패치 노트 — data/patchnotes.json 렌더
async function renderPatchNotes() {
  const container = document.getElementById('patchnotesContent');
  if (!container || appState.patchNotes.loaded) return;
  try {
    const entries = await fetchJson('/data/patchnotes.json', { cache: 'no-cache' });
    const tagLabel = { feat: 'NEW', fix: 'FIX', improve: 'IMPROVE', chore: 'CHORE' };
    if (!Array.isArray(entries) || entries.length === 0) {
      setElementState(container, '기록된 패치 노트가 없습니다.', 'empty');
      return;
    }
    container.innerHTML = entries.map(e => {
      const rawTag = String(e.tag || 'feat').toLowerCase();
      const tag = Object.prototype.hasOwnProperty.call(tagLabel, rawTag) ? rawTag : 'chore';
      const label = tagLabel[tag] || 'UPDATE';
      const items = Array.isArray(e.items) ? e.items : [];
      return `
        <article class="patch-entry">
          <div class="patch-entry-head">
            <span class="patch-entry-tag ${escHtml(tag)}">${escHtml(label)}</span>
            <span class="patch-entry-title">${escHtml(e.title || '')}</span>
            <span class="patch-entry-date num">${escHtml(e.date || '')}</span>
          </div>
          <ul class="patch-entry-items">
            ${items.map((it, idx) => `<li><span class="k">${String(idx + 1).padStart(2, '0')}</span><span class="v">${escHtml(it)}</span></li>`).join('')}
          </ul>
        </article>`;
    }).join('');
    appState.patchNotes.loaded = true;
  } catch (e) {
    setElementState(container, `패치 노트를 불러올 수 없습니다: ${e.message}`, 'error');
  }
}

// ────────────────────────────────────────────────
// 서버 상태 확인
// ────────────────────────────────────────────────
async function checkServer() {
  if (appState.serverBase === null) {
    document.getElementById('serverNotice').classList.add('show');
    document.getElementById('searchBtn').disabled = true;
    document.getElementById('searchBtn').title = '로컬 서버를 먼저 실행하세요';
    return false;
  }
  return true;
}

checkServer();

const pageNavButtons = Array.from(document.querySelectorAll('.nav-title, .nav-item'));
pageNavButtons.forEach((btn, idx) => {
  btn.addEventListener('click', () => switchPage(btn.dataset.page, btn));
  btn.addEventListener('keydown', event => {
    let nextIdx = null;
    if (event.key === 'ArrowRight') nextIdx = (idx + 1) % pageNavButtons.length;
    else if (event.key === 'ArrowLeft') nextIdx = (idx - 1 + pageNavButtons.length) % pageNavButtons.length;
    else if (event.key === 'Home') nextIdx = 0;
    else if (event.key === 'End') nextIdx = pageNavButtons.length - 1;
    if (nextIdx == null) return;
    event.preventDefault();
    const next = pageNavButtons[nextIdx];
    next.focus();
    switchPage(next.dataset.page, next);
  });
});

document.getElementById('searchBtn').addEventListener('click', doSearch);
document.getElementById('searchInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') doSearch();
  if (event.key === 'Escape') hideSearchResults();
});

// ────────────────────────────────────────────────
// KRX KIND 검색
// ────────────────────────────────────────────────
async function doSearch() {
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

  const resultsEl = document.getElementById('searchResults');
  const btn = document.getElementById('searchBtn');

  btn.disabled = true;
  btn.textContent = '조회 중...';
  showSearchLoading('KRX KIND에서 데이터를 가져오는 중...');

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

function renderSearchResults(results) {
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

document.getElementById('searchResults').addEventListener('click', (e) => {
  const item = e.target.closest('.result-item');
  if (item && item.dataset.idx != null) {
    selectResult(appState.search.results[item.dataset.idx]);
  }
});

function hideWarningCards() {
  const rc = document.getElementById('resultCard');
  if (rc) {
    rc.classList.remove('show');
    // 경고 관련 하위 섹션 숨김
    ['sec-chart','sec-rules'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const v = document.getElementById('sec-verdict');
    if (v) v.style.display = 'none';
  }
}

function hideCautionCard() {
  document.getElementById('cautionCard').style.display = 'none';
}

function showNotWarning() {
  showSearchMessage('현재 투자경고가 아님.');
  hideWarningCards();
  hideCautionCard();
}

function selectResult(r) {
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
  showSearchLoading('투자주의 여부 확인 중...');
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

function _cautionMetaHtml(d, showIndex) {
  const codeLabel = d.code ? ` (${escHtml(d.code)}${d.market ? '·' + escHtml(d.market) : ''})` : '';
  let html = `종목: <strong>${escHtml(d.stockName)}</strong>${codeLabel}`;

  const an = d.activeNotice;
  if (an) {
    html += ` &nbsp;|&nbsp; 지정예고일: <strong>${escHtml(an.noticeDate)}</strong>` +
            ` &nbsp;|&nbsp; 판단 기간: <strong>${escHtml(an.firstJudgmentDate)} ~ ${escHtml(an.lastJudgmentDate)}</strong>` +
            ` (판단일 ${escHtml(an.judgmentDayIndex)}/${escHtml(an.judgmentWindowTotal)})`;
  } else if (d.latestDesignationDate) {
    html += ` &nbsp;|&nbsp; 지정일: <strong>${escHtml(d.latestDesignationDate)}</strong>`;
    if (d.designationReason) html += ` &nbsp;|&nbsp; 사유: <strong>${escHtml(d.designationReason)}</strong>`;
  }

  if (showIndex && d.escalation) {
    const e = d.escalation;
    const idxTxt = typeof e.indexClose === 'number' ? e.indexClose.toLocaleString('ko-KR', {maximumFractionDigits: 2}) : '';
    html += `<br/>현재가 <strong>${fmt(e.tClose)}원</strong> (${escHtml(e.tDate)})`;
    if (idxTxt) html += ` &nbsp;|&nbsp; ${escHtml(d.indexSymbol || '지수')} <strong>${idxTxt}</strong>`;
  }
  return html;
}

function renderCaution(d) {
  const card = document.getElementById('cautionCard');
  const meta = document.getElementById('cautionMeta');
  const content = document.getElementById('cautionContent');
  const verdict = document.getElementById('cautionVerdict');

  meta.innerHTML = _cautionMetaHtml(d, true);

  const e = d.escalation;
  const setHtml = (s) => {
    const statusCls = s.allMet ? 'met' : 'unmet';
    const statusTxt = s.allMet ? '모두 충족' : '해당 없음';
    const conds = s.conditions.map(c => `
      <div class="caution-cond">
        <div class="caution-cond-mark ${c.met ? 'met' : 'unmet'}">${c.met ? '충족' : '미충족'}</div>
        <div>
          <div class="caution-cond-label">${escHtml(c.label)}</div>
          <div class="caution-cond-detail">${escHtml(c.detail)}</div>
        </div>
      </div>`).join('');
    return `
      <div class="caution-set">
        <div class="caution-set-head">
          <span class="caution-set-title">${escHtml(s.label)}</span>
          <span class="caution-set-status ${statusCls}">${statusTxt}</span>
        </div>
        ${conds}
      </div>`;
  };
  content.innerHTML = e.sets.map(setHtml).join('');

  verdict.classList.remove('keep', 'release', 'soft');
  verdict.style.display = '';
  const h = e.headline || { verdict: 'none' };
  if (h.verdict === 'strong') {
    const matched = e.sets[h.matchedSet];
    verdict.classList.add('keep');
    verdict.textContent = `→ 투자경고 지정 예상 · ${matched.label} 충족`;
  } else {
    verdict.classList.add('release');
    verdict.textContent = '→ 투자경고 지정 미해당';
  }

  card.style.display = 'block';
}

function renderCautionNonPrice(d) {
  const card = document.getElementById('cautionCard');
  const meta = document.getElementById('cautionMeta');
  const content = document.getElementById('cautionContent');
  const verdict = document.getElementById('cautionVerdict');

  meta.innerHTML = _cautionMetaHtml(d, false);
  content.innerHTML = `
    <div class="caution-nonprice">
      이 종목은 <strong>${escHtml(d.designationReason || '')}</strong> 사유로 투자주의 지정되었습니다.<br/>
      가격 기반 투자경고 격상 조건(단기급등/중장기급등)은 적용되지 않습니다.
    </div>`;
  verdict.classList.remove('keep', 'release', 'soft');
  verdict.style.display = 'none';
  verdict.textContent = '';
  card.style.display = 'block';
}

function renderCautionPartial(d) {
  const card = document.getElementById('cautionCard');
  const meta = document.getElementById('cautionMeta');
  const content = document.getElementById('cautionContent');
  const verdict = document.getElementById('cautionVerdict');
  verdict.classList.remove('keep', 'release', 'soft');
  verdict.style.display = 'none';
  verdict.textContent = '';

  meta.innerHTML = _cautionMetaHtml(d, false);
  const msg = d.status === 'code_not_found'
    ? '종목코드를 찾을 수 없어 격상 요건을 계산할 수 없습니다.'
    : `주가/지수 조회 불가: ${d.errorMessage || '알 수 없는 오류'}`;
  content.innerHTML = stateMessageHtml(msg, 'error');
  card.style.display = 'block';
}

async function checkAndDisplay(r, warningRequestId) {
  const requestId = warningRequestId || ++appState.warning.requestId;
  await holidaysReady;
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
      // 종목코드 조회 실패 시 기존대로 표시
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
    // 이미 가격 데이터를 가져왔으므로 직접 렌더링
    const item = codeData.items[0];
    renderSymHeader(r.stockName, code, item.market, document.getElementById('designationDate').value, t);
    renderConditions(t);
    const releaseDate = appState.warning.releaseDate || new Date();
    renderVerdict(t, releaseDate);
    renderChartLegend(t, priceData);
    renderInlineChart(priceData, code, r.stockName);

  } catch (e) {
    // 오류 시 기존대로 표시
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
  setConditionsTableState('네이버 금융에서 주가 데이터를 조회 중입니다.', 'loading');

  try {
    // 1. 종목코드 검색
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

    // 2. 일별 주가 + 기준가 계산
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

    // Update symbol header with price
    const desigStr = document.getElementById('designationDate').value;
    renderSymHeader(stockName, code, item.market, desigStr, t);

    // Render conditions table + verdict
    renderConditions(t);

    // Verdict uses release date computed in calculate() — stored on resultCard dataset
    const releaseDate = appState.warning.releaseDate || new Date();
    renderVerdict(t, releaseDate);

    // Chart legend + 인라인 SVG 차트 (중복 fetch 없이 priceData 재사용)
    renderChartLegend(t, priceData);
    renderInlineChart(priceData, code, stockName);

  } catch (e) {
    if (!isCurrentWarning(requestId)) return;
    setConditionsTableState(`가격 조회 오류: ${e.message}`, 'error');
  }
}

function fmt(n) {
  const value = Number(n);
  return Number.isFinite(value) ? value.toLocaleString('ko-KR') : '—';
}

// ────────────────────────────────────────────────
// Terminal-tone renderers (Step 4)
// ────────────────────────────────────────────────

// §2 Symbol header — partial (no price yet) or full (with price)
function renderSymHeader(stockName, code, market, designationDate, priceData) {
  const h = document.getElementById('sym-header');
  if (!h) return;

  const tickerEl = h.querySelector('.ticker');
  const nameEl   = h.querySelector('.name');
  const metaEl   = h.querySelector('.meta');
  const chipsEl  = h.querySelector('.chips');
  const valEl    = h.querySelector('.px .val');
  const chgEl    = h.querySelector('.px .chg');

  tickerEl.textContent = code || '------';
  nameEl.textContent   = stockName || '—';

  const metaParts = [];
  if (market) metaParts.push(market);
  if (designationDate) metaParts.push('지정 ' + designationDate);
  metaEl.textContent = metaParts.join(' · ');

  chipsEl.innerHTML = '<span class="chip warn">투자경고 지정중</span>';

  if (priceData) {
    const close = priceData.tClose;
    const prev  = priceData.prevClose || close;
    const delta = close - prev;
    const pct   = prev ? (delta / prev * 100) : 0;
    const upDn  = delta > 0 ? 'up' : delta < 0 ? 'dn' : '';
    const arrow = delta > 0 ? '▲' : delta < 0 ? '▼' : '·';
    valEl.textContent = fmt(close);
    valEl.classList.remove('up','dn');
    if (upDn) valEl.classList.add(upDn);
    chgEl.textContent = `${arrow} ${fmt(Math.abs(delta))} · ${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
    chgEl.classList.remove('up','dn');
    if (upDn) chgEl.classList.add(upDn);
  } else {
    valEl.textContent = '--';
    valEl.classList.remove('up','dn');
    chgEl.textContent = '';
    chgEl.classList.remove('up','dn');
  }
}

// §3 Timeline — 11 cells (D0 → T+1..T+9 → 해제)
function renderTimeline(designationDate, today, releaseDate) {
  const track = document.querySelector('#sec-timeline .tm-tl-track');
  const foot  = document.querySelector('#sec-timeline .tm-tl-foot');
  if (!track || !foot) return;

  // Count trading days elapsed from designation to today
  let daysPassed;
  if (today < designationDate) {
    daysPassed = 0;
  } else {
    const count = countTradingDays(designationDate, today);
    daysPassed = Math.max(0, Math.min(10, count - 1));
  }

  const labels = ['D0','T+1','T+2','T+3','T+4','T+5','T+6','T+7','T+8','T+9','해제'];
  track.innerHTML = labels.map((lbl, i) => {
    let cls = 'future';
    if (i === 10) cls = 'release';
    else if (i < daysPassed) cls = 'past';
    else if (i === daysPassed) cls = 'today';
    else cls = '';
    return `<div class="tm-tl-cell ${cls}">${lbl}</div>`;
  }).join('');

  const fmtDate = d => {
    const y = d.getFullYear(), m = String(d.getMonth()+1).padStart(2,'0'), dd = String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${dd}`;
  };
  foot.querySelector('.d1').textContent = fmtDate(designationDate);
  foot.querySelector('.d2').textContent = fmtDate(today) + ` · ${Math.min(daysPassed,10)}거래일 경과`;
  foot.querySelector('.d3').textContent = fmtDate(releaseDate);

  // Section head source info
  const src = document.querySelector('#sec-timeline .tm-sec-head .src');
  if (src) {
    const dDay = Math.max(0, 10 - daysPassed);
    src.textContent = daysPassed >= 10 ? '해제 심사 가능' : `T · ${daysPassed}거래일 경과 · D-${dDay}`;
  }
}

// §4 Conditions table — 3 rows (T-5 × 1.45, T-15 × 1.75, 15일 최고가)
function renderConditions(t) {
  const tbody = document.getElementById('conditionsTbody');
  if (!tbody) return;

  function row(num, formula, desc, baseDate, baseClose, ratio, thresh, tClose, met) {
    const statusCls = met ? 'hold' : 'clear';
    const flag = met ? '유지' : '이탈';
    const delta = tClose - thresh;
    const pct = thresh ? (delta / thresh * 100) : 0;
    const deltaCls = delta >= 0 ? 'up' : 'dn';
    const sign = pct >= 0 ? '+' : '';
    return `
      <tr class="${statusCls}">
        <td>
          <div class="lbl-col">
            <div class="badge">${num}</div>
            <div class="txt">
              <div class="n">${formula}</div>
              <div class="d">${desc}</div>
            </div>
          </div>
        </td>
        <td class="num">${escHtml(baseDate)}</td>
        <td class="num">${fmt(baseClose)}</td>
        <td>${ratio}</td>
        <td class="num accent">${fmt(thresh)}</td>
        <td class="num ${deltaCls}">${fmt(tClose)}</td>
        <td class="num ${deltaCls}">${sign}${pct.toFixed(2)}%</td>
        <td><span class="flag ${statusCls}">${flag}</span></td>
      </tr>`;
  }

  function row3(t) {
    const met = t.cond3;
    const statusCls = met ? 'hold' : 'clear';
    const flag = met ? '유지' : '이탈';
    const delta = t.tClose - t.max15;
    const pct = t.max15 ? (delta / t.max15 * 100) : 0;
    const deltaCls = delta >= 0 ? 'up' : 'dn';
    const sign = pct >= 0 ? '+' : '';
    return `
      <tr class="${statusCls}">
        <td>
          <div class="lbl-col">
            <div class="badge">3</div>
            <div class="txt">
              <div class="n">= 15일 최고가</div>
              <div class="d">15일 최고가 테스트</div>
            </div>
          </div>
        </td>
        <td class="num">${escHtml(t.max15Date)}</td>
        <td class="num">${fmt(t.max15)}</td>
        <td>—</td>
        <td class="num accent">${fmt(t.max15)}</td>
        <td class="num ${deltaCls}">${fmt(t.tClose)}</td>
        <td class="num ${deltaCls}">${sign}${pct.toFixed(2)}%</td>
        <td><span class="flag ${statusCls}">${flag}</span></td>
      </tr>`;
  }

  tbody.innerHTML =
    row(1, 'T-5 종가 × 1.45', '5일 45% 급등 테스트', t.t5Date,  t.t5Close,  '1.45×', t.thresh1, t.tClose, t.cond1) +
    row(2, 'T-15 종가 × 1.75', '15일 75% 급등 테스트', t.t15Date, t.t15Close, '1.75×', t.thresh2, t.tClose, t.cond2) +
    row3(t);
}

// §5 Verdict — release / hold / risk variants
function renderVerdict(t, releaseDate) {
  const v = document.getElementById('sec-verdict');
  if (!v) return;

  const anyClear = !t.cond1 || !t.cond2 || !t.cond3;
  const missing = [];
  if (!t.cond1) missing.push('①');
  if (!t.cond2) missing.push('②');
  if (!t.cond3) missing.push('③');

  v.classList.remove('hold','risk');
  v.style.display = 'flex';

  const fmtDate = d => {
    const y = d.getFullYear(), m = String(d.getMonth()+1).padStart(2,'0'), dd = String(d.getDate()).padStart(2,'0');
    return `${m}-${dd}`;
  };

  const tagEl = v.querySelector('.tag');
  const hEl   = v.querySelector('.h');
  const bEl   = v.querySelector('.b');
  const dEl   = v.querySelector('.side .d');

  if (anyClear) {
    tagEl.textContent = '해제 예정';
    hEl.textContent = `${fmtDate(releaseDate)} 투자경고 해제 예정`;
    bEl.textContent = `조건 ${missing.join('·')} 미충족 — KRX §4-2 기준상 해제 판단일에 세 조건 중 하나라도 미충족이면 해제 대상으로 판정됩니다.`;
    dEl.textContent = fmtDate(releaseDate);
  } else {
    v.classList.add('hold');
    tagEl.textContent = '경고 유지';
    hEl.textContent = '3가지 조건 모두 충족 · 경고 유지';
    bEl.textContent = '① T-5 × 1.45, ② T-15 × 1.75, ③ 15일 최고가 — 세 조건이 동시에 충족되어 투자경고가 유지됩니다.';
    dEl.textContent = '—';
  }
}

// §7 KRX Rules — static 4 items
function renderRules(releaseDate) {
  const box = document.getElementById('rulesContent');
  if (!box) return;

  const fmtDate = d => {
    if (!d) return '—';
    const y = d.getFullYear(), m = String(d.getMonth()+1).padStart(2,'0'), dd = String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${dd}`;
  };

  box.innerHTML = `
    <div class="r"><span class="k">1</span><span class="v">지정일로부터 10 매매거래일 경과 후 해제 심사 시작</span><span class="m num">${fmtDate(releaseDate)}</span></div>
    <div class="r"><span class="k">2</span><span class="v">해제 판단일에 ① ② ③ 세 조건 모두 충족 시 경고 유지. 하나라도 미충족이면 해제 대상.</span><span class="m">3 중 3</span></div>
    <div class="r"><span class="k">3</span><span class="v">지정 기간 중 신용융자 금지, 위탁증거금 100% 현금</span><span class="m">—</span></div>
    <div class="r"><span class="k">4</span><span class="v">지정 기간 내 요건 재충족 시 투자위험종목으로 상향 지정</span><span class="m">—</span></div>`;
}

// Chart legend (§6) — T 종가 + 3 thresholds as swatches
function renderChartLegend(t, priceData) {
  const legend = document.getElementById('chartLegend');
  if (!legend) return;
  let tEntry = '';
  if (typeof t.tClose === 'number') {
    let lastColor = 'var(--tm-text)';
    const prices = priceData && Array.isArray(priceData.prices) ? priceData.prices : null;
    if (prices && prices.length >= 2) {
      const delta = prices[prices.length - 1].close - prices[prices.length - 2].close;
      lastColor = delta >= 0 ? 'var(--tm-up)' : 'var(--tm-dn)';
    }
    tEntry = `<span class="t-mark">T ${escHtml(t.tDate || '')} · 종가 <b style="color:${lastColor}">${fmt(t.tClose)}</b></span>`;
  }
  legend.innerHTML = `
    ${tEntry}
    <span><span class="sw" style="background:#FFFFFF"></span>① ${fmt(t.thresh1)}</span>
    <span><span class="sw" style="background:#F04452"></span>② ${fmt(t.thresh2)}</span>
    <span><span class="sw" style="background:#4ADE80"></span>③ ${fmt(t.max15)}</span>`;
}

// ────────────────────────────────────────────────
// 공휴일 (data/holidays.json 단일 소스)
// ────────────────────────────────────────────────
const MAX_HOLIDAY_YEAR = 2029;

const holidaysReady = fetchJson('/data/holidays.json')
  .then(arr => { appState.holidays = new Set(arr); })
  .catch(e => console.warn('공휴일 데이터 로드 실패, 주말만 판정합니다:', e));

function toDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function isHoliday(d) { return appState.holidays.has(toDateStr(d)); }
function isWeekend(d) { const day = d.getDay(); return day === 0 || day === 6; }
function isTradingDay(d) { return !isWeekend(d) && !isHoliday(d); }

function addDays(d, n) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function addTradingDays(start, n) {
  let count = 0, cur = new Date(start);
  while (count < n) { cur = addDays(cur, 1); if (isTradingDay(cur)) count++; }
  return cur;
}

function countTradingDays(start, end) {
  let count = 0, cur = new Date(start);
  while (cur <= end) { if (isTradingDay(cur)) count++; cur = addDays(cur, 1); }
  return count;
}

// ────────────────────────────────────────────────
// 이벤트
// ────────────────────────────────────────────────
document.getElementById('designationDate').value = toDateStr(new Date());

// 외부 클릭 시 검색 결과 닫기
document.addEventListener('click', (e) => {
  if (!e.target.closest('.form-group')) {
    hideSearchResults();
  }
});

// ────────────────────────────────────────────────
// 계산 → 터미널 섹션 스택 렌더
// ────────────────────────────────────────────────
async function calculate() {
  await holidaysReady;
  const stockName        = document.getElementById('stockName').value.trim();
  const designationDateStr = document.getElementById('designationDate').value;
  const tradingStop      = document.getElementById('tradingStop').value;
  const resumeDateStr    = document.getElementById('resumeDate').value;

  if (!stockName)          { showSearchError('종목명을 입력해주세요.'); return; }
  if (!designationDateStr) { showSearchError('지정일을 입력해주세요.');  return; }

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
  const m = String(releaseDate.getMonth()+1).padStart(2,'0');
  const d = String(releaseDate.getDate()).padStart(2,'0');
  appState.warning.releaseDate = releaseDate;
  rc.dataset.releaseDate = `${y}-${m}-${d}`;

  // Rules
  renderRules(releaseDate);
  document.getElementById('sec-rules').style.display = '';

  rc.classList.add('show');
  rc.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// 경고 탭 인라인 SVG 차트 — NAVER 일별 주가 + 3개 임계선
// TV 무료 embed는 한국 소형주 차트 렌더가 막혀 AAPL로 fallback되므로 사용하지 않음.
function renderInlineChart(priceData, stockCode, stockName) {
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

  const fmt = n => Number(n).toLocaleString('ko-KR');

  // 임계선 3개
  const lines = [];
  if (typeof t.thresh1 === 'number') {
    const y = yScale(t.thresh1);
    lines.push(`<line x1="${padL}" y1="${y}" x2="${padL + innerW}" y2="${y}" stroke="#FFFFFF" stroke-width="1" stroke-dasharray="4 3" opacity="0.65"/>`);
    lines.push(`<text x="${padL + innerW - 4}" y="${y - 4}" fill="#FFFFFF" font-size="9" font-family="var(--mono)" text-anchor="end" opacity="0.85">① ${fmt(t.thresh1)}</text>`);
  }
  if (typeof t.thresh2 === 'number') {
    const y = yScale(t.thresh2);
    lines.push(`<line x1="${padL}" y1="${y}" x2="${padL + innerW}" y2="${y}" stroke="#F04452" stroke-width="1" stroke-dasharray="4 3" opacity="0.7"/>`);
    lines.push(`<text x="${padL + innerW - 4}" y="${y - 4}" fill="#F04452" font-size="9" font-family="var(--mono)" text-anchor="end" opacity="0.9">② ${fmt(t.thresh2)}</text>`);
  }
  if (typeof t.max15 === 'number') {
    const y = yScale(t.max15);
    lines.push(`<line x1="${padL}" y1="${y}" x2="${padL + innerW}" y2="${y}" stroke="#4ADE80" stroke-width="1" stroke-dasharray="4 3" opacity="0.7"/>`);
    lines.push(`<text x="${padL + innerW - 4}" y="${y - 4}" fill="#4ADE80" font-size="9" font-family="var(--mono)" text-anchor="end" opacity="0.9">③ ${fmt(t.max15)}</text>`);
  }

  // Y축 눈금 라벨
  const yAxisLabels = yTicks.map(tk => `
    <line x1="${padL}" y1="${tk.y}" x2="${padL + innerW}" y2="${tk.y}" stroke="var(--tm-hairline)" stroke-width="0.5" opacity="0.6"/>
    <text x="${padL - 8}" y="${tk.y + 3}" fill="var(--tm-text-mute)" font-size="9" font-family="var(--mono)" text-anchor="end">${fmt(Math.round(tk.v))}</text>`).join('');

  // X축 라벨
  const xAxisLabels = xLabels.map(l => `
    <text x="${l.x}" y="${H - 10}" fill="var(--tm-text-mute)" font-size="9" font-family="var(--mono)" text-anchor="middle">${escHtml(l.label)}</text>`).join('');

  // T 종가 텍스트는 임계선과 겹치지 않도록 차트 외부 범례(#chartLegend)로 이동

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
async function syncTvChartByName(stockName) {
  if (!stockName) return;
  const chartRequestId = ++appState.chart.requestId;
  try {
    const codeData = await fetchJson(`/api/stock-code?name=${encodeURIComponent(stockName)}`);
    if (!isCurrentChart(chartRequestId)) return;
    if (apiErrorMessage(codeData) || !codeData.items || codeData.items.length === 0) return;
    const code = safeStockCode(codeData.items[0].code);
    if (!code) return;
    // 이미 같은 종목 차트 마운트돼 있으면 스킵
    if (appState.chart.code === code) return;
    const priceData = await fetchJson(`/api/stock-price?code=${encodeURIComponent(code)}`);
    if (!isCurrentChart(chartRequestId)) return;
    if (apiErrorMessage(priceData) || priceData.error) return;
    renderInlineChart(priceData, code, stockName);
    if (priceData.thresholds) renderChartLegend(priceData.thresholds, priceData);
  } catch (e) { /* 네트워크/서버 오류는 조용히 무시 */ }
}

(function(){
  const items = [
    'ㅅㅅㅅ 금지','가즈아 금지','심상정인데? 금지','오늘 xxx 개쎄다 금지',
    '거래대금 언급 금지','거래량 보소 금지','미쳤다 금지','다행이다 금지',
    '차 살까? 금지','계좌 고점이다 금지','나이스! 금지','xxx 왜 안삼? 금지',
    '했제 금지','해외 골프 금지'
  ];
  const track = document.getElementById('tickerTrack');
  // 두 번 반복해서 끊김 없는 무한 스크롤
  const html = items.map(t => '<span class="ticker-item">' + t + '</span>').join('');
  track.innerHTML = html + html;
})();

// Terminal sub-bar live clock
(function(){
  const el = document.getElementById('tmClock');
  if (!el) return;
  function tick() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    el.textContent = pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }
  tick();
  setInterval(tick, 1000);
})();
