# COMPONENTS

섹션별 마크업 패턴. 모든 예시는 **기존 `index.html` 의 vanilla HTML/CSS 문법**으로 씁니다 (JSX 아님). 목업 JSX에서 `className` → `class`, 중괄호 보간 → 템플릿 리터럴 또는 `innerHTML`.

모든 컴포넌트는 `<div class="warning-terminal"> ... </div>` wrapper 안에서 사용하세요 — 토큰 스코프 격리(`DESIGN_TOKENS.md` 3.참고).

---

## 1. 섹션 래퍼 · 헤더

**모든 섹션**은 이 패턴을 공유합니다.

```html
<section class="tm-sec">
  <div class="tm-sec-head">
    <span class="t">지정 타임라인 · 10 거래일</span>
    <span class="src">T · 9거래일 경과 · 해제 D-1</span>
  </div>
  <!-- 내용 -->
</section>
```

```css
.tm-sec { border-bottom: 1px solid var(--tm-hairline); }
.tm-sec-head {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 16px 9px;
  font-family: var(--font-display);
  font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase;
}
.tm-sec-head .t {
  color: var(--tm-text); font-weight: 500;
  border-left: 2px solid var(--tm-accent); padding-left: 10px;
}
.tm-sec-head .src {
  margin-left: auto; color: var(--tm-text-mute);
  font-size: 9px; font-family: var(--mono); letter-spacing: 0.3px;
  text-transform: none;
}
```

---

## 2. 상단 네비 (기존 `.nav-bar` 를 터미널 버전으로 스와프)

```html
<div class="tm-top">
  <span class="tm-logo">샤머니즘 리서치</span>
  <nav class="tm-nav">
    <button onclick="switchPage('dashboard', this)">재무 현황 (개발중)</button>
    <button class="active" onclick="switchPage('warning', this)">투자경고 계산기</button>
    <button onclick="switchPage('dart', this)">공시 분석기 (개발중)</button>
    <button onclick="switchPage('patchnotes', this)">패치 노트</button>
  </nav>
  <div class="tm-status"><span class="num" id="clock">14:32</span></div>
</div>
```

```css
.tm-top { display: flex; align-items: center; height: 30px; background: #000;
          border-bottom: 1px solid var(--tm-hairline); padding: 0 12px; gap: 16px; font-size: 10px; }
.tm-logo { color: var(--tm-accent); font-weight: 600; letter-spacing: 0.8px; font-family: var(--font-display); }
.tm-nav { display: flex; height: 100%; align-items: stretch; }
.tm-nav button { color: var(--tm-text-mute); padding: 0 14px; font-size: 10px; letter-spacing: 0.8px;
                 text-transform: uppercase; border-bottom: 2px solid transparent; background: transparent;
                 border: none; border-bottom: 2px solid transparent; font-family: var(--font-display); cursor: pointer; }
.tm-nav button.active { color: var(--tm-accent); border-bottom-color: var(--tm-accent); }
.tm-status { margin-left: auto; color: var(--tm-text-mute); }
```

**기존 `switchPage()` 함수 그대로 사용**. 라벨만 "(개발중)" 서픽스 추가.

---

## 3. Symbol Header

```html
<div class="tm-sym">
  <div class="ticker">086520</div>
  <div class="name-block">
    <div class="name">에코프로 · EcoPro Co</div>
    <div class="meta">KOSDAQ · 2차전지 · 시총 15.4조 · 지정 2026-04-08</div>
  </div>
  <div class="chips">
    <span class="chip warn">투자경고 지정중</span>
    <span class="chip dday">D-1</span>
  </div>
  <div class="px">
    <span class="val num">584,000</span>
    <span class="chg">▲ 23,000 · +4.10%</span>
  </div>
</div>
```

```css
.tm-sym { display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-bottom: 1px solid var(--tm-hairline); }
.tm-sym .ticker { font-family: var(--font-display); font-size: 26px; font-weight: 600; color: var(--tm-accent); letter-spacing: 0.5px; line-height: 1; }
.tm-sym .name { font-size: 13px; color: var(--tm-text); font-family: var(--font-text); }
.tm-sym .meta { font-size: 10px; color: var(--tm-text-mute); font-family: var(--font-text); }
.tm-sym .chips { margin-left: auto; display: flex; gap: 6px; }
.tm-sym .chip { font-size: 9px; padding: 3px 8px; letter-spacing: 1px; font-weight: 600; text-transform: uppercase; }
.tm-sym .chip.warn { background: var(--tm-accent-soft); color: var(--tm-accent); border: 1px solid var(--tm-accent); }
.tm-sym .chip.dday { background: var(--tm-toss-soft); color: var(--tm-toss); border: 1px solid var(--tm-toss); }
.tm-sym .px { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; margin-left: 24px; }
.tm-sym .px .val { font-size: 22px; color: var(--tm-up); font-weight: 500; letter-spacing: -0.3px; line-height: 1; }
.tm-sym .px .chg { font-size: 11px; color: var(--tm-up); font-weight: 500; }
```

---

## 4. 타임라인

```html
<div class="tm-tl">
  <div class="tm-tl-track">
    <div class="tm-tl-cell past">D0</div>
    <div class="tm-tl-cell past">T+1</div>
    <!-- T+2 .. T+8 동일 패턴 (past) -->
    <div class="tm-tl-cell today">T+9</div>
    <div class="tm-tl-cell release">해제</div>
  </div>
  <div class="tm-tl-foot">
    <span><b>2026-04-08</b> · 지정</span>
    <span>T · <b>2026-04-21</b> · 9거래일 경과</span>
    <span><b>2026-04-22</b> · 해제 가능</span>
  </div>
</div>
```

```css
.tm-tl { padding: 10px 16px 16px; }
.tm-tl-track { display: grid; grid-template-columns: repeat(11, 1fr); gap: 2px; margin: 8px 0; }
.tm-tl-cell { height: 24px; background: #16161A; border: 1px solid var(--tm-hairline);
              display: flex; align-items: center; justify-content: center;
              font-size: 9px; color: var(--tm-text-mute); letter-spacing: 0.3px; }
.tm-tl-cell.past    { background: var(--tm-ok-soft); color: var(--tm-ok); border-color: rgba(74,222,128,0.3); }
.tm-tl-cell.today   { background: var(--tm-accent); color: #000; font-weight: 700; }
.tm-tl-cell.release { background: var(--tm-toss-soft); color: var(--tm-toss); border-color: var(--tm-toss); }
.tm-tl-foot { display: flex; justify-content: space-between; font-size: 9px; color: var(--tm-text-mute); margin-top: 4px; }
.tm-tl-foot b { color: var(--tm-text); font-family: var(--mono); font-weight: 500; }
```

**동작**: 장 마감 전엔 `today` 셀이 현재 `T+n`. 장 마감 후엔 다음 거래일로 앞당겨짐.

---

## 5. 조건 테이블 (핵심)

```html
<table class="tm-tbl">
  <thead>
    <tr>
      <th>조건</th><th>기준일</th><th>기준 종가</th><th>×</th>
      <th>임계가</th><th>T 종가</th><th>Δ</th><th>상태</th>
    </tr>
  </thead>
  <tbody>
    <tr class="hold">
      <td>
        <div class="lbl-col">
          <div class="badge">1</div>
          <div class="txt">
            <div class="n">T-5 종가 × 1.45</div>
            <div class="d">5일 45% 급등 테스트</div>
          </div>
        </div>
      </td>
      <td class="num">2026-04-14</td>
      <td class="num">398,000</td>
      <td>1.45×</td>
      <td class="num accent">577,100</td>
      <td class="num up">584,000</td>
      <td class="num up">+1.19%</td>
      <td><span class="flag hold">유지</span></td>
    </tr>
    <!-- ② hold · ③ clear 동일 패턴 -->
  </tbody>
</table>
```

```css
.tm-tbl { width: 100%; border-collapse: collapse; font-size: 11px; font-variant-numeric: tabular-nums; }
.tm-tbl th { font-family: var(--font-display); font-size: 9px; letter-spacing: 0.8px; text-transform: uppercase;
             color: var(--tm-text-mute); font-weight: 500; text-align: right; padding: 9px 14px;
             border-bottom: 1px solid var(--tm-hairline); background: var(--tm-panel); }
.tm-tbl th:first-child { text-align: left; }
.tm-tbl td { padding: 11px 14px; text-align: right; border-bottom: 1px solid var(--tm-hairline-soft); color: var(--tm-text); }
.tm-tbl td:first-child { text-align: left; }
.tm-tbl tr:last-child td { border-bottom: none; }
.tm-tbl .lbl-col { display: flex; align-items: center; gap: 10px; }
.tm-tbl .lbl-col .badge { width: 22px; height: 22px; border-radius: 50%;
                          display: flex; align-items: center; justify-content: center;
                          font-size: 10px; font-weight: 700; font-family: var(--font-display);
                          background: var(--tm-hairline); color: var(--tm-text-dim); flex-shrink: 0; }
.tm-tbl tr.hold  .lbl-col .badge { background: var(--tm-up-soft);  color: var(--tm-up);  border: 1px solid rgba(240,68,82,0.4); }
.tm-tbl tr.clear .lbl-col .badge { background: var(--tm-ok-soft);  color: var(--tm-ok);  border: 1px solid rgba(74,222,128,0.4); }
.tm-tbl .lbl-col .txt .n { color: var(--tm-text); font-family: var(--font-text); font-size: 12px; font-weight: 500; }
.tm-tbl .lbl-col .txt .d { color: var(--tm-text-mute); font-size: 10px; margin-top: 2px; font-family: var(--mono); }
.tm-tbl .up { color: var(--tm-up); } .tm-tbl .dn { color: var(--tm-dn); } .tm-tbl .accent { color: var(--tm-accent); }
.tm-tbl .flag { display: inline-block; padding: 2px 8px; font-size: 9px; letter-spacing: 1.2px; font-weight: 600; text-transform: uppercase; }
.tm-tbl .flag.hold  { background: var(--tm-up-soft);  color: var(--tm-up);  border: 1px solid var(--tm-up); }
.tm-tbl .flag.clear { background: var(--tm-ok-soft);  color: var(--tm-ok);  border: 1px solid var(--tm-ok); }
```

---

## 6. Verdict 카드

```html
<div class="tm-verdict">
  <div class="ico">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 8l3 3 7-7"/>
    </svg>
  </div>
  <div class="body">
    <div class="head"><span class="tag">다음 거래일 해제</span></div>
    <div class="h">다음 거래일(4/22) 투자경고 해제</div>
    <div class="b">조건 ③ <span class="num">15일 최고가 일치</span> 요건 미충족 · 10 거래일 경과 요건도 수요일에 충족. KRX §4-2 규정상 세 조건 중 하나라도 미충족이면 다음 거래일에 해제됩니다.</div>
  </div>
  <div class="side">
    <div class="d num">04-22</div>
    <div class="l">해제 가능일</div>
  </div>
</div>
```

```css
.tm-verdict { display: flex; align-items: center; gap: 14px; padding: 16px;
              background: linear-gradient(90deg, var(--tm-ok-soft), transparent 70%);
              border-left: 2px solid var(--tm-ok); }
.tm-verdict .ico { width: 36px; height: 36px; border-radius: 50%;
                   background: var(--tm-ok-soft); border: 1px solid var(--tm-ok); color: var(--tm-ok);
                   display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tm-verdict .tag { font-size: 9px; letter-spacing: 1.2px; color: var(--tm-ok);
                   padding: 2px 7px; background: var(--tm-ok-soft); font-weight: 600;
                   border: 1px solid var(--tm-ok); text-transform: uppercase; }
.tm-verdict .h { font-size: 15px; color: var(--tm-text); font-weight: 600; letter-spacing: -0.2px; margin-top: 3px; }
.tm-verdict .b { font-size: 12px; color: var(--tm-text-dim); line-height: 1.55; margin-top: 3px; }
.tm-verdict .side { border-left: 1px solid var(--tm-hairline); padding-left: 18px; margin-left: 6px; text-align: right; }
.tm-verdict .side .d { font-size: 18px; color: var(--tm-ok); letter-spacing: -0.3px; }
.tm-verdict .side .l { font-size: 9px; color: var(--tm-text-mute); letter-spacing: 1px; margin-top: 3px;
                       font-family: var(--font-display); text-transform: uppercase; }
```

**변형**: `.tm-verdict.hold` (warning amber / `--tm-amber`) · `.tm-verdict.risk` (red / `--tm-up`) — 같은 구조에서 색만 치환.

---

## 7. 차트 (컨테이너 스타일만; 실제 렌더러는 프로젝트 기존 것)

```html
<div class="tm-chart-wrap">
  <div class="tm-chart-tabs">
    <button>5D</button><button>15D</button><button class="active">30D</button>
    <div class="flex"></div>
    <div class="legend">
      <span><span class="sw" style="background:#FFFFFF"></span>① 577,100</span>
      <span><span class="sw" style="background:#F04452"></span>② 574,000</span>
      <span><span class="sw" style="background:#4ADE80"></span>③ 591,000</span>
    </div>
  </div>
  <div class="tm-chart" id="chart-container">
    <!-- 차트 라이브러리가 그림 -->
    <div class="crosshair"><span class="k">T 2026-04-21 · </span>종가 <b class="num" style="color:#F04452">584,000</b></div>
  </div>
</div>
```

```css
.tm-chart-wrap { padding: 8px 16px 16px; }
.tm-chart-tabs { display: flex; gap: 0; margin-bottom: 10px; }
.tm-chart-tabs button { font-size: 10px; letter-spacing: 0.5px; padding: 5px 11px;
                        color: var(--tm-text-mute); border: 1px solid var(--tm-hairline); border-right: none;
                        background: transparent; font-family: var(--font-display); font-weight: 500; cursor: pointer; }
.tm-chart-tabs button:last-of-type { border-right: 1px solid var(--tm-hairline); }
.tm-chart-tabs button.active { color: var(--tm-accent); background: var(--tm-accent-soft); border-color: var(--tm-accent); }
.tm-chart-tabs .flex { flex: 1; }
.tm-chart-tabs .legend { display: flex; gap: 14px; font-size: 10px; color: var(--tm-text-mute); align-items: center; }
.tm-chart-tabs .legend .sw { display: inline-block; width: 16px; height: 2px; vertical-align: middle; margin-right: 5px; }
.tm-chart { position: relative; height: 160px; background: linear-gradient(180deg, var(--tm-accent-soft), transparent 70%);
            border: 1px solid var(--tm-hairline); }
.tm-chart .crosshair { position: absolute; top: 8px; left: 10px; font-size: 10px; color: var(--tm-text-dim); }
.tm-chart .crosshair .k { color: var(--tm-text-mute); }
```

**차트 렌더러 규칙**:
- Line: `stroke: var(--tm-accent)` · `stroke-width: 1.5`
- Area fill: `linear-gradient(180deg, var(--tm-accent-soft), transparent 70%)`
- Threshold line 3본: `stroke-dasharray: 4 3` · `opacity: 0.7` · 색은 위 legend 와 일치
- 마지막 점(현재가): `fill: var(--tm-up)` · `stroke: var(--tm-bg)` · `stroke-width: 1.5` · `r: 3.5`
- 15일 최고점 마커: `fill: var(--tm-ok)` · `r: 2.5`

---

## 8. 기본 시세 스트립 (3셀)

```html
<div class="tm-strip">
  <div class="tm-cell"><div class="l">종가</div><div class="v up">584,000</div><div class="s up">▲ 23,000 · +4.10%</div></div>
  <div class="tm-cell"><div class="l">고가 / 저가</div><div class="v up">591,000</div><div class="s dn">568,500</div></div>
  <div class="tm-cell"><div class="l">거래량</div><div class="v">3,284,112</div><div class="s">전일 대비 +38.2%</div></div>
</div>
```

```css
.tm-strip { display: grid; grid-template-columns: repeat(3, 1fr); border-bottom: 1px solid var(--tm-hairline); }
.tm-cell { padding: 10px 14px; border-right: 1px solid var(--tm-hairline); }
.tm-cell:last-child { border-right: none; }
.tm-cell .l { font-size: 9px; color: var(--tm-text-mute); letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 5px; font-family: var(--font-display); font-weight: 500; }
.tm-cell .v { font-size: 15px; color: var(--tm-text); font-variant-numeric: tabular-nums; letter-spacing: -0.2px; }
.tm-cell .v.up { color: var(--tm-up); } .tm-cell .v.dn { color: var(--tm-dn); }
.tm-cell .s { font-size: 10px; color: var(--tm-text-mute); margin-top: 3px; font-variant-numeric: tabular-nums; }
.tm-cell .s.up { color: var(--tm-up); } .tm-cell .s.dn { color: var(--tm-dn); }
```

---

## 9. KRX 규정 리스트

```html
<div class="tm-rules">
  <div class="r"><span class="k">1</span><span class="v">지정일로부터 10 매매거래일 경과 후 해제 심사 시작</span><span class="m num">2026-04-22</span></div>
  <div class="r"><span class="k">2</span><span class="v">① ② ③ 세 조건 모두 충족 시 경고 유지. 하나라도 미충족이면 다음 거래일 해제.</span><span class="m">3 중 2</span></div>
  <div class="r"><span class="k">3</span><span class="v">지정 기간 중 신용융자 금지, 위탁증거금 100% 현금</span><span class="m">—</span></div>
  <div class="r"><span class="k">4</span><span class="v">지정 기간 내 요건 재충족 시 투자위험종목으로 상향 지정</span><span class="m">—</span></div>
</div>
```

```css
.tm-rules .r { display: grid; grid-template-columns: 46px 1fr auto; align-items: center; gap: 12px;
               padding: 9px 16px; border-bottom: 1px solid var(--tm-hairline-soft); font-size: 11px; }
.tm-rules .r:last-child { border-bottom: none; }
.tm-rules .r .k { font-family: var(--font-display); font-size: 9px; color: var(--tm-accent); letter-spacing: 1px; font-weight: 600; }
.tm-rules .r .v { color: var(--tm-text-dim); font-family: var(--font-text); line-height: 1.5; }
.tm-rules .r .m { font-family: var(--mono); font-size: 10px; color: var(--tm-text-mute); font-variant-numeric: tabular-nums; }
```

---

## 10. 티커 테이프 (하단 고정 28px)

```html
<div class="tm-tape">
  <div class="tm-tape-label">TABOO · 투자금지</div>
  <div class="tm-tape-track">
    <!-- 아래 배열을 2회 반복 렌더해서 seamless loop -->
    <span class="tm-tape-item">ㅅㅅㅅ 금지</span>
    <span class="tm-tape-item">가즈아 금지</span>
    <!-- ... -->
  </div>
</div>
```

```css
.tm-tape { height: 28px; background: #000; border-top: 1px solid var(--tm-hairline);
           overflow: hidden; position: relative; font-size: 11px; }
.tm-tape-track { display: flex; white-space: nowrap; height: 100%; align-items: center;
                 padding-left: 110px; animation: tm-tape 60s linear infinite; }
.tm-tape:hover .tm-tape-track { animation-play-state: paused; }
@keyframes tm-tape { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.tm-tape-item { padding: 0 22px; color: var(--tm-text-dim); font-weight: 500; }
.tm-tape-item::before { content: "⛩"; color: var(--tm-amber); opacity: 0.55; margin-right: 8px; }
.tm-tape-label { position: absolute; left: 0; top: 0; bottom: 0; z-index: 2;
                 display: flex; align-items: center; padding: 0 14px; background: #000;
                 border-right: 1px solid var(--tm-hairline); color: var(--tm-accent);
                 font-weight: 600; font-family: var(--font-display); font-size: 9px; letter-spacing: 1.5px; }
```

금지어 배열은 기존 `index.html` 에 이미 선언돼 있을 가능성이 높음. **기존 배열을 재사용**하세요. 없으면 목업(`option-a-terminal.jsx`) 하단에서 복사.

---

## 11. 사이드바 (선택)

**권장**: v1 에서는 **제거**. 사용자의 관심종목 저장소가 없고, 공시 피드는 별도 탭(`공시 분석기`)과 중복.

v2 에 추가할 때의 마크업은 목업 `option-a-terminal.jsx` 하단 `.tm-side` 영역 참조.
