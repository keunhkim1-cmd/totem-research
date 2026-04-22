// Terminal Mockup — Bloomberg base × TradingView chart × Toss warmth
// Accepts `theme` prop to switch primary accent: 'mint' | 'violet' | 'coral'
// Mint   — calm, analytical (KakaoBank-ish soft green)
// Violet — modern, premium (Linear/Raycast)
// Coral  — warm, Toss-adjacent (tech Korean fintech)

function TerminalMockup({ theme = 'mint' }) {
  const M = window.MOCK;
  const THEMES = {
    mint:   { p:'#35D1A1', pDark:'#0F3D30', pGrad:'rgba(53,209,161,0.22)', name:'MINT'   },
    violet: { p:'#A78BFA', pDark:'#2E1E5C', pGrad:'rgba(167,139,250,0.22)', name:'VIOLET' },
    coral:  { p:'#FF7A59', pDark:'#4A1D12', pGrad:'rgba(255,122,89,0.22)',  name:'CORAL'  },
    mono:     { p:'#FFFFFF', pDark:'#1A1A1A', pGrad:'rgba(255,255,255,0.18)', name:'MONO'    },
    monoWarm: { p:'#EDE6D8', pDark:'#2A241C', pGrad:'rgba(237,230,216,0.18)', name:'MONO·WARM' },
    monoDay:  { p:'#0A0A0A', pDark:'#D0CCC2', pGrad:'rgba(10,10,10,0.12)',    name:'MONO·DAY' },
  };
  const T = THEMES[theme] || THEMES.mint;
  const rootCls = `tm tm-theme-${theme}`;
  const css = `
    /* ── Base (Bloomberg) ──────────────────────────────────────────── */
    .tm { --bg:#0A0A0A; --panel:#0F0F10; --elev:#141416; --hairline:#1E1E22; --hairline-soft:#16161A;
          --text:#E8E8E8; --text-dim:#9A9A9A; --text-mute:#5E5E63;
          --amber:#F5A623; --amber-soft:rgba(245,166,35,0.12);
          --up:#F04452;    --up-soft:rgba(240,68,82,0.10);
          --dn:#3485FF;    --dn-soft:rgba(52,133,255,0.10);
          --ok:#4ADE80;    --ok-soft:rgba(74,222,128,0.10);
          --toss:#3182F6;  --toss-soft:rgba(49,130,246,0.10);
          font-family:'IBM Plex Mono','Menlo',monospace; background:var(--bg); color:var(--text);
          font-size:11px; line-height:1.45; height:100%; overflow:hidden; display:flex;
          flex-direction:column; -webkit-font-smoothing:antialiased; }
    .tm-theme-mint   { --amber:#35D1A1; --amber-soft:rgba(53,209,161,0.14); }
    .tm-theme-violet { --amber:#A78BFA; --amber-soft:rgba(167,139,250,0.14); }
    .tm-theme-coral  { --amber:#FF7A59; --amber-soft:rgba(255,122,89,0.14); }

    /* ── Monochrome variants (Zara-ish restraint) ──────────────────── */
    /* Accent becomes neutral ink; up/down/ok/toss collapse to grayscale.
       Red remains only as a single thin alert token for ▲/▼ price moves. */
    .tm-theme-mono { --bg:#0A0A0A; --panel:#0F0F10; --elev:#141416;
                     --hairline:#242424; --hairline-soft:#1A1A1A;
                     --text:#F2F2F2; --text-dim:#9A9A9A; --text-mute:#5E5E5E;
                     --amber:#FFFFFF; --amber-soft:rgba(255,255,255,0.10);
                     --up:#E8E8E8;    --up-soft:rgba(255,255,255,0.06);
                     --dn:#8A8A8A;    --dn-soft:rgba(138,138,138,0.08);
                     --ok:#F2F2F2;    --ok-soft:rgba(255,255,255,0.06);
                     --toss:#BDBDBD;  --toss-soft:rgba(189,189,189,0.08); }
    .tm-theme-monoWarm { --bg:#0D0B08; --panel:#12100C; --elev:#17140F;
                         --hairline:#2A251C; --hairline-soft:#1C1812;
                         --text:#EDE6D8; --text-dim:#A39A87; --text-mute:#5F584C;
                         --amber:#EDE6D8; --amber-soft:rgba(237,230,216,0.10);
                         --up:#EDE6D8;    --up-soft:rgba(237,230,216,0.06);
                         --dn:#8A8272;    --dn-soft:rgba(138,130,114,0.08);
                         --ok:#EDE6D8;    --ok-soft:rgba(237,230,216,0.06);
                         --toss:#B8AE98;  --toss-soft:rgba(184,174,152,0.08); }
    .tm-theme-monoDay  { --bg:#F3EFE7; --panel:#EDE8DE; --elev:#E6E0D3;
                         --hairline:#CFC8B9; --hairline-soft:#DCD6C8;
                         --text:#151311; --text-dim:#5F584C; --text-mute:#8A8272;
                         --amber:#151311; --amber-soft:rgba(21,19,17,0.08);
                         --up:#151311;    --up-soft:rgba(21,19,17,0.06);
                         --dn:#5F584C;    --dn-soft:rgba(95,88,76,0.08);
                         --ok:#151311;    --ok-soft:rgba(21,19,17,0.06);
                         --toss:#5F584C;  --toss-soft:rgba(95,88,76,0.08); }
    .tm-theme-monoDay ::-webkit-scrollbar-thumb { background:#B8B0A0; }
    .tm-theme-monoDay .tm-top,
    .tm-theme-monoDay .tm-rail,
    .tm-theme-monoDay .tm-bottom { background:#E6E0D3; }
    .tm-theme-monoDay .tm-tl-cell.today { color:#F3EFE7; }
    .tm, .tm * { box-sizing:border-box; }
    .tm ::-webkit-scrollbar { width:6px; height:6px; }
    .tm ::-webkit-scrollbar-thumb { background:#2A2A2E; }
    .tm button { font-family:inherit; cursor:pointer; border:none; background:transparent; color:inherit; }
    .tm .sans { font-family:'IBM Plex Sans','Pretendard','Inter',system-ui,sans-serif; }
    .tm .cond { font-family:'IBM Plex Sans Condensed','IBM Plex Sans',sans-serif; }
    .tm .num  { font-variant-numeric:tabular-nums; }

    /* ── Top app bar ───────────────────────────────────────────────── */
    .tm-top { display:flex; align-items:center; height:30px; background:#000; border-bottom:1px solid var(--hairline);
              padding:0 12px; gap:16px; font-size:10px; flex-shrink:0; }
    .tm-logo { color:var(--amber); font-weight:600; letter-spacing:0.8px; font-family:'IBM Plex Sans',sans-serif; }
    .tm-nav { display:flex; height:100%; align-items:stretch; }
    .tm-nav button { color:var(--text-mute); padding:0 14px; font-size:10px; letter-spacing:0.8px;
                     text-transform:uppercase; border-bottom:2px solid transparent; font-family:'IBM Plex Sans',sans-serif; }
    .tm-nav button.active { color:var(--amber); border-bottom-color:var(--amber); }
    .tm-status { margin-left:auto; color:var(--text-mute); display:flex; gap:16px; align-items:center; font-family:'IBM Plex Sans',sans-serif; }
    .tm-status .live::before { content:"●"; color:var(--ok); margin-right:5px; animation:pulse 1.6s infinite; }
    @keyframes pulse { 50% { opacity:0.3; } }

    /* ── Body ──────────────────────────────────────────────────────── */
    .tm-body { display:flex; flex:1; min-height:0; }
    .tm-mid { flex:1; display:flex; min-width:0; }
    .tm-main { flex:1; min-width:0; overflow-y:auto; }
    .tm-side { width:320px; border-left:1px solid var(--hairline); background:var(--panel);
               overflow-y:auto; flex-shrink:0; }

    /* ── Symbol header ─────────────────────────────────────────────── */
    .tm-sym { display:flex; align-items:center; gap:14px; padding:14px 16px;
              border-bottom:1px solid var(--hairline); }
    .tm-sym .ticker { font-family:'IBM Plex Sans Condensed',sans-serif; font-size:26px; font-weight:600;
                      color:var(--amber); letter-spacing:0.5px; line-height:1; }
    .tm-sym .name-block { display:flex; flex-direction:column; gap:3px; }
    .tm-sym .name { font-size:13px; color:var(--text); font-family:'IBM Plex Sans',sans-serif; }
    .tm-sym .meta { font-size:10px; color:var(--text-mute); letter-spacing:0.3px; font-family:'IBM Plex Sans',sans-serif; }
    .tm-sym .chips { margin-left:auto; display:flex; gap:6px; align-items:center; }
    .tm-sym .chip { font-size:9px; padding:3px 8px; letter-spacing:1px;
                    font-family:'IBM Plex Sans',sans-serif; font-weight:600; }
    .tm-sym .chip.warn { background:var(--amber-soft); color:var(--amber); border:1px solid var(--amber); }
    .tm-sym .chip.dday { background:var(--toss-soft); color:var(--toss); border:1px solid var(--toss); }
    .tm-sym .px { display:flex; flex-direction:column; align-items:flex-end; gap:2px; margin-left:24px; }
    .tm-sym .px .val { font-size:22px; color:var(--up); font-weight:500; letter-spacing:-0.3px;
                       font-variant-numeric:tabular-nums; line-height:1; }
    .tm-sym .px .chg { font-size:11px; color:var(--up); font-variant-numeric:tabular-nums;
                       font-family:'IBM Plex Sans',sans-serif; font-weight:500; }

    /* ── Price strip (3 cells — 경고 계산에 쓰이는 것만) ─────────── */
    .tm-strip { display:grid; grid-template-columns:repeat(3,1fr); border-bottom:1px solid var(--hairline); }
    .tm-cell { padding:10px 14px; border-right:1px solid var(--hairline); }
    .tm-cell:last-child { border-right:none; }
    .tm-cell .l { font-size:9px; color:var(--text-mute); letter-spacing:0.8px; text-transform:uppercase;
                  margin-bottom:5px; font-family:'IBM Plex Sans',sans-serif; font-weight:500; }
    .tm-cell .v { font-size:15px; color:var(--text); font-variant-numeric:tabular-nums; letter-spacing:-0.2px; }
    .tm-cell .v.up    { color:var(--up); }
    .tm-cell .v.dn    { color:var(--dn); }
    .tm-cell .v.amber { color:var(--amber); }
    .tm-cell .s { font-size:10px; color:var(--text-mute); margin-top:3px; font-variant-numeric:tabular-nums; }
    .tm-cell .s.up { color:var(--up); } .tm-cell .s.dn { color:var(--dn); }

    /* ── Section wrapper ───────────────────────────────────────────── */
    .tm-sec { border-bottom:1px solid var(--hairline); }
    .tm-sec-head { display:flex; align-items:center; gap:10px; padding:11px 16px 9px;
                   font-family:'IBM Plex Sans Condensed',sans-serif; font-size:11px;
                   letter-spacing:1.5px; text-transform:uppercase; }
    .tm-sec-head .t  { color:var(--text); font-weight:500; border-left:2px solid var(--amber); padding-left:10px; }
    .tm-sec-head .src { margin-left:auto; color:var(--text-mute); font-size:9px;
                        font-family:'IBM Plex Mono',monospace; letter-spacing:0.3px; }

    /* ── Chart (TradingView) ───────────────────────────────────────── */
    .tm-chart-wrap { padding:8px 16px 16px; }
    .tm-chart-tabs { display:flex; gap:0; margin-bottom:10px; font-family:'IBM Plex Sans',sans-serif; }
    .tm-chart-tabs button { font-size:10px; letter-spacing:0.5px; padding:5px 11px; color:var(--text-mute);
                            border:1px solid var(--hairline); border-right:none; font-weight:500; }
    .tm-chart-tabs button:last-child { border-right:1px solid var(--hairline); }
    .tm-chart-tabs button.active { color:var(--amber); background:var(--amber-soft); border-color:var(--amber); }
    .tm-chart-tabs .flex { flex:1; }
    .tm-chart-tabs .legend { display:flex; gap:14px; align-items:center; font-size:10px; color:var(--text-mute); }
    .tm-chart-tabs .legend .sw { display:inline-block; width:16px; height:2px; vertical-align:middle; margin-right:5px; }
    .tm-chart { position:relative; height:160px; background:linear-gradient(180deg, rgba(245,166,35,0.03), transparent 70%);
                border:1px solid var(--hairline); }
    .tm-chart svg { display:block; width:100%; height:100%; }
    .tm-chart .annot { position:absolute; font-family:'IBM Plex Sans',sans-serif; font-size:9px;
                       letter-spacing:0.5px; padding:2px 5px; background:var(--bg); }
    .tm-chart .annot.a1 { right:8px; top:6px; color:var(--amber); border:1px solid var(--amber); }
    .tm-chart .annot.a2 { right:8px; top:30px; color:var(--up); border:1px solid var(--up); }
    .tm-chart .annot.a3 { right:8px; bottom:36px; color:var(--ok); border:1px solid var(--ok); }
    .tm-chart .crosshair { position:absolute; top:8px; left:10px; font-size:10px; color:var(--text-dim);
                           font-family:'IBM Plex Sans',sans-serif; letter-spacing:0.3px; }
    .tm-chart .crosshair .k { color:var(--text-mute); }

    /* ── Dense conditions table ───────────────────────────────────── */
    .tm-tbl { width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric:tabular-nums; }
    .tm-tbl th { font-family:'IBM Plex Sans',sans-serif; font-size:9px; letter-spacing:0.8px; text-transform:uppercase;
                 color:var(--text-mute); font-weight:500; text-align:right; padding:9px 14px;
                 border-bottom:1px solid var(--hairline); background:var(--panel); }
    .tm-tbl th:first-child { text-align:left; }
    .tm-tbl td { padding:11px 14px; text-align:right; border-bottom:1px solid var(--hairline-soft);
                 color:var(--text); }
    .tm-tbl td:first-child { text-align:left; }
    .tm-tbl tr:last-child td { border-bottom:none; }
    .tm-tbl .lbl-col { display:flex; align-items:center; gap:10px; }
    .tm-tbl .lbl-col .badge { width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center;
                              font-size:10px; font-weight:700; font-family:'IBM Plex Sans',sans-serif;
                              background:var(--hairline); color:var(--text-dim); flex-shrink:0; }
    .tm-tbl tr.hold .lbl-col .badge { background:var(--up-soft); color:var(--up); border:1px solid rgba(240,68,82,0.4); }
    .tm-tbl tr.clear .lbl-col .badge { background:var(--ok-soft); color:var(--ok); border:1px solid rgba(74,222,128,0.4); }
    .tm-tbl .lbl-col .txt .n { color:var(--text); font-family:'IBM Plex Sans',sans-serif; font-size:12px; font-weight:500; }
    .tm-tbl .lbl-col .txt .d { color:var(--text-mute); font-size:10px; margin-top:2px; font-family:'IBM Plex Mono',monospace; }
    .tm-tbl .up { color:var(--up); } .tm-tbl .dn { color:var(--dn); } .tm-tbl .ok { color:var(--ok); } .tm-tbl .amber { color:var(--amber); }
    .tm-tbl .flag { display:inline-block; padding:2px 8px; font-size:9px; letter-spacing:1.2px; font-weight:600;
                    font-family:'IBM Plex Sans',sans-serif; }
    .tm-tbl .flag.hold { background:var(--up-soft); color:var(--up); border:1px solid var(--up); }
    .tm-tbl .flag.clear { background:var(--ok-soft); color:var(--ok); border:1px solid var(--ok); }

    /* ── Verdict (Toss-style warm copy inside terminal shell) ─────── */
    .tm-verdict { display:flex; align-items:center; gap:14px; padding:16px 16px;
                  background:linear-gradient(90deg, var(--ok-soft), transparent 70%);
                  border-left:2px solid var(--ok); }
    .tm-verdict .ico { width:36px; height:36px; border-radius:50%; background:var(--ok-soft);
                       border:1px solid var(--ok); color:var(--ok); display:flex; align-items:center; justify-content:center;
                       font-size:16px; flex-shrink:0; }
    .tm-verdict .body { flex:1; font-family:'IBM Plex Sans','Pretendard',sans-serif; }
    .tm-verdict .head { display:flex; align-items:center; gap:8px; margin-bottom:3px; }
    .tm-verdict .tag { font-size:9px; letter-spacing:1.2px; color:var(--ok); padding:2px 7px;
                       background:var(--ok-soft); font-weight:600; border:1px solid var(--ok); }
    .tm-verdict .h { font-size:15px; color:var(--text); font-weight:600; letter-spacing:-0.2px; }
    .tm-verdict .b { font-size:12px; color:var(--text-dim); line-height:1.55; }
    .tm-verdict .side { border-left:1px solid var(--hairline); padding-left:18px; margin-left:6px;
                        text-align:right; font-family:'IBM Plex Mono',monospace; }
    .tm-verdict .side .d { font-size:18px; color:var(--ok); font-variant-numeric:tabular-nums; letter-spacing:-0.3px; }
    .tm-verdict .side .l { font-size:9px; color:var(--text-mute); letter-spacing:1px; margin-top:3px;
                           font-family:'IBM Plex Sans',sans-serif; text-transform:uppercase; }

    /* ── Timeline ─────────────────────────────────────────────────── */
    .tm-tl { padding:10px 16px 16px; }
    .tm-tl-track { display:grid; grid-template-columns:repeat(11,1fr); gap:2px; margin:8px 0; }
    .tm-tl-cell { height:24px; background:#16161A; border:1px solid var(--hairline); display:flex;
                  align-items:center; justify-content:center; font-size:9px; color:var(--text-mute);
                  font-family:'IBM Plex Sans',sans-serif; letter-spacing:0.3px; position:relative; }
    .tm-tl-cell.past { background:var(--ok-soft); color:var(--ok); border-color:rgba(74,222,128,0.3); }
    .tm-tl-cell.today { background:var(--amber); color:#000; border-color:var(--amber); font-weight:700; }
    .tm-tl-cell.release { background:var(--toss-soft); color:var(--toss); border-color:var(--toss); }
    .tm-tl-foot { display:flex; justify-content:space-between; font-size:9px; color:var(--text-mute);
                  font-family:'IBM Plex Sans',sans-serif; letter-spacing:0.3px; margin-top:4px; }
    .tm-tl-foot b { color:var(--text); font-family:'IBM Plex Mono',monospace; font-weight:500;
                    font-variant-numeric:tabular-nums; }

    /* ── Side: watchlist + disclosures ─────────────────────────────── */
    .tm-wl { font-size:11px; font-variant-numeric:tabular-nums; }
    .tm-wl-row { display:grid; grid-template-columns:1.7fr 1fr 0.7fr; padding:9px 14px;
                 border-bottom:1px solid var(--hairline-soft); align-items:center; gap:8px; }
    .tm-wl-row:hover { background:var(--hairline-soft); }
    .tm-wl-row .n { color:var(--text); font-family:'IBM Plex Sans',sans-serif; font-size:11px; font-weight:500; }
    .tm-wl-row .c { color:var(--text-mute); font-size:9px; display:block; margin-top:1px; font-family:'IBM Plex Mono',monospace; }
    .tm-wl-row .chg { text-align:right; }
    .tm-wl-row .chg .p { color:var(--text-dim); font-size:11px; }
    .tm-wl-row .chg .pc { font-size:10px; font-weight:500; }
    .tm-wl-row .chg .pc.up { color:var(--up); } .tm-wl-row .chg .pc.dn { color:var(--dn); }
    .tm-wl-row .lv { justify-self:end; font-size:8px; letter-spacing:1px; padding:3px 7px;
                     font-family:'IBM Plex Sans',sans-serif; font-weight:600; }
    .tm-wl-row .lv.w { background:var(--amber-soft); color:var(--amber); border:1px solid var(--amber); }
    .tm-wl-row .lv.c { background:var(--hairline); color:var(--text-dim); }
    .tm-wl-row .lv.n { color:var(--text-mute); }
    .tm-wl-row .dday { font-family:'IBM Plex Sans',sans-serif; font-size:9px; color:var(--toss);
                       margin-top:2px; font-weight:600; letter-spacing:0.5px; }

    .tm-disc-row { padding:10px 14px; border-bottom:1px solid var(--hairline-soft); }
    .tm-disc-row:hover { background:var(--hairline-soft); }
    .tm-disc-row .mt { display:flex; gap:10px; font-size:9px; }
    .tm-disc-row .mt .d { color:var(--text-mute); letter-spacing:0.3px; }
    .tm-disc-row .mt .ty { color:var(--amber); letter-spacing:0.5px; font-family:'IBM Plex Sans',sans-serif; font-weight:500; }
    .tm-disc-row .ti { font-size:11px; color:var(--text); margin-top:4px;
                       font-family:'IBM Plex Sans','Pretendard',sans-serif; line-height:1.45; }

    /* ── Ticker tape — 투자 금지 미신 (샤머니즘 리서치 원본) ───────── */
    .tm-tape { height:28px; background:#000; border-top:1px solid var(--hairline);
               overflow:hidden; position:relative; flex-shrink:0;
               font-family:'IBM Plex Sans','Pretendard',sans-serif; font-size:11px; }
    .tm-theme-monoDay .tm-tape { background:#E6E0D3; }
    .tm-tape-track { display:flex; gap:0; white-space:nowrap; height:100%; align-items:center;
                     animation:tm-tape-scroll 60s linear infinite; will-change:transform; }
    .tm-tape:hover .tm-tape-track { animation-play-state:paused; }
    @keyframes tm-tape-scroll { from { transform:translateX(0); } to { transform:translateX(-50%); } }
    .tm-tape-item { display:inline-flex; align-items:center; padding:0 22px;
                    color:var(--text-dim); letter-spacing:-0.1px; font-weight:500; }
    .tm-tape-item::before { content:"⛩"; color:var(--amber); opacity:0.55; margin-right:8px; font-size:11px; }
    .tm-tape-label { position:absolute; left:0; top:0; bottom:0; z-index:2; display:flex;
                     align-items:center; padding:0 14px; background:#000;
                     border-right:1px solid var(--hairline); color:var(--amber); font-weight:600;
                     font-family:'IBM Plex Sans',sans-serif; font-size:9px; letter-spacing:1.5px; }
    .tm-theme-monoDay .tm-tape-label { background:#E6E0D3; }

    /* ── Rules mini-table ──────────────────────────────────────────── */
    .tm-rules { padding:4px 0; }
    .tm-rules .r { display:grid; grid-template-columns:46px 1fr auto; align-items:center; gap:12px;
                   padding:9px 16px; border-bottom:1px solid var(--hairline-soft); font-size:11px; }
    .tm-rules .r:last-child { border-bottom:none; }
    .tm-rules .r .k { font-family:'IBM Plex Sans',sans-serif; font-size:9px; color:var(--amber);
                      letter-spacing:1px; font-weight:600; }
    .tm-rules .r .v { color:var(--text-dim); font-family:'IBM Plex Sans','Pretendard',sans-serif; line-height:1.5; }
    .tm-rules .r .m { font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--text-mute); font-variant-numeric:tabular-nums; }
  `;

  const fmt = n => n.toLocaleString('ko-KR');
  const pct = (a,b) => (((a-b)/b) * 100).toFixed(2);

  // Inline SVG chart — 30-day synthetic close series ending at M.tClose.
  // Horizontal threshold lines: 15-day max (③), cond1 threshold, cond2 threshold.
  const chart = React.useMemo(() => {
    // Hand-tuned series: slow grind → acceleration → last 2 days pull back a touch.
    const prices = [
      328000,332500,341000,338000,346000,355000,362500,371000,368500,398000, // T-20..T-10
      405000,412000,421500,436000,458000,481000,502000,528000,549000,561000, // T-9..T0-ish
      568000,572000,575000,579000,585500,591000,589000,586500,584500,584000, // recent 10
    ];
    const W = 1100, H = 160, P = 10;
    const min = Math.min(...prices) * 0.96;
    const max = Math.max(...prices) * 1.02;
    const xs = i => P + (i/(prices.length-1)) * (W - 2*P);
    const ys = p => P + (1 - (p - min)/(max - min)) * (H - 2*P);
    const pathD = prices.map((p,i) => `${i===0?'M':'L'}${xs(i).toFixed(1)},${ys(p).toFixed(1)}`).join(' ');
    const areaD = pathD + ` L${xs(prices.length-1).toFixed(1)},${H-P} L${xs(0).toFixed(1)},${H-P} Z`;

    const lines = [
      { v: M.thresh1, color: T.p, label:'① 임계 577,100' },
      { v: M.thresh2, color:'#F04452', label:'② 임계 574,000' },
      { v: M.max15,   color:'#4ADE80', label:'③ 15일 최고 591,000' },
    ];
    return { W, H, P, prices, pathD, areaD, lines, xs, ys, min, max };
  }, [M]);

  return (
    <React.Fragment>
      <style>{css}</style>
      <div className={rootCls}>
        {/* Top app bar */}
        <div className="tm-top">
          <span className="tm-logo">샤머니즘 리서치 <span style={{opacity:0.4,marginLeft:6}}>[{T.name}]</span></span>
          <div className="tm-nav">
            <button>재무현황</button>
            <button className="active">경고계산기</button>
            <button>공시분석기</button>
            <button>재무모델</button>
            <button>패치노트</button>
          </div>
          <div className="tm-status">
            <span className="num">14:32:08</span>
          </div>
        </div>

        <div className="tm-body">
          <div className="tm-mid">
            <div className="tm-main">
              {/* Symbol header */}
              <div className="tm-sym">
                <div className="ticker">086520</div>
                <div className="name-block">
                  <div className="name">에코프로 · EcoPro Co</div>
                  <div className="meta">KOSDAQ · 2차전지 · 시총 15.4조 · 지정 2026-04-08</div>
                </div>
                <div className="chips">
                  <span className="chip warn">투자경고 지정중</span>
                </div>
                <div className="px">
                  <span className="val">{fmt(M.tClose)}</span>
                  <span className="chg">▲ {fmt(M.tClose - M.prevClose)} · +{pct(M.tClose, M.prevClose)}%</span>
                </div>
              </div>

              {/* W0 — Timeline (primary — 해제 여부가 최우선) */}
              <div className="tm-sec tm-tl">
                <div className="tm-sec-head">
                  <span className="t">지정 타임라인 · 10 거래일</span>
                  <span className="src">T · 9거래일 경과 · 해제 D-1</span>
                </div>
                <div className="tm-tl-track">
                  {Array.from({length:11}).map((_,i) => {
                    const cls = i < 9 ? 'past' : i === 9 ? 'today' : 'release';
                    return <div key={i} className={`tm-tl-cell ${cls}`}>{i === 0 ? 'D0' : i === 10 ? '해제' : `T+${i}`}</div>;
                  })}
                </div>
                <div className="tm-tl-foot">
                  <span><b>2026-04-08</b> · 지정</span>
                  <span>T · <b>2026-04-21</b> · 9거래일 경과</span>
                  <span><b>2026-04-22</b> · 해제 가능</span>
                </div>
              </div>

              {/* W1 — Conditions */}
              <div className="tm-sec">
                <div className="tm-sec-head">
                  <span className="t">해제 조건 · 투자경고</span>
                  <span className="src">규정: KRX §4-2 · 3조건 AND</span>
                </div>
                <table className="tm-tbl">
                  <thead>
                    <tr>
                      <th>조건</th>
                      <th>기준일</th>
                      <th>기준 종가</th>
                      <th>×</th>
                      <th>임계가</th>
                      <th>T 종가</th>
                      <th>Δ</th>
                      <th>상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="hold">
                      <td>
                        <div className="lbl-col">
                          <div className="badge">1</div>
                          <div className="txt">
                            <div className="n">T-5 종가 × 1.45</div>
                            <div className="d">5일 45% 급등 테스트</div>
                          </div>
                        </div>
                      </td>
                      <td className="num">{M.t5Date}</td>
                      <td className="num">{fmt(M.t5Close)}</td>
                      <td>1.45×</td>
                      <td className="amber num">{fmt(M.thresh1)}</td>
                      <td className="up num">{fmt(M.tClose)}</td>
                      <td className="up num">+{pct(M.tClose, M.thresh1)}%</td>
                      <td><span className="flag hold">유지</span></td>
                    </tr>
                    <tr className="hold">
                      <td>
                        <div className="lbl-col">
                          <div className="badge">2</div>
                          <div className="txt">
                            <div className="n">T-15 종가 × 1.75</div>
                            <div className="d">15일 75% 급등 테스트</div>
                          </div>
                        </div>
                      </td>
                      <td className="num">{M.t15Date}</td>
                      <td className="num">{fmt(M.t15Close)}</td>
                      <td>1.75×</td>
                      <td className="amber num">{fmt(M.thresh2)}</td>
                      <td className="up num">{fmt(M.tClose)}</td>
                      <td className="up num">+{pct(M.tClose, M.thresh2)}%</td>
                      <td><span className="flag hold">유지</span></td>
                    </tr>
                    <tr className="clear">
                      <td>
                        <div className="lbl-col">
                          <div className="badge">3</div>
                          <div className="txt">
                            <div className="n">= 15일 최고 종가</div>
                            <div className="d">15일 최고가와 동일</div>
                          </div>
                        </div>
                      </td>
                      <td className="num">{M.max15Date}</td>
                      <td className="num">{fmt(M.max15)}</td>
                      <td>=</td>
                      <td className="amber num">{fmt(M.max15)}</td>
                      <td className="dn num">{fmt(M.tClose)}</td>
                      <td className="dn num">{pct(M.tClose, M.max15)}%</td>
                      <td><span className="flag clear">이탈</span></td>
                    </tr>
                  </tbody>
                </table>

                {/* Toss-warm verdict inside terminal shell */}
                <div className="tm-verdict">
                  <div className="ico">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 8l3 3 7-7"/>
                    </svg>
                  </div>
                  <div className="body">
                    <div className="head">
                      <span className="tag">다음 거래일 해제</span>
                    </div>
                    <div className="h">다음 거래일(4/22) 투자경고 해제</div>
                    <div className="b">조건 ③ <span className="num">15일 최고가 일치</span> 요건 미충족 · 10 거래일 경과 요건도 수요일에 충족. KRX §4-2 규정상 세 조건 중 하나라도 미충족이면 다음 거래일에 해제됩니다.</div>
                  </div>
                  <div className="side">
                    <div className="d">04-22</div>
                    <div className="l">해제 가능일</div>
                  </div>
                </div>
              </div>

              {/* W2 — Chart */}
              <div className="tm-sec">
                <div className="tm-sec-head">
                  <span className="t">시세 · 30일 + 임계선</span>
                  <span className="src">출처: NAVER · KRX</span>
                </div>
                <div className="tm-chart-wrap">
                  <div className="tm-chart-tabs">
                    <button>1D</button>
                    <button>5D</button>
                    <button className="active">30D</button>
                    <button>3M</button>
                    <button>1Y</button>
                    <div className="flex" />
                    <div className="legend">
                      <span><span className="sw" style={{background: T.p}}/>① 577,100</span>
                      <span><span className="sw" style={{background:'#F04452'}}/>② 574,000</span>
                      <span><span className="sw" style={{background:'#4ADE80'}}/>③ 591,000</span>
                    </div>
                  </div>
                  <div className="tm-chart">
                    <svg viewBox={`0 0 ${chart.W} ${chart.H}`} preserveAspectRatio="none">
                      {/* grid */}
                      {[0.25,0.5,0.75].map(f => (
                        <line key={f} x1={chart.P} x2={chart.W-chart.P} y1={chart.P + f*(chart.H - 2*chart.P)}
                              y2={chart.P + f*(chart.H - 2*chart.P)} stroke="#1E1E22" strokeWidth="1" />
                      ))}
                      {/* threshold lines */}
                      {chart.lines.map((ln,i) => {
                        const y = chart.ys(ln.v);
                        return (
                          <g key={i}>
                            <line x1={chart.P} x2={chart.W-chart.P} y1={y} y2={y}
                                  stroke={ln.color} strokeWidth="1" strokeDasharray="4 3" opacity="0.7" />
                          </g>
                        );
                      })}
                      {/* area */}
                      <defs>
                        <linearGradient id="tm-g" x1="0" x2="0" y1="0" y2="1">
                          <stop offset="0%" stopColor={T.p} stopOpacity="0.30"/>
                          <stop offset="100%" stopColor={T.p} stopOpacity="0"/>
                        </linearGradient>
                      </defs>
                      <path d={chart.areaD} fill="url(#tm-g)" />
                      <path d={chart.pathD} fill="none" stroke={T.p} strokeWidth="1.5" />
                      {/* last point */}
                      <circle cx={chart.xs(chart.prices.length-1)} cy={chart.ys(chart.prices[chart.prices.length-1])} r="3.5" fill="#F04452" stroke="#0A0A0A" strokeWidth="1.5" />
                      {/* 15-day max marker (just before last) */}
                      <circle cx={chart.xs(chart.prices.length-5)} cy={chart.ys(M.max15)} r="2.5" fill="#4ADE80" />
                    </svg>
                    <div className="crosshair">
                      <span className="k">T 2026-04-21 · </span>
                      <span>종가 <b className="num" style={{color:'#F04452'}}>{fmt(M.tClose)}</b></span>
                      <span className="k"> · 15일 최고 </span>
                      <span style={{color:'#4ADE80'}} className="num">{fmt(M.max15)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Base · Price strip (후순위 — 기본 시세) */}
              <div className="tm-sec">
                <div className="tm-sec-head">
                  <span className="t">기본 시세</span>
                  <span className="src">출처: NAVER 모바일</span>
                </div>
                <div className="tm-strip">
                  <div className="tm-cell">
                    <div className="l">시가</div>
                    <div className="v">{fmt(M.tOpen)}</div>
                    <div className="s">전일 {fmt(M.prevClose)}</div>
                  </div>
                  <div className="tm-cell">
                    <div className="l">고가 / 저가</div>
                    <div className="v up">{fmt(M.dayHigh)}</div>
                    <div className="s dn">{fmt(M.dayLow)}</div>
                  </div>
                  <div className="tm-cell">
                    <div className="l">거래량</div>
                    <div className="v">{fmt(M.volume)}</div>
                    <div className="s">주</div>
                  </div>
                  <div className="tm-cell">
                    <div className="l">시총</div>
                    <div className="v">15.4조</div>
                    <div className="s">KOSDAQ</div>
                  </div>
                  <div className="tm-cell">
                    <div className="l">52주 고 / 저</div>
                    <div className="v up" style={{fontSize:12}}>{fmt(M.high52w)}</div>
                    <div className="s dn">{fmt(M.low52w)}</div>
                  </div>
                  <div className="tm-cell">
                    <div className="l">PER · PBR</div>
                    <div className="v">68.3 · 8.42</div>
                    <div className="s">외인 12.7%</div>
                  </div>
                </div>
              </div>

              {/* W4 — Rules */}
              <div className="tm-sec">
                <div className="tm-sec-head">
                  <span className="t">KRX 규정 · 시장경보</span>
                </div>
                <div className="tm-rules">
                  <div className="r">
                    <span className="k">10일</span>
                    <span className="v">지정일로부터 10 매매거래일 경과 후 해제 심사 시작</span>
                    <span className="m">2026-04-22</span>
                  </div>
                  <div className="r">
                    <span className="k">AND</span>
                    <span className="v">① ② ③ 세 조건 모두 충족 시 경고 유지. 하나라도 미충족이면 다음 거래일 해제.</span>
                    <span className="m">3 중 2</span>
                  </div>
                  <div className="r">
                    <span className="k">증거금</span>
                    <span className="v">지정 기간 중 신용융자 금지, 위탁증거금 100% 현금</span>
                    <span className="m">—</span>
                  </div>
                  <div className="r">
                    <span className="k">상향</span>
                    <span className="v">지정 기간 내 요건 재충족 시 투자위험종목으로 상향 지정</span>
                    <span className="m">—</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Side */}
            <div className="tm-side">
              <div className="tm-sec">
                <div className="tm-sec-head">
                  <span className="t">관심종목</span>
                </div>
                <div className="tm-wl">
                  {M.watchlist.map((w,i) => (
                    <div key={i} className="tm-wl-row">
                      <div>
                        <div className="n">{w.name}</div>
                        <div className="c">{w.code}
                          {w.dday !== '—' && <span className="dday"> · {w.dday}</span>}
                        </div>
                      </div>
                      <div className="chg">
                        <div className="p num">{fmt(w.price)}</div>
                      </div>
                      <div className={`lv ${w.level === '투자경고' ? 'w' : w.level === '투자주의' ? 'c' : 'n'}`}>
                        {w.level === '—' ? '—' : w.level === '투자경고' ? '경고' : '주의'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="tm-sec">
                <div className="tm-sec-head">
                  <span className="t">공시 피드</span>
                </div>
                <div>
                  {M.disclosures.map((d,i) => (
                    <div key={i} className="tm-disc-row">
                      <div className="mt">
                        <span className="d num">{d.date}</span>
                        <span className="ty">{d.type}</span>
                      </div>
                      <div className="ti">{d.title}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Ticker tape — 투자 금지 미신 (원본 사이트 하단) */}
        <div className="tm-tape">
          <div className="tm-tape-label">TABOO · 투자금지</div>
          <div className="tm-tape-track" style={{paddingLeft:110}}>
            {[...Array(2)].flatMap((_,loop) => [
              'ㅅㅅㅅ 금지','가즈아 금지','심상정인데? 금지','오늘 xxx 개쎄다 금지',
              '거래대금 언급 금지','거래량 보소 금지','미쳤다 금지','다행이다 금지',
              '차 살까? 금지','계좌 고점이다 금지','했제 금지','xxx 왜 안삼? 금지',
              '해외 골프 금지',
            ].map((t,i) => (
              <span key={`${loop}-${i}`} className="tm-tape-item">{t}</span>
            )))}
          </div>
        </div>

        {/* Bottom status line removed — empty footer bar */}
      </div>
    </React.Fragment>
  );
}

window.TerminalMockup = TerminalMockup;
