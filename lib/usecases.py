"""Shared endpoint use cases.

API handlers and the local development server should stay as transport shims:
parse HTTP, call one of these functions, then shape the HTTP response.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from lib.dart import search_disclosure
from lib.dart_base import DART_SEARCH_OK_STATUSES, raise_for_status
from lib.financial_api_security import validate_params
from lib.holidays import add_trading_days, count_trading_days
from lib.krx import search_kind, search_kind_caution
from lib.naver import (
    calc_official_escalation,
    calc_thresholds,
    fetch_index_prices,
    fetch_prices,
    fetch_stock_overview,
    stock_code,
)
from lib.validation import (
    normalize_query,
    parse_int_range,
    validate_corp_code,
    validate_dart_pblntf_ty,
    validate_date_range,
    validate_stock_code,
)


KST = timezone(timedelta(hours=9))


def _market_to_index_symbol(market: str) -> str:
    """시장명(한글/영문) → 네이버 fchart 지수 심볼."""
    if not market:
        return ''
    m = market.upper()
    if 'KOSDAQ' in m or '코스닥' in market:
        return 'KOSDAQ'
    if 'KOSPI' in m or '코스피' in market or '유가증권' in market:
        return 'KOSPI'
    return ''


def warning_search_payload(raw_name: str) -> dict:
    name = normalize_query(raw_name)
    return {'results': search_kind(name), 'query': name}


def caution_search_payload(raw_name: str) -> dict:
    """투자주의 → 투자경고 격상 여부 점검.

    활성 '투자경고 지정예고' 윈도우(예고일 + 10거래일 이내)가 있으면
    공식 [1]/[2] 조건을 계산한다.

    반환 status:
      'ok'                — 활성 지정예고 + [1]/[2] 계산 완료
      'non_price_reason'  — 오늘 지정은 있으나 활성 예고 없음 (소수계좌 등)
      'not_caution'       — 투자주의 이력 자체 없음 또는 활성 이력 없음
      'code_not_found'    — 네이버 종목코드 조회 실패
      'price_error'       — 주가/지수 조회 실패 또는 데이터 부족
    최상위 예외는 호출자(핸들러)에서 'error' 로 감쌈.
    """
    today_kst = datetime.now(KST).date().isoformat()
    raw = (raw_name or '').strip()
    if not raw:
        return {'status': 'not_caution', 'query': '', 'todayKst': today_kst}

    name = normalize_query(raw)
    results = search_kind_caution(name)
    if not results:
        return {'status': 'not_caution', 'query': name, 'todayKst': today_kst}

    warn = results[0]
    today_date = datetime.now(KST).date()
    entries = warn.get('entries', [])

    # 가장 최근의 '투자경고 지정예고' 행 중 판단 윈도우(예고일 + 10거래일)가
    # 아직 유효한 것을 찾는다. entries는 최신→과거 순 정렬.
    active_notice = None
    for e in entries:
        if e.get('reason') != '투자경고 지정예고':
            continue
        try:
            notice_date = date.fromisoformat(e['date'])
        except ValueError:
            continue
        last_judgment = add_trading_days(notice_date, 10)
        if last_judgment >= today_date:
            first_judgment = add_trading_days(notice_date, 1)
            try:
                elapsed = count_trading_days(notice_date, today_date) - 1
            except Exception:
                elapsed = 0
            active_notice = {
                'noticeDate': e['date'],
                'firstJudgmentDate': first_judgment.isoformat(),
                'lastJudgmentDate': last_judgment.isoformat(),
                'judgmentDayIndex': max(0, elapsed),
                'judgmentWindowTotal': 10,
            }
            break

    krx_market = warn.get('market', '')
    latest_reason = warn.get('latestDesignationReason', '')
    latest_date = warn.get('latestDesignationDate', '')

    base_fields = {
        'query': name, 'todayKst': today_kst,
        'stockName': warn['stockName'],
        'latestDesignationDate': latest_date,
        'designationReason': latest_reason,
        'recent15dCount': warn.get('recent15dCount', 0),
        'allDates': warn.get('allDates', []),
        'entries': entries,
        'krxMarket': krx_market,
    }

    if not active_notice:
        if latest_date == today_kst:
            return {'status': 'non_price_reason', **base_fields}
        return {'status': 'not_caution', **base_fields}

    base_fields['activeNotice'] = active_notice

    codes = stock_code(warn['stockName'])
    if not codes:
        return {'status': 'code_not_found', **base_fields}

    code = codes[0]['code']
    naver_market = codes[0].get('market', '')
    idx_symbol = _market_to_index_symbol(krx_market or naver_market)

    if not idx_symbol:
        return {
            'status': 'price_error', **base_fields,
            'code': code, 'market': naver_market,
            'errorMessage': f'시장 구분 판정 실패 ({krx_market or naver_market!r})',
        }

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            price_future = pool.submit(fetch_prices, code, count=30)
            index_future = pool.submit(fetch_index_prices, idx_symbol, count=30)
            prices = price_future.result()
            index_prices = index_future.result()
    except Exception as e:
        return {
            'status': 'price_error', **base_fields,
            'code': code, 'market': naver_market, 'indexSymbol': idx_symbol,
            'errorMessage': str(e),
        }

    escalation = calc_official_escalation(prices, index_prices)
    if 'error' in escalation:
        return {
            'status': 'price_error', **base_fields,
            'code': code, 'market': naver_market, 'indexSymbol': idx_symbol,
            'errorMessage': escalation['error'],
        }

    return {
        'status': 'ok', **base_fields,
        'code': code, 'market': naver_market, 'indexSymbol': idx_symbol,
        'escalation': escalation,
    }


def stock_code_payload(raw_name: str) -> dict:
    name = normalize_query(raw_name)
    return {'items': stock_code(name)}


def stock_price_payload(raw_code: str) -> dict:
    code = validate_stock_code(raw_code)
    prices = fetch_prices(code, count=20)
    thresholds = calc_thresholds(prices)
    payload = {'prices': prices[-16:], 'thresholds': thresholds}
    if 'error' in thresholds:
        payload['warnings'] = [{
            'code': 'INSUFFICIENT_PRICE_DATA',
            'message': thresholds['error'],
        }]
    return payload


def stock_overview_payload(raw_code: str) -> dict:
    code = validate_stock_code(raw_code)
    return fetch_stock_overview(code)


def dart_search_payload(
    *,
    corp_code: str = '',
    bgn_de: str = '',
    end_de: str = '',
    page_no: str = '1',
    page_count: str = '20',
    pblntf_ty: str = '',
) -> dict:
    valid_corp_code = validate_corp_code(corp_code, required=False)
    valid_bgn_de, valid_end_de = validate_date_range(bgn_de, end_de)
    valid_page_no = parse_int_range(page_no, 'page_no', 1, 1, 1000)
    valid_page_count = parse_int_range(page_count, 'page_count', 20, 1, 100)
    valid_pblntf_ty = validate_dart_pblntf_ty(pblntf_ty)
    data = search_disclosure(
        corp_code=valid_corp_code,
        bgn_de=valid_bgn_de,
        end_de=valid_end_de,
        page_no=valid_page_no,
        page_count=valid_page_count,
        pblntf_ty=valid_pblntf_ty,
    )
    raise_for_status(data, ok_statuses=DART_SEARCH_OK_STATUSES)
    return data


def financial_model_payload(
    *,
    corp_code: str,
    fs_div: str = 'CFS',
    years: str = '5',
) -> dict:
    valid_corp_code, valid_fs_div, valid_years = validate_params(
        corp_code,
        fs_div,
        years,
    )
    from lib.financial_model import build_model

    return build_model(valid_corp_code, fs_div=valid_fs_div, years=valid_years)
