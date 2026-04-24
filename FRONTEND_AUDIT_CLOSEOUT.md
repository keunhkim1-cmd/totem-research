# Frontend Audit Closeout

Date: 2026-04-24

This closes the staged senior frontend audit for the single-file SPA that started
as a 105 KB inline `index.html`. The app now uses a small HTML shell plus
cacheable CSS and JS assets.

## Current Asset Shape

| Asset | Raw | gzip | Cache policy |
| --- | ---: | ---: | --- |
| `index.html` | 13.2 KB | 3.9 KB | `max-age=0, must-revalidate` |
| `assets/app.css` | 49.6 KB | 8.6 KB | `max-age=31536000, immutable` |
| `assets/app.js` | 47.0 KB | 12.2 KB | `max-age=31536000, immutable` |
| Total | 109.8 KB | 24.8 KB | mixed shell/assets |

The first load still downloads the whole SPA behavior, but repeat visits should
revalidate only the HTML shell while reusing the versioned CSS and JS from cache.

## Audit Item Status

| # | Area | Status | Notes |
| ---: | --- | --- | --- |
| 1 | Bundle size and loading | Mostly closed | Inline payload is split. Current gzip total is below 32 KB budget. Tab-level code split is deferred because only two real tabs exist and JS gzip is 12.2 KB. |
| 2 | Inline vs external files | Closed | CSS/JS moved to `assets/`; immutable cache headers added. Only JSON-LD and state-driven `display:none` inline markers remain. |
| 3 | Design token duplication | Mostly closed | Apple/default tokens and terminal `--tm-*` are scoped by page state. Patch notes no longer inherits terminal wrapper. |
| 4 | `--blue` vs `--link` | Closed | Added semantic `--action-blue`, `--info-blue`, and link tokens. Old blue names are compatibility aliases. |
| 5 | Accessibility | Improved, not fully certified | Added tablist/tabpanel semantics, keyboard tab switching, live result states, focus styles, hidden panels, labels, and reduced-motion support. Needs real screen-reader pass. |
| 6 | SEO and meta | Closed for baseline | Added description, canonical, OG, Twitter Card, JSON-LD, `robots.txt`, and `sitemap.xml`. |
| 7 | Responsive | Improved | Added mobile breakpoints for search, tables, timeline, chart, and warning sections. Needs device-matrix visual QA before public launch. |
| 8 | State management | Mostly closed | Central `appState` and request IDs reduce global collision and stale async updates. Still plain DOM JS, not a framework store. |
| 9 | Error boundary and API failure UI | Closed for current stack | Common `fetchJson`, state messages, error states, and runtime/unhandled rejection handlers are in place. |
| 10 | Bundler ROI | Closed as decision | Deferred Vite/esbuild. Added `FRONTEND_BUILD_ROI.md` and a frontend size-budget script. |

## Lighthouse Estimate

No Lighthouse run was executed in this local environment. Based on current asset
size, render path, static caching, and browser smoke checks:

| Category | Estimated score | Confidence |
| --- | ---: | --- |
| Performance | 90-96 desktop, 84-92 mobile | Medium |
| Accessibility | 88-94 | Medium |
| Best Practices | 95-100 | Medium-high |
| SEO | 92-98 | Medium-high |

Main performance constraints are API latency after interaction, the single JS
module still being loaded upfront, and no image/OG image asset. Main a11y
uncertainty is screen-reader behavior in the custom tab/search/result flow.

## Verification

Commands run:

```bash
python3 scripts/check_frontend_budget.py
python3 scripts/check_frontend_budget.py --json
python3 scripts/check_frontend_smoke.py
node --check assets/app.js
python3 -m compileall api lib scripts serve.py
python3 -m json.tool vercel.json
python3 -c "import xml.etree.ElementTree as ET; ET.parse('sitemap.xml')"
python3 -m unittest discover -s tests
git diff --check
curl -I http://127.0.0.1:5173/index.html
curl -I 'http://127.0.0.1:5173/assets/app.css?v=20260424-7'
curl -I 'http://127.0.0.1:5173/assets/app.js?v=20260424-7'
curl -I http://127.0.0.1:5173/robots.txt
```

`python3 -m pytest` was attempted but `pytest` is not installed in the current
Python environment. The test suite is `unittest` compatible and passed through
`python3 -m unittest discover -s tests`.

Browser smoke checks passed on `http://127.0.0.1:5173/index.html`:

- search empty state renders `결과 없음 / 종목명을 입력하세요.`
- warning, patch notes, and about tabs update ARIA selection and hidden state
- arrow-key tab navigation cycles warning -> patch notes -> about -> warning
- patch notes lazy content loads
- current in-app browser viewport screenshot showed no obvious overlap in the
  initial warning calculator view
- console warning/error count: 0

The local `lighthouse` CLI is not installed in this environment, so the
Lighthouse values remain estimates rather than measured scores.

## Residual Risks

1. Screen-reader QA is still manual. The semantic structure is better, but NVDA,
   VoiceOver, and keyboard-only traversal should be checked before treating a11y
   as certified.
2. Mobile responsiveness has code-level and browser smoke coverage, not a full
   viewport/device matrix. Test at 360, 390, 768, and desktop widths before a
   public release.
3. The frontend has no automated DOM tests. If the calculator grows again, add a
   small browser smoke test runner before introducing a full bundler.
4. Asset versioning is manual. If version misses happen, that is the first strong
   signal to add an esbuild manifest step.
5. SEO lacks a real social preview image. Baseline metadata is present, but a
   dedicated OG image would improve share quality.

## Next Priority

No urgent frontend blocker remains from the original audit. The next valuable
step is a lightweight visual/a11y QA pass across fixed viewport widths, followed
by either screenshot baselines or a minimal browser smoke script if this UI will
continue changing.
