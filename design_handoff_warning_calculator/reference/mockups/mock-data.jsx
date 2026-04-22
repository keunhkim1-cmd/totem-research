// Shared mock data — 에코프로 투자경고 지정 시나리오
const MOCK = {
  stockName: '에코프로',
  stockCode: '086520',
  market: 'KOSDAQ',
  designationDate: '2026-04-08',
  tDate: '2026-04-21',
  elapsedDays: 9,
  releaseDate: '2026-04-22',

  // Price summary
  tClose: 584000,
  tOpen: 578000,
  prevClose: 572000,
  dayHigh: 591000,
  dayLow: 575500,
  volume: 2841293,
  tradingValue: 1657284000000, // 1.66조

  // Thresholds (cond1, cond2, cond3)
  t5Date: '2026-04-14',
  t5Close: 398000,
  thresh1: 577100, // 398000 * 1.45
  cond1: true,

  t15Date: '2026-03-31',
  t15Close: 328000,
  thresh2: 574000, // 328000 * 1.75
  cond2: true,

  max15: 591000,
  max15Date: '2026-04-20',
  cond3: false, // T close < 15-day max → release candidate

  // Overview extras
  marketCap: '15.4조',
  per: '68.3',
  pbr: '8.42',
  foreignRate: '12.7%',
  high52w: 629000,
  low52w: 268500,

  // Related warnings (ticker-ish)
  watchlist: [
    { name: '에코프로',      code: '086520', level: '투자경고', dday: 'D-1',  price: 584000, chg: +2.10 },
    { name: '에코프로비엠',    code: '247540', level: '투자주의', dday: '—',    price: 312500, chg: +1.84 },
    { name: '포스코퓨처엠',    code: '003670', level: '투자주의', dday: '—',    price: 287000, chg: -0.35 },
    { name: '엘앤에프',       code: '066970', level: '투자경고', dday: 'D-4',  price: 198700, chg: +4.21 },
    { name: '삼성SDI',        code: '006400', level: '—',      dday: '—',    price: 415500, chg: -1.07 },
    { name: 'LG에너지솔루션',  code: '373220', level: '—',      dday: '—',    price: 408000, chg: +0.49 },
  ],

  // Recent disclosures
  disclosures: [
    { date: '2026-04-21', type: '거래소공시', title: '투자경고종목 지정',              corp: '에코프로' },
    { date: '2026-04-18', type: '주요사항',   title: '현금·현물배당 결정',               corp: '에코프로' },
    { date: '2026-04-15', type: '정기공시',   title: '분기보고서 (2026.03)',             corp: '에코프로' },
    { date: '2026-04-10', type: '지분공시',   title: '주식등의대량보유상황보고서',        corp: '에코프로' },
    { date: '2026-04-03', type: '거래소공시', title: '투자주의종목 지정',                corp: '에코프로' },
  ],
};

window.MOCK = MOCK;
