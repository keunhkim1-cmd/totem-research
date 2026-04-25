---
description: DESIGN.md 타이포그래피 규칙 위반 검사 — 사이즈·LS·LH·weight·정렬·패밀리 위반을 표로 보고만 (수정 X)
---

# Audit DESIGN.md 컴플라이언스

`DESIGN.md` 의 타이포그래피 규칙에 어긋나는 항목을 찾아 **표로 보고**하는 작업입니다.

**중요**:
- 코드를 **수정하지 마세요**. 사용자가 결과를 본 뒤 별도로 지시합니다.
- 출력은 표 + 1~2줄 요약만. 장문 해설 X.
- DESIGN.md 를 먼저 Read 해서 현재 규칙을 확인한 뒤 시작.

---

## 입력

검사 범위: **$ARGUMENTS**

비어있으면 → 기본값 `assets/app.css` 전체.

지원하는 인자 예시:
- `assets/app.css` → 그 파일만
- `§6` 또는 `정렬` → 해당 섹션 위반만
- `git diff` 또는 `최근 변경` → `git diff HEAD` 로 나오는 변경 부분만
- `index.html` → HTML 의 인라인 style·class 사용 검토

---

## 검사 항목 (DESIGN.md 매핑)

1. **§1 사이즈** — `font-size: NNpx` 하드코딩이 있는지. 5단계 스케일(28/21/14/12/10) 외 값(`11/13/15/16/17/18/22/24/32/40px` 등) 발견시 위반
2. **§2 패밀리** — `text-transform: uppercase` 인데 `--font-display` 안 씀 / 한글 본문에 display / 숫자 컬럼에 비례폭 폰트
3. **§3 letter-spacing** — 표 외 값(`-0.224`, `-0.374`, `0.231`, `0.196`, `1px`, `1.2px`, `0.5px` 등) 발견시 위반. 허용값: `0`, `-0.12`, `-0.3`, `0.3`, `0.8`, `1.5`
4. **§4 weight** — 허용값(400/500/600) 외 발견시 위반 (특히 300, 700, 800)
5. **§5 line-height** — `1` 또는 `1.45` 외 값 발견시 위반
6. **§6 정렬** — 본문/헤딩/카피/캡션/footnote 의 `text-align: center` 발견시 위반 (state-message / price-loading / price-error 등 빈상태·로딩·에러 컴포넌트는 예외)

---

## 출력 형식

위반 발견시:

```
| 파일:라인 | 섹션 | 현재 | 위반 사유 | 권장 |
|---|---|---|---|---|
| assets/app.css:240 | §6 정렬 | text-align: center | 본문 p는 좌측 정렬이어야 함 | text-align: left |
```

마지막에 1줄 요약: `총 N건 (§1: a · §3: b · §4: c · §5: d · §6: e)`

위반 0건이면 표 없이:

```
✓ DESIGN.md 컴플라이언스 OK — 검사 범위: <파일/섹션>
```

---

## 검사 방법 힌트

- `grep -nE "font-size: *[0-9]+px"` 으로 하드코딩 사이즈
- `grep -hoE "letter-spacing: [^;]+" | sort -u` 로 LS 분포 → 표 외 값
- `grep -hoE "line-height: [^;]+" | sort -u` 로 LH 분포
- `grep -hoE "font-weight: *[0-9]+" | sort -u` 로 weight 분포
- `grep -nE "text-align: *center"` 후 각 라인 컨텍스트에서 본문/헤딩/카피인지 판단 (state/loading/error 제외)

위반 라인을 찾았다면 그 컨텍스트(부모 selector)를 함께 표시하면 더 명확합니다.
