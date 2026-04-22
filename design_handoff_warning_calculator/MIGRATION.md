# MIGRATION

기존 `shamanism-research/index.html` (vanilla JS · 단일 파일) 을 이 시안 톤으로 포팅하는 **순서**. 각 단계는 **독립적으로 머지 가능**하게 쪼개져 있습니다.

---

## 전제

- 기존 파일: `shamanism-research/index.html` (약 2,100 라인, 단일 HTML)
- 기존 페이지 전환: `switchPage(name, btn)` 전역 함수 (유지)
- 기존 API: `/api/warn-search` · `/api/caution-search` · `/api/stock-price` · `/api/stock-overview` · `/api/dart-list` (유지)
- 기존 글로벌: `currentStock`, `warningResult`, `priceSnapshot` 등 (유지)

**이 포팅 작업은 "투자경고 계산기" 페이지의 HTML/CSS만 교체**합니다. JS 로직·API·다른 탭은 건드리지 않습니다.

---

## Step 1 · 토큰 주입 (15분)

1. `index.html` 의 `<style>` 내 `:root { ... }` 블록 하단에 `DESIGN_TOKENS.md` 의 `--tm-*` 변수 **전부 복붙**.
2. 폰트 변수(`--font-display / --font-text / --mono`) 는 이미 있으므로 **건드리지 않음**.
3. 페이지 전환 확인: `재무 현황`, `공시 분석기`, `패치 노트`, `About` 탭이 모두 정상 동작해야 함 (변경한 게 CSS 변수 추가뿐이므로 영향 없음).

**커밋 단위**: `feat(tokens): add terminal mono-night tokens for warning calculator`

---

## Step 2 · 래퍼 + 스코프 (10분)

1. `<div id="page-warning" class="page-section">` 내부에 **최상위 wrapper** 추가:
   ```html
   <div id="page-warning" class="page-section">
     <div class="warning-terminal">
       <!-- 기존 내용 전부 이 안으로 -->
     </div>
   </div>
   ```
2. `.warning-terminal` 스코프 스타일 추가 (COMPONENTS.md §0 기본 스타일).
3. 이 시점에서 다른 탭은 기존 톤 유지, 투자경고 탭만 배경이 `#0A0A0A` 로 살짝 바뀌어야 함.

**커밋**: `refactor(warning): wrap in .warning-terminal scope`

---

## Step 3 · 네비게이션 라벨 정합 (5분)

현재 라벨은 이미 `재무 현황 (개발중)` 등으로 되어있음 (확인됨). 터미널 시안은 네비 자체를 **재사용** 하고 스타일만 덮어씁니다.

1. 기존 `.nav-bar / .nav-inner / .nav-item` 스타일은 그대로 두되, `.warning-terminal` 스코프 안에서 **터미널 버전 `.tm-top / .tm-nav`** 를 추가.
2. **옵션 A (권장)**: 네비는 원본 그대로 두고, `.warning-terminal` 내부에 **별도 상단 바(`.tm-top`)** 추가. 탭 네비는 원본 한 벌만.
3. **옵션 B**: 원본 `.nav-bar` 를 `.tm-top` 스타일로 덮어쓰기. 단, 다른 탭에서도 보여지므로 **해당 탭을 클릭했을 때만 터미널 스타일**이 되도록 `body.page-warning-active .nav-bar { ... }` 조건부 적용.

본 가이드는 **옵션 A** 기준. 즉, 투자경고 계산기 탭 안에 `.tm-top` 이 하나 더 들어갑니다(종목 정보 + 실시간 시계).

**커밋**: `feat(warning): add terminal sub-bar with clock`

---

## Step 4 · 결과 영역 재구성 (핵심, 45분)

기존 구조:

```
#result-container
├── .search-result (.result-card / .price-card / .warning-box ...)
├── .price-snapshot
├── .conditions
└── ...
```

→ 이 자리를 **섹션 스택**으로 교체:

```html
<div id="result-container" class="warning-terminal">
  <div class="tm-top">…</div>
  <div class="tm-sym" id="sym-header">…</div>
  <section class="tm-sec tm-tl" id="sec-timeline">…</section>
  <section class="tm-sec" id="sec-conditions">
    <div class="tm-sec-head">…</div>
    <table class="tm-tbl">…</table>
    <div class="tm-verdict">…</div>
  </section>
  <section class="tm-sec" id="sec-chart">…</section>
  <section class="tm-sec" id="sec-price">
    <div class="tm-sec-head">…</div>
    <div class="tm-strip">…</div>
  </section>
  <section class="tm-sec" id="sec-rules">…</section>
  <div class="tm-tape">…</div>
</div>
```

### 4-1 Symbol Header 바인딩

기존 `renderWarningResult(data)` 내부에서 `#result-card .name` / `.code` / `.price` 등에 값을 꽂던 코드를 **`#sym-header` 하위 `.ticker / .name / .meta / .px .val / .px .chg` 로 재작성**.

```js
function renderSymHeader(stock, price) {
  const h = document.getElementById('sym-header');
  h.querySelector('.ticker').textContent = stock.code;
  h.querySelector('.name').textContent = `${stock.name} · ${stock.nameEn || ''}`;
  h.querySelector('.meta').textContent = `${stock.market} · ${stock.sector} · 시총 ${stock.marketCap} · 지정 ${stock.designatedAt}`;
  h.querySelector('.px .val').textContent = fmt(price.close);
  const delta = price.close - price.prevClose;
  h.querySelector('.px .chg').textContent = `${delta >= 0 ? '▲' : '▼'} ${fmt(Math.abs(delta))} · ${delta >= 0 ? '+' : ''}${((delta / price.prevClose) * 100).toFixed(2)}%`;
  h.querySelectorAll('.px .val, .px .chg').forEach(el => el.style.color = delta >= 0 ? 'var(--tm-up)' : 'var(--tm-dn)');
}
```

### 4-2 타임라인 바인딩

```js
function renderTimeline(desig, today, release) {
  // desig=지정일, today=T, release=해제가능일
  const cells = document.querySelector('#sec-timeline .tm-tl-track').children;
  const daysPassed = calcBusinessDays(desig, today);  // 기존 util 가정
  for (let i = 0; i < 11; i++) {
    const cls = i < daysPassed ? 'past' : i === daysPassed ? 'today' : 'release';
    cells[i].className = `tm-tl-cell ${cls}`;
  }
  // foot: 지정·T·해제 날짜 치환
}
```

### 4-3 조건 테이블 바인딩

`warningResult.conditions` 배열 (①②③) 각 항목을 `<tr>` 하나로 렌더:

```js
function renderConditions(conds) {
  const tbody = document.querySelector('#sec-conditions tbody');
  tbody.innerHTML = conds.map((c, i) => {
    const statusClass = c.met ? 'hold' : 'clear';   // met = 조건 충족 = 경고 유지
    const flag = c.met ? '유지' : '이탈';
    const deltaClass = c.delta >= 0 ? 'up' : 'dn';
    const sign = c.delta >= 0 ? '+' : '';
    return `
      <tr class="${statusClass}">
        <td>
          <div class="lbl-col">
            <div class="badge">${i + 1}</div>
            <div class="txt">
              <div class="n">${c.formula}</div>
              <div class="d">${c.desc}</div>
            </div>
          </div>
        </td>
        <td class="num">${c.refDate}</td>
        <td class="num">${fmt(c.refClose)}</td>
        <td>${c.multiplier}</td>
        <td class="num accent">${fmt(c.threshold)}</td>
        <td class="num ${deltaClass}">${fmt(c.tClose)}</td>
        <td class="num ${deltaClass}">${sign}${c.delta.toFixed(2)}%</td>
        <td><span class="flag ${statusClass}">${flag}</span></td>
      </tr>`;
  }).join('');
}
```

### 4-4 Verdict 바인딩

세 상태:

```js
function renderVerdict(result) {
  const v = document.querySelector('.tm-verdict');
  const anyClear = result.conditions.some(c => !c.met);
  if (anyClear) {
    v.className = 'tm-verdict';
    v.querySelector('.tag').textContent = '다음 거래일 해제';
    v.querySelector('.h').textContent = `다음 거래일(${result.releaseDate}) 투자경고 해제`;
    /* ... */
  } else {
    v.classList.add('hold');  // amber tone variant
    /* ... */
  }
}
```

---

## Step 5 · 차트 (30분)

목업은 SVG 손그림. 실제 구현:

1. 프로젝트에 이미 차트 라이브러리가 있으면 그거 사용.
2. 없으면 **Lightweight-Charts** (가벼움·경량) 또는 **Recharts** 추천.
3. 스타일은 `COMPONENTS.md §7` 의 렌더러 규칙만 지키면 됨.
4. Threshold 3본(①②③)은 라이브러리의 **price line / horizontal line** 기능으로 추가.

**중요**: 빈 상태에선 차트 컨테이너(`#chart-container`)를 숨기거나 skeleton bar 표시.

---

## Step 6 · 티커 테이프 (10분)

1. 기존 `index.html` 최하단(fixed footer) 에 이미 티커 테이프가 있다면 **해당 마크업을 투자경고 계산기 페이지 안으로 이동**.
2. 금지어 배열(`TABOO_WORDS`) 은 기존 전역 상수를 그대로 사용.
3. 다른 탭에도 하단 테이프가 필요한지 확인 (현재 시안은 투자경고 탭에만).

---

## Step 7 · 반응형 (15분)

- **≥ 1200px**: 사이드바 포함 3컬럼. 본 v1 에선 사이드바 제거 권장 (COMPONENTS.md §11).
- **768 ~ 1199px**: 메인만. 조건 테이블은 가로 스크롤.
- **< 768px (모바일)**: 조건 테이블을 카드 3장으로 대체. 타임라인은 가로 스크롤. 티커 테이프 라벨 숨김.

우선 순위 낮음 — v1 은 데스크톱 1380px 기준 고정 레이아웃으로.

---

## Step 8 · 엣지 케이스 (20분)

| 케이스 | 처리 |
|---|---|
| 종목 미선택 | 결과 섹션 전체 `display: none`. 검색 placeholder만. |
| 종목이 경고 대상이 아님 | Symbol Header + 기본 시세만 표시. 타임라인/조건/Verdict는 비노출. Verdict 자리에 "이 종목은 현재 투자경고 지정 대상이 아닙니다" 정보 박스. |
| API 실패 | 해당 섹션 영역에 `<div class="tm-error">데이터 조회 실패 · 재시도</div>` (border: 1px dashed var(--tm-up-soft)). |
| 장 미마감 | `today` 셀이 전일 `T` 로 고정. Verdict 태그는 "장중 · 판정 미정". |
| 거래정지 | 조건 테이블 전체 skeleton gray. Verdict 태그 "판정 보류 (거래정지)". |

---

## Step 9 · QA 체크리스트

- [ ] `--tm-*` 변수가 **투자경고 계산기 탭 밖에서 참조되지 않음** (grep 해서 확인).
- [ ] 기존 `--blue` / `--up` / `--down` 값은 **변경되지 않음**.
- [ ] 다른 3 탭(`재무현황 / 공시분석기 / 패치노트 / About`) 시각적으로 동일.
- [ ] 네비 active 상태 전환 정상.
- [ ] SF Pro 폰트 렌더링 확인 (macOS/iOS 외 플랫폼에서 `Helvetica` fallback 가독성).
- [ ] `toLocaleString('ko-KR')` 콤마 구분자 확인.
- [ ] 티커 테이프 60s 루프 seamless 확인 (복제 2배 렌더).
- [ ] 조건 ①②③ 3행이 모두 HOLD일 때·CLEAR일 때·N/A일 때 각각 스냅샷.
- [ ] Verdict 카드 3 변형(다음 거래일 해제 / 경고 유지 / 위험 상향) 렌더 확인.
- [ ] Lighthouse 성능 점수 기존 대비 -5점 이내.

---

## Step 10 · v2 로 미루기

**이번 범위 밖**:

- 관심종목 사이드바 (저장소 미구현)
- 공시 피드 사이드바 (별도 탭과 중복)
- 투자 위험종목 상향 지정 시뮬레이터
- 차트 크로스헤어 인터랙션
- 모바일 최적화

---

## 예상 공수

| 단계 | 시간 |
|---|---|
| 1. 토큰 주입 | 15m |
| 2. 스코프 래퍼 | 10m |
| 3. 네비 | 5m |
| 4. 결과 영역 재구성 | 45m |
| 5. 차트 | 30m |
| 6. 티커 테이프 | 10m |
| 7. 반응형 | 15m |
| 8. 엣지 | 20m |
| 9. QA | 20m |
| **Total** | **~2.5h** |

충분히 단일 PR 로 가능한 크기.
