// 앱 부트스트랩 — 모듈 결합 + 이벤트 와이어 + 초기화.
import { createSecondaryPageRenderers } from './secondary_pages.js?v=20260426-101';
import { appState } from './app/state.js?v=20260426-101';
import {
  escHtml,
  fetchJson,
  hideSearchResults,
  setElementState,
  showRuntimeError,
} from './app/dom_utils.js?v=20260426-101';
import { toDateStr } from './app/calendar.js?v=20260426-101';
import { doSearch, selectResult } from './app/search.js?v=20260426-101';

// ────────────────────────────────────────────────
// 전역 에러 핸들러
// ────────────────────────────────────────────────
window.addEventListener('error', event => {
  showRuntimeError(event.error || event.message);
});
window.addEventListener('unhandledrejection', event => {
  showRuntimeError(event.reason || 'Unhandled promise rejection');
});

// ────────────────────────────────────────────────
// 공휴일 (data/holidays.json 단일 소스) — appState로 노출해 다른 모듈이 await
// ────────────────────────────────────────────────
appState.holidaysReady = fetchJson('/data/holidays.json')
  .then(arr => { appState.holidays = new Set(arr); })
  .catch(e => console.warn('공휴일 데이터 로드 실패, 주말만 판정합니다:', e));

// ────────────────────────────────────────────────
// 페이지 전환 (about / warning / fortune / patchnotes)
// ────────────────────────────────────────────────
const { renderFortune, renderPatchNotes } = createSecondaryPageRenderers({
  appState,
  escHtml,
  fetchJson,
  setElementState,
});

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

// 로컬 서버 상태 확인 (file:// 직접 열기일 때 검색 기능 비활성)
function checkServer() {
  if (appState.serverBase === null) {
    document.getElementById('serverNotice').classList.add('show');
    document.getElementById('searchBtn').disabled = true;
    document.getElementById('searchBtn').title = '로컬 서버를 먼저 실행하세요';
  }
}
checkServer();

// ────────────────────────────────────────────────
// 이벤트 와이어
// ────────────────────────────────────────────────
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

document.getElementById('searchResults').addEventListener('click', (e) => {
  const item = e.target.closest('.result-item');
  if (item && item.dataset.idx != null) {
    selectResult(appState.search.results[item.dataset.idx]);
  }
});

// 외부 클릭 시 검색 결과 닫기
document.addEventListener('click', (e) => {
  if (!e.target.closest('.form-group')) {
    hideSearchResults();
  }
});

// 지정일 기본값(오늘)
document.getElementById('designationDate').value = toDateStr(new Date());

// 하단 티커 (재미용 — 두 번 반복해서 끊김 없는 무한 스크롤)
(function () {
  const items = [
    'ㅅㅅㅅ 금지', '가즈아 금지', '심상정인데? 금지', '오늘 xxx 개쎄다 금지',
    '거래대금 언급 금지', '거래량 보소 금지', '미쳤다 금지', '다행이다 금지',
    '차 살까? 금지', '계좌 고점이다 금지', '나이스! 금지', 'xxx 왜 안삼? 금지',
    '했제 금지', '해외 골프 금지'
  ];
  const track = document.getElementById('tickerTrack');
  const html = items.map(t => '<span class="ticker-item">' + t + '</span>').join('');
  track.innerHTML = html + html;
})();
