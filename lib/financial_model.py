"""재무 모델 빌더 — DART 전체계정 데이터를 Model 시트 양식 JSON으로 변환.

설계 노트:
- 본 MVP는 DART Open API(fnlttSinglAcntAll)만 사용 → P&L/BS/CF 메인 계정 약 70% 커버.
- 미지원 필드(인건비, 광고선전비, 토지/설비 등 세부, 직원수, 환율)는 null 반환.
- 추후 어댑터 추가 시 build_model() 내부에서 enrich_*()만 호출 추가.
- Supabase 캐싱: 확정 기간(전년도 이전) 데이터는 DB에서 조회, 미확정만 DART 호출.
"""
import json, os
from concurrent.futures import ThreadPoolExecutor

from lib.dart_full import fetch_all
from lib.http_utils import log_event, safe_exception_text

_MAPPING_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'data', 'account-mapping.json')

with open(_MAPPING_PATH, encoding='utf-8') as _f:
    MAPPING = json.load(_f)


# DART reprt_code → 분기 매핑 (DART Open API 표준)
REPRT_QUARTER = {
    '11013': '1Q',
    '11012': '2Q',
    '11014': '3Q',
    '11011': 'FY',
}


def derive_q4_from_annual(q1, q2, q3, fy):
    """단일 분기 IS/CF 값들에서 Q4 도출. Q4 = FY - (Q1+Q2+Q3)."""
    if fy is None:
        return None
    parts = [q1, q2, q3]
    if any(p is None for p in parts):
        return None
    return fy - (q1 + q2 + q3)


def yoy(cur, prev):
    """전년 대비 증감률. None safe."""
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev)


def safe_div(num, den):
    if num is None or den is None or den == 0:
        return None
    return num / den


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def _to_num(s):
    if s is None or s == '' or s == '-':
        return None
    try:
        return float(str(s).replace(',', ''))
    except (ValueError, TypeError):
        return None


def _index_accounts(api_response: dict, fs_div: str) -> dict:
    """DART API 응답 → {sj_div::key: amount} 인덱스.
    fnlttSinglAcntAll은 호출 파라미터로 fs_div를 이미 필터링하므로 응답 item에는
    fs_div 필드가 없음. sj_div(BS/IS/CIS/CF/SCE)로만 구분.
    """
    if api_response.get('status') != '000':
        return {}
    out = {}
    for item in api_response.get('list', []):
        aid = item.get('account_id', '')
        anm = item.get('account_nm', '')
        amt = _to_num(item.get('thstrm_amount'))
        if amt is None:
            continue
        sj = item.get('sj_div', '')
        out[f'{sj}::{aid}'] = amt
        out[f'{sj}::name::{anm}'] = amt
    return out


def _resolve(idx: dict, sj: str, candidates: dict):
    """candidates: {ids: [...], names: [...]} → 첫 매칭 amount or None."""
    for aid in candidates.get('ids', []):
        v = idx.get(f'{sj}::{aid}')
        if v is not None:
            return v
    for nm in candidates.get('names', []):
        v = idx.get(f'{sj}::name::{nm}')
        if v is not None:
            return v
    return None


def _extract_period(api_response: dict, fs_div: str) -> dict:
    """단일 보고서 응답 → 표준화된 필드 dict."""
    idx = _index_accounts(api_response, fs_div)
    out = {}
    # IS — 손익계산서/포괄손익계산서. sj_div는 IS 또는 CIS
    for key, cand in MAPPING['is'].items():
        out[key] = _resolve(idx, 'IS', cand) or _resolve(idx, 'CIS', cand)
    # BS
    for key, cand in MAPPING['bs'].items():
        out[key] = _resolve(idx, 'BS', cand)
    # CF
    for key, cand in MAPPING['cf'].items():
        out[key] = _resolve(idx, 'CF', cand)
    return out


def _fetch_period_safe(corp_code: str, year: str, reprt: str, fs_div: str):
    try:
        return fetch_all(corp_code, year, reprt, fs_div)
    except Exception as e:
        return {'status': 'ERR', 'message': str(e)}


def _periods_to_quarterly(by_period: dict) -> dict:
    """{period_label: extracted_dict} → 단일 분기 1Q/2Q/3Q/4Q dict.
    period_label: '1Q','2Q','3Q','FY'.
    IS/CF: 보고서 thstrm은 단일 분기값. Q4는 FY - (Q1+Q2+Q3)으로 도출.
    BS: 시점값. 4Q는 사업보고서의 12/31 시점값 사용.
    """
    flow_keys = list(MAPPING['is'].keys()) + list(MAPPING['cf'].keys())
    stock_keys = list(MAPPING['bs'].keys())

    result = {q: {} for q in ['1Q', '2Q', '3Q', '4Q']}

    # Flow: 분기 보고서값 그대로, Q4는 FY - 합
    for key in flow_keys:
        q1 = by_period.get('1Q', {}).get(key)
        q2 = by_period.get('2Q', {}).get(key)
        q3 = by_period.get('3Q', {}).get(key)
        fy = by_period.get('FY', {}).get(key)
        result['1Q'][key] = q1
        result['2Q'][key] = q2
        result['3Q'][key] = q3
        result['4Q'][key] = derive_q4_from_annual(q1, q2, q3, fy)

    # Stock: 각 보고서 시점값. Q4 = 사업보고서 시점값(12/31)
    for key in stock_keys:
        result['1Q'][key] = by_period.get('1Q', {}).get(key)
        result['2Q'][key] = by_period.get('2Q', {}).get(key)
        result['3Q'][key] = by_period.get('3Q', {}).get(key)
        result['4Q'][key] = by_period.get('FY', {}).get(key)
    return result


def _enrich_derived(period: dict) -> dict:
    """파생 지표 계산 — YoY 제외(다년 비교 필요)."""
    rev = period.get('revenue')
    period['gpm'] = safe_div(period.get('gross_profit'), rev)
    period['opm'] = safe_div(period.get('operating_income'), rev)
    period['npm'] = safe_div(period.get('net_income'), rev)
    period['tax_rate'] = safe_div(period.get('income_tax'), period.get('pretax_income'))
    # 차입금 = 단기 + 장기
    st = period.get('st_borrowings') or 0
    lt = period.get('lt_borrowings') or 0
    if period.get('st_borrowings') is not None or period.get('lt_borrowings') is not None:
        period['total_borrowings'] = st + lt
    else:
        period['total_borrowings'] = None
    # 순현금 = 현금 - 차입금
    cash = period.get('cash')
    if cash is not None and period['total_borrowings'] is not None:
        period['net_cash'] = cash - period['total_borrowings']
    else:
        period['net_cash'] = None
    # CAPEX = 유형자산 취득 + 무형자산 취득
    capex_p = period.get('capex_ppe') or 0
    capex_i = period.get('capex_intangible') or 0
    if period.get('capex_ppe') is not None or period.get('capex_intangible') is not None:
        period['capex'] = capex_p + capex_i
    else:
        period['capex'] = None
    return period


def _load_cache(corp_code: str, fs_div: str) -> dict:
    """Supabase에서 기존 캐시 데이터를 일괄 로드 → {(period_type, period_key): data}"""
    try:
        from lib.supabase_client import cache_enabled, get_client
        if not cache_enabled():
            return {}
        rows = (get_client().table('financial_data')
                .select('period_type, period_key, data')
                .eq('corp_code', corp_code)
                .eq('fs_div', fs_div)
                .execute()).data
        return {(r['period_type'], r['period_key']): r['data'] for r in rows}
    except Exception as e:
        log_event('warning', 'financial_cache_load_failed',
                  error=safe_exception_text(e))
        return {}


def _save_cache(corp_code: str, fs_div: str, rows: list):
    """새 데이터를 Supabase에 upsert. rows: [{'period_type', 'period_key', 'data'}]"""
    if not rows:
        return
    try:
        from lib.supabase_client import cache_writes_enabled, get_client
        if not cache_writes_enabled():
            return
        records = [{'corp_code': corp_code, 'fs_div': fs_div, **r} for r in rows]
        (get_client().table('financial_data')
         .upsert(records, on_conflict='corp_code,fs_div,period_type,period_key')
         .execute())
    except Exception as e:
        log_event('warning', 'financial_cache_save_failed',
                  error=safe_exception_text(e))


def build_model(corp_code: str, fs_div: str = 'CFS', years: int = 5) -> dict:
    """
    Args:
        corp_code: DART 8자리 corp_code
        fs_div: 'CFS'(연결) or 'OFS'(별도)
        years: 조회할 연수 (현재년-1 부터 역순)
    Returns:
        {
          'meta': {corp_code, fs_div, years_requested, last_period},
          'annual': { '2020': {...}, '2021': {...}, ... },
          'quarterly': { '1Q23': {...}, '2Q23': {...}, ... }
        }
    """
    from datetime import date
    end_year = date.today().year - 1
    start_year = end_year - years + 1
    year_list = [str(y) for y in range(start_year, end_year + 1)]

    # ── Supabase 캐시 로드 ──
    cache = _load_cache(corp_code, fs_div)

    # 확정 기간 판별: 전년도(end_year - 1) 이전은 변하지 않음
    current_year = str(date.today().year)
    prev_year = str(end_year)  # 가장 최근 연도 (아직 보고서 업데이트 가능)

    def _is_settled(year: str) -> bool:
        """전전년도 이전이면 확정 (보고서 수정 가능성 없음)"""
        return year < prev_year

    def _year_fully_cached(year: str) -> bool:
        """해당 연도의 연간 + 4분기 모두 캐시에 있으면 True"""
        if ('annual', year) not in cache:
            return False
        for q in ['1Q', '2Q', '3Q', '4Q']:
            if ('quarterly', f'{q}{year[2:]}') not in cache:
                return False
        return True

    annual = {}
    by_year_period = {}
    to_save = []  # Supabase에 저장할 새 데이터

    # ── 연도별 처리: 캐시 히트 or DART 호출 ──
    years_to_fetch = []
    for y in year_list:
        if _is_settled(y) and _year_fully_cached(y):
            # 캐시에서 복원
            annual[y] = cache[('annual', y)]
            by_year_period[y] = {}
            for q in ['1Q', '2Q', '3Q', '4Q']:
                by_year_period[y][q] = cache[('quarterly', f'{q}{y[2:]}')]
        else:
            years_to_fetch.append(y)

    # ── 캐시 미스 연도만 DART 병렬 호출 ──
    if years_to_fetch:
        tasks = []
        planned_calls = len(years_to_fetch) * len(REPRT_QUARTER)
        warn_calls = _env_int('DART_FINANCIAL_WARN_CALLS_PER_REQUEST', 12, 1, 64)
        max_workers = _env_int('DART_FINANCIAL_MAX_WORKERS', 2, 1, 4)
        log_event(
            'info',
            'financial_dart_fetch_plan',
            corp_code=corp_code,
            fs_div=fs_div,
            years_to_fetch=years_to_fetch,
            planned_calls=planned_calls,
            max_workers=max_workers,
            cached_years=[y for y in year_list if y not in years_to_fetch],
        )
        if planned_calls >= warn_calls:
            log_event(
                'warning',
                'financial_dart_fetch_burst',
                corp_code=corp_code,
                planned_calls=planned_calls,
                threshold=warn_calls,
            )
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for y in years_to_fetch:
                for reprt in REPRT_QUARTER:
                    tasks.append((y, reprt, ex.submit(_fetch_period_safe, corp_code, y, reprt, fs_div)))

            for y, reprt, fut in tasks:
                resp = fut.result()
                period = _extract_period(resp, fs_div) if resp.get('status') == '000' else {}
                label = REPRT_QUARTER[reprt]
                by_year_period.setdefault(y, {})[label] = period

                if reprt == '11011' and period:
                    annual[y] = _enrich_derived(dict(period))

    # ── 분기 단일값 산출 (DART 호출된 연도만) ──
    quarterly = {}
    for y in year_list:
        if y not in years_to_fetch:
            # 캐시에서 복원된 분기 데이터 (이미 enrich 완료)
            for q in ['1Q', '2Q', '3Q', '4Q']:
                quarterly[f'{q}{y[2:]}'] = by_year_period[y][q]
            continue
        single = _periods_to_quarterly(by_year_period.get(y, {}))
        for q in ['1Q', '2Q', '3Q', '4Q']:
            label = f'{q}{y[2:]}'
            quarterly[label] = _enrich_derived(dict(single[q]))

    # ── 연간 YoY 계산 ──
    sorted_years = sorted(annual.keys())
    for i, y in enumerate(sorted_years):
        if i == 0:
            annual[y]['revenue_yoy'] = None
        else:
            prev_y = sorted_years[i - 1]
            annual[y]['revenue_yoy'] = yoy(annual[y].get('revenue'),
                                           annual[prev_y].get('revenue'))

    # ── 분기 YoY 계산 ──
    for y in year_list:
        prev_y = str(int(y) - 1)
        for q in ['1Q', '2Q', '3Q', '4Q']:
            cur_label = f'{q}{y[2:]}'
            prev_label = f'{q}{prev_y[2:]}'
            cur = quarterly.get(cur_label, {})
            prev = quarterly.get(prev_label, {})
            cur['revenue_yoy'] = yoy(cur.get('revenue'), prev.get('revenue')) if prev else None

    # ── DART에서 가져온 데이터를 Supabase에 저장 ──
    for y in years_to_fetch:
        if y in annual:
            to_save.append({'period_type': 'annual', 'period_key': y, 'data': annual[y]})
        for q in ['1Q', '2Q', '3Q', '4Q']:
            label = f'{q}{y[2:]}'
            if label in quarterly and any(v is not None for v in quarterly[label].values()):
                to_save.append({'period_type': 'quarterly', 'period_key': label, 'data': quarterly[label]})
    _save_cache(corp_code, fs_div, to_save)

    return {
        'meta': {
            'corp_code': corp_code,
            'fs_div': fs_div,
            'years': year_list,
            'unsupported': MAPPING['_unsupported_mvp']['fields'],
            'cached_years': [y for y in year_list if y not in years_to_fetch],
            'fetched_years': years_to_fetch,
        },
        'annual': annual,
        'quarterly': quarterly,
    }
