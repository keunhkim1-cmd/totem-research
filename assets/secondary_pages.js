const fortuneDeck = [
  '오늘은 물타기를 조심하세요.',
  '뜻밖의 종목이 가까이 다가옵니다.',
  '서두르지 않으면 좋은 공시가 들려옵니다.',
  '뉴스 한 줄이 새로운 흐름을 엽니다.',
  '오래된 차트가 오늘의 답을 가져옵니다.',
  '낯선 섹터에서 익숙한 패턴을 만나게 됩니다.',
  '잠시 매수를 멈추면 더 멀리 보입니다.',
  '작은 분할매수가 큰 수익으로 돌아옵니다.',
  '오늘 본 사소한 거래량이 내일의 단서가 됩니다.',
  '잊고 있던 종목이 문득 떠오를 것입니다.',
  '한 번 더 검토하는 사람이 수익을 찾습니다.',
  '오늘은 해외 시장 창을 한 번 열어 보세요.',
  '소중한 종목을 만날지도 모릅니다.',
  '오래 미뤄둔 손절이 마음을 가볍게 합니다.',
  '예상치 못한 종목에서 작은 배당이 옵니다.',
  '오늘은 관망이 가장 좋은 매매입니다.',
  '오래된 종목 하나가 새로운 의미를 얻습니다.',
  '미국 시장을 보면 생각이 정리됩니다.',
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

export function createSecondaryPageRenderers({
  appState,
  escHtml,
  fetchJson,
  setElementState,
}) {
  function renderFortune() {
    const container = document.getElementById('fortuneContent');
    const titleEl = document.getElementById('fortunePanelTitle');
    if (!container) return;
    const dateInfo = getKstDateInfo();
    if (appState.fortune.dateKey === dateInfo.key && container.innerHTML) return;
    const message = fortuneDeck[fortuneIndex(dateInfo.key, fortuneDeck.length)];
    const [, month, day] = dateInfo.key.split('-');
    if (titleEl) titleEl.textContent = `${month}월 ${day}일 운세`;
    container.innerHTML = `
      <p class="fortune-message">${escHtml(message)}</p>`;
    appState.fortune.dateKey = dateInfo.key;
  }

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

  return { renderFortune, renderPatchNotes };
}
