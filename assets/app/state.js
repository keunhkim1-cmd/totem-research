// 앱 전역 상태와 요청 ID 헬퍼.
// 부수효과 없음 — DOM/네트워크에 닿지 않는다.
export const appState = {
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
  // 부트스트랩(app.js)이 실제 fetch 프라미스로 덮어쓴다.
  holidaysReady: Promise.resolve(),
  serverBase: window.location.protocol === 'file:' ? null : '',
};

export function isCurrentSearch(requestId) {
  return requestId === appState.search.requestId;
}

export function isCurrentWarning(requestId) {
  return requestId === appState.warning.requestId;
}

export function isCurrentChart(requestId) {
  return requestId === appState.chart.requestId;
}
