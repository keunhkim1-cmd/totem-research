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
  '오래된 종목 하나가 새로운 의미를 얻습니다.',
  '미국 시장을 보면 생각이 정리됩니다.',
  '익숙한 종목이 새로운 모습으로 다가옵니다.',
  '천천히 살피는 마음이 좋은 흐름을 만나게 합니다.',
  '차분히 기다리는 사람에게 기회가 다가옵니다.',
  '작게 적어둔 메모 하나가 오늘 빛을 발합니다.',
  '마음에 둔 종목이 잔잔히 자리를 잡습니다.',
  '묵혀둔 관심이 다시 살아나는 하루입니다.',
  '가만히 들여다본 차트가 부드럽게 말을 겁니다.',
  '조용한 하루가 작은 발견을 데려옵니다.',
];

export function createSecondaryPageRenderers({
  apiErrorMessage,
  appState,
  escHtml,
  fetchJson,
  setElementState,
}) {
  function renderFortune() {
    const container = document.getElementById('fortuneContent');
    const titleEl = document.getElementById('fortunePanelTitle');
    if (!container) return;
    if (titleEl) titleEl.textContent = '행운이 함께하기를!';
    container.innerHTML = `
      <button type="button" class="fortune-cookie" aria-label="오늘의 운세 열기">🥠</button>`;

    const cookieBtn = container.querySelector('.fortune-cookie');
    if (!cookieBtn) return;
    cookieBtn.addEventListener('click', () => {
      const message = fortuneDeck[Math.floor(Math.random() * fortuneDeck.length)];
      const dots = ['.', '..', '...'];
      container.innerHTML = `<p class="fortune-message fortune-message--loading">${dots[0]}</p>`;
      let step = 0;
      const stepMs = 400;
      const timer = setInterval(() => {
        step += 1;
        if (step < dots.length) {
          const el = container.querySelector('.fortune-message');
          if (el) el.textContent = dots[step];
        } else {
          clearInterval(timer);
          container.innerHTML = `<p class="fortune-message">${escHtml(message)}</p>`;
        }
      }, stepMs);
    }, { once: true });
  }

  function forecastSummaryHtml(data) {
    const summary = data.summary || {};
    const generated = data.generatedAt ? String(data.generatedAt).replace('T', ' ') : '—';
    const cells = [
      ['기준일', data.todayKst || '—', generated],
      ['경보', summary.alert || 0, '공개 조건 충족'],
      ['근접', summary.near || 0, '고위험 후보'],
      ['관찰', summary.watch || 0, `확인 필요 ${summary.needsReview || 0}`],
    ];
    return cells.map(([label, value, sub]) => `
      <div class="tm-cell">
        <div class="l">${escHtml(label)}</div>
        <div class="v">${escHtml(value)}</div>
        <div class="s">${escHtml(sub)}</div>
      </div>`).join('');
  }

  function forecastErrorsHtml(errors) {
    if (!Array.isArray(errors) || errors.length === 0) return '';
    const message = errors.map(error => error?.message || String(error)).filter(Boolean).join(' · ');
    if (!message) return '';
    return `
      <div class="state-message state-message-error forecast-source-error" role="alert">
        <span class="state-message-label">${escHtml('확인 필요')}</span>
        <span class="state-message-text">${escHtml(message)}</span>
      </div>`;
  }

  function forecastSignalText(item) {
    const signal = item.forecastSignal || {};
    if (signal.primarySignal) return signal.primarySignal;
    if (item.calcStatus === 'calculated') {
      const escalation = item.escalation || {};
      const headline = escalation.headline || {};
      const sets = Array.isArray(escalation.sets) ? escalation.sets : [];
      if (item.level === 'alert') {
        const matched = sets[headline.matchedSet] || {};
        return `${matched.label || '공개 가격조건'} 충족`;
      }
      return '공개 가격조건 미충족';
    }
    return item.calcDetail || item.calcStatusLabel || '확인 필요';
  }

  function forecastSignalMeta(item) {
    const signal = item.forecastSignal || {};
    const parts = [];
    const score = Number(signal.riskScore ?? item.riskScore);
    if (Number.isFinite(score) && score > 0) parts.push(`risk ${Math.max(0, Math.min(100, Math.round(score)))}`);
    if (signal.remainingText) parts.push(signal.remainingText);
    return parts.join(' · ') || item.calcStatusLabel || '';
  }

  function forecastScoreHtml(item) {
    if (item.calcStatus !== 'calculated') return '';
    const signal = item.forecastSignal || {};
    const raw = Number(signal.riskScore ?? item.riskScore ?? 0);
    const score = Number.isFinite(raw) ? Math.max(0, Math.min(100, Math.round(raw))) : 0;
    return `<div class="forecast-scorebar" aria-hidden="true"><span style="width:${score}%"></span></div>`;
  }

  function renderForecastRows(items) {
    if (!Array.isArray(items) || items.length === 0) {
      return `
        <table class="tm-tbl forecast-table">
          <tbody>
            <tr class="state-row"><td>${escHtml('활성 투자경고 지정예고 후보가 없습니다.')}</td></tr>
          </tbody>
        </table>`;
    }
    const rows = items.map((item) => {
      const levelClass = ['alert', 'near', 'review'].includes(item.level) ? item.level : 'watch';
      const code = item.code ? ` · ${item.code}` : '';
      const market = item.market || item.krxMarket || '시장 미확인';
      const windowText = `${item.firstJudgmentDate || '—'} ~ ${item.lastJudgmentDate || '—'}`;
      const dayText = `판단 ${item.judgmentDayIndex || 0}/${item.judgmentWindowTotal || 10}`;
      return `
        <tr class="forecast-row forecast-row-${levelClass}">
          <td><span class="forecast-level ${levelClass}">${escHtml(item.levelLabel || '주의보')}</span></td>
          <td>
            <div class="forecast-stock">${escHtml(item.stockName || '—')}</div>
            <div class="forecast-meta">${escHtml(market + code)}</div>
          </td>
          <td>
            <div class="forecast-window">${escHtml(windowText)}</div>
            <div class="forecast-meta">${escHtml(dayText)}</div>
          </td>
          <td>
            <div class="forecast-signal">${escHtml(forecastSignalText(item))}</div>
            <div class="forecast-meta">${escHtml(forecastSignalMeta(item))}</div>
            ${forecastScoreHtml(item)}
          </td>
          <td><button type="button" class="forecast-check" data-stock="${escHtml(item.stockName || '')}">점검</button></td>
        </tr>`;
    }).join('');
    return `
      <table class="tm-tbl forecast-table">
        <thead>
          <tr>
            <th>예보</th>
            <th>종목</th>
            <th>판단 기간</th>
            <th>근접도</th>
            <th>동작</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  function bindForecastChecks(container) {
    container.querySelectorAll('.forecast-check').forEach(button => {
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('totem:forecast-check', {
          detail: { stockName: button.dataset.stock || '' },
        }));
      });
    });
  }

  async function renderMarketForecast(options = {}) {
    const force = Boolean(options.force);
    const summaryEl = document.getElementById('forecastSummary');
    const container = document.getElementById('forecastContent');
    if (!container || !summaryEl) return;
    if (appState.forecast.loaded && !force) return;
    if (appState.serverBase === null) {
      summaryEl.innerHTML = '';
      setElementState(container, '로컬 서버 실행 후 예보를 조회할 수 있습니다.', 'empty');
      return;
    }

    summaryEl.innerHTML = '';
    setElementState(container, '투자경고 예보를 불러오는 중...', 'loading');
    try {
      const data = await fetchJson('/api/market-alert-forecast', { cache: 'no-cache' });
      const error = apiErrorMessage(data);
      if (error) {
        throw new Error(error);
      }
      const sourceErrors = Array.isArray(data.errors) ? data.errors : [];
      const items = Array.isArray(data.items) ? data.items : [];
      if (sourceErrors.length > 0 && items.length === 0) {
        throw new Error(sourceErrors[0]?.message || '예보 원천 데이터를 확인할 수 없습니다.');
      }
      appState.forecast.loaded = true;
      appState.forecast.items = items;
      summaryEl.innerHTML = forecastSummaryHtml(data);
      container.innerHTML = forecastErrorsHtml(sourceErrors) + renderForecastRows(appState.forecast.items);
      bindForecastChecks(container);
    } catch (e) {
      appState.forecast.loaded = false;
      summaryEl.innerHTML = '';
      setElementState(container, `투자경고 예보를 불러올 수 없습니다: ${e.message}`, 'error');
    }
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

  return { renderFortune, renderMarketForecast, renderPatchNotes };
}
