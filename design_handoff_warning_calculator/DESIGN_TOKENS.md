# DESIGN TOKENS

> 모든 값은 **기존 `shamanism-research/index.html` 의 `:root` 에 merge** 하는 형태로 주입합니다. 기존 토큰(`--bg`, `--text`, `--blue` 등)은 **유지**하고, `--tm-*` 네임스페이스로 신규 값만 추가한 뒤 투자경고 계산기 섹션에서만 참조하세요.

---

## 1. 폰트 — 변경 없음

기존 변수를 **그대로 사용**합니다. 이 시안을 위해 새로 추가할 폰트 없음.

```css
/* 기존 index.html 에 이미 있음 — 유지 */
--font-display: 'SF Pro Display', 'SF Pro Icons', 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
--font-text:    'SF Pro Text', 'SF Pro Icons', 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif;
--mono:         'SF Mono', 'Menlo', 'Consolas', monospace;
```

목업(`option-a-terminal.jsx`)의 `'IBM Plex Mono'` / `'IBM Plex Sans Condensed'` 참조는 **모두 무시**하고 위 세 변수로 치환합니다. 매핑:

| 목업 참조 | 실제 사용 변수 |
|---|---|
| `'IBM Plex Mono', 'Menlo', monospace` | `var(--mono)` |
| `'IBM Plex Sans', 'Pretendard', sans-serif` | `var(--font-text)` |
| `'IBM Plex Sans Condensed', 'IBM Plex Sans', sans-serif` | `var(--font-display)` |
| `'IBM Plex Sans', sans-serif` (라벨·탭) | `var(--font-display)` + `text-transform: uppercase` + `letter-spacing: 0.8~1.5px` |

SF Pro는 이미 Condensed 계열이 없으므로, 목업의 `Condensed` 자리는 **`var(--font-display)` + `letter-spacing: 1.5px` + `uppercase`** 조합으로 흉내냅니다. 실제로 렌더링해보면 터미널의 density 느낌이 충분히 납니다.

---

## 2. 컬러 토큰 — 신규 추가

기존 `:root` 블록 하단에 이어서 추가합니다:

```css
:root {
  /* ─── 기존 유지 (건드리지 말 것) ─── */
  --bg: #000000;
  --surface: #272729;
  --text: #ffffff;
  --blue: #0071e3;
  /* ... */

  /* ─── 신규: 터미널 시안 전용 (--tm-* 네임스페이스) ─── */
  /* Base surfaces */
  --tm-bg:             #0A0A0A;
  --tm-panel:          #0F0F10;
  --tm-elev:           #141416;
  --tm-hairline:       #1E1E22;
  --tm-hairline-soft:  #16161A;

  /* Text 3-scale */
  --tm-text:      #E8E8E8;
  --tm-text-dim:  #9A9A9A;
  --tm-text-mute: #5E5E63;

  /* Accent (Mono · Night — 섹션 좌측 바, 포커스, 로고) */
  --tm-accent:      #FFFFFF;
  --tm-accent-soft: rgba(255, 255, 255, 0.10);

  /* Price signal (한국식 상승=빨강, 하락=파랑) */
  --tm-up:      #F04452;   --tm-up-soft:   rgba(240, 68, 82, 0.10);
  --tm-dn:      #3485FF;   --tm-dn-soft:   rgba(52, 133, 255, 0.10);

  /* Verdict / info */
  --tm-ok:      #4ADE80;   --tm-ok-soft:   rgba(74, 222, 128, 0.10);
  --tm-toss:    #3182F6;   --tm-toss-soft: rgba(49, 130, 246, 0.10);

  /* 티커 테이프·앰버 하이라이트 (원본 샤머니즘 모티브와의 브리지) */
  --tm-amber:      #F5A623;
  --tm-amber-soft: rgba(245, 166, 35, 0.12);
}
```

### 기존 값과의 매핑

| 기존 `index.html` 변수 | 투자경고 계산기에서 | 비고 |
|---|---|---|
| `--bg #000000` | **그대로** | 페이지 최외곽 배경 |
| `--surface #272729` | `--tm-panel` 로 대체 | 사이드 패널·헤더 배경 |
| `--border #38383a` | `--tm-hairline` 로 대체 | 섹션 구분선 |
| `--text #ffffff` | `--tm-text #E8E8E8` | **약간 더 낮은 명도** (장시간 시청용) |
| `--text-secondary` | `--tm-text-dim` | |
| `--text-muted` | `--tm-text-mute` | |
| `--blue #0071e3` | **투자경고 계산기에서는 쓰지 않음** | 다른 탭에서는 유지 |
| `--blue-bright #2997ff` | `--tm-toss #3182F6` 로 대체 | D-day · 정보 |
| `--up #ff3b30` | `--tm-up #F04452` 로 대체 | 약간 더 어두운 빨강 |
| `--down #007aff` | `--tm-dn #3485FF` 로 대체 | |

### 기존 탭과의 공존

투자경고 계산기 섹션에만 스코프된 클래스(`.warning-terminal` 또는 `#page-warning .warning-terminal`)를 wrapper로 두고, 그 안에서만 `--tm-*` 를 참조하도록 격리하세요. 다른 탭(About / 재무현황 / 공시 / 패치노트)은 기존 Apple dark 톤을 그대로 유지합니다.

```css
#page-warning .warning-terminal {
  background: var(--tm-bg);
  color: var(--tm-text);
  /* 이하 모든 컴포넌트 */
}
```

---

## 3. 크기 스케일

```css
/* Space */
--tm-space-1: 4px;
--tm-space-2: 6px;
--tm-space-3: 8px;
--tm-space-4: 10px;
--tm-space-5: 14px;
--tm-space-6: 16px;
--tm-space-7: 24px;

/* Typography — SF Pro 기준 */
--tm-fs-micro:   9px;   /* 라벨·출처 */
--tm-fs-xs:     10px;   /* 탭·메타 */
--tm-fs-sm:     11px;   /* 본문·테이블 */
--tm-fs-md:     12px;   /* Verdict body */
--tm-fs-lg:     15px;   /* Verdict head · 프라이스 셀 값 */
--tm-fs-xl:     22px;   /* 종가 대형 숫자 */
--tm-fs-2xl:    26px;   /* 티커 대형 (에코프로 086520) */

/* Weight */
--tm-fw-reg:  400;
--tm-fw-med:  500;
--tm-fw-semi: 600;
--tm-fw-bold: 700;

/* Letter-spacing */
--tm-ls-caps:   1.5px;   /* 섹션 헤더 uppercase */
--tm-ls-label:  0.8px;   /* 라벨·출처 uppercase */
--tm-ls-tight: -0.3px;   /* 대형 숫자 */

/* Border radius */
--tm-radius: 0;          /* 기본 0 (터미널 직각) */
--tm-radius-pill: 50%;   /* 조건 테이블의 번호 배지만 */
```

---

## 4. 공통 스타일 헬퍼

```css
.warning-terminal { font-family: var(--font-text); font-size: var(--tm-fs-sm); line-height: 1.45; -webkit-font-smoothing: antialiased; }
.warning-terminal .num { font-variant-numeric: tabular-nums; font-family: var(--mono); }
.warning-terminal .caps { font-family: var(--font-display); text-transform: uppercase; letter-spacing: var(--tm-ls-caps); }
.warning-terminal .label { font-family: var(--font-display); text-transform: uppercase; letter-spacing: var(--tm-ls-label); font-size: var(--tm-fs-micro); color: var(--tm-text-mute); font-weight: var(--tm-fw-med); }
.warning-terminal ::-webkit-scrollbar { width: 6px; height: 6px; }
.warning-terminal ::-webkit-scrollbar-thumb { background: #2A2A2E; }
```

세 가지 유틸(`.num` / `.caps` / `.label`)을 외우면 대부분의 마크업이 해결됩니다.

---

## 5. 색 사용 규칙 요약표

| 토큰 | 쓰이는 곳 (유일) |
|---|---|
| `--tm-accent #FFFFFF` | 섹션 헤더 좌측 2px 바 · 네비 active 밑줄 · 로고 |
| `--tm-up #F04452` | 상승 가격 · 조건 `유지` 플래그 · 상승 ▲ · 현재가 원 마커 |
| `--tm-dn #3485FF` | 하락 가격 · 하락 ▼ |
| `--tm-ok #4ADE80` | 조건 `이탈` 플래그 · Verdict "다음 거래일 해제" · 타임라인 `past` 셀 · 15일 최고 선 |
| `--tm-toss #3182F6` | D-day 칩 · 타임라인 `release` 셀 · 관심종목 D-day 텍스트 |
| `--tm-amber #F5A623` | **사용 지양**. 원본 index의 하이라이트와의 브리지가 필요할 때만. 터미널 시안 자체는 Mono Night. |

**금지**: 세 신호 색을 배경 그라디언트나 대형 블록으로 쓰는 것. 반드시 **soft(10~12% alpha) 배경 + 풀 색 텍스트 + 1px 풀 색 보더** 트라이어드만.

예:

```css
.tm-flag-hold {
  background: var(--tm-up-soft);
  color: var(--tm-up);
  border: 1px solid var(--tm-up);
}
```
