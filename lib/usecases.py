"""Shared endpoint use cases.

API handlers and the local development server should stay as transport shims:
parse HTTP, call one of these functions, then shape the HTTP response.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from lib.dart import search_disclosure
from lib.dart_base import DART_SEARCH_OK_STATUSES, raise_for_status
from lib.forecast_policy import FORECAST_POLICY, build_forecast_signal
from lib.holidays import count_trading_days, is_trading_day
from lib.http_utils import safe_exception_text
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
FORECAST_MAX_WORKERS = 4
FORECAST_PRICE_COUNT = 30
WARNING_NOTICE_REASON = '투자경고 지정예고'
INTERNAL_REVIEW_REASON_KEYWORDS = (
    '불건전',
    '매수관여',
    '시세영향',
    '소수계좌',
    '특정계좌',
    '풍문',
    '스팸',
)


def _nth_trading_day_inclusive(start: date, n: int) -> date:
    if n < 1:
        raise ValueError('n must be >= 1')
    cur = start
    count = 0
    while True:
        if is_trading_day(cur):
            count += 1
            if count == n:
                return cur
        cur += timedelta(days=1)


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


def _today_kst_date() -> date:
    return datetime.now(KST).date()


def _active_warning_notice(entries: list, today_date: date) -> dict | None:
    """Return the latest active KRX warning-designation notice window."""
    for entry in entries:
        if WARNING_NOTICE_REASON not in str(entry.get('reason', '')):
            continue
        try:
            notice_date = date.fromisoformat(entry['date'])
        except (KeyError, TypeError, ValueError):
            continue
        first_judgment = _nth_trading_day_inclusive(notice_date, 1)
        last_judgment = _nth_trading_day_inclusive(notice_date, 10)
        if last_judgment < today_date:
            continue
        if today_date < first_judgment:
            elapsed = 0
        else:
            try:
                elapsed = count_trading_days(first_judgment, today_date)
            except Exception:
                elapsed = 0
        return {
            'noticeDate': entry['date'],
            'noticeReason': str(entry.get('reason', '')),
            'firstJudgmentDate': first_judgment.isoformat(),
            'lastJudgmentDate': last_judgment.isoformat(),
            'judgmentDayIndex': max(0, min(10, elapsed)),
            'judgmentWindowTotal': 10,
            'judgmentWindowRule': '지정예고일 포함 10거래일',
        }
    return None


def _caution_base_fields(name: str, warn: dict, today_kst: str) -> dict:
    return {
        'query': name, 'todayKst': today_kst,
        'stockName': warn['stockName'],
        'latestDesignationDate': warn.get('latestDesignationDate', ''),
        'designationReason': warn.get('latestDesignationReason', ''),
        'recent15dCount': warn.get('recent15dCount', 0),
        'allDates': warn.get('allDates', []),
        'entries': warn.get('entries', []),
        'krxMarket': warn.get('market', ''),
    }


def _notice_requires_internal_review(active_notice: dict) -> bool:
    text = str(active_notice.get('noticeReason', ''))
    return any(keyword in text for keyword in INTERNAL_REVIEW_REASON_KEYWORDS)


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
    today_date = _today_kst_date()
    today_kst = today_date.isoformat()
    raw = (raw_name or '').strip()
    if not raw:
        return {'status': 'not_caution', 'query': '', 'todayKst': today_kst}

    name = normalize_query(raw)
    results = search_kind_caution(name)
    if not results:
        return {'status': 'not_caution', 'query': name, 'todayKst': today_kst}

    warn = results[0]
    entries = warn.get('entries', [])

    # 가장 최근의 '투자경고 지정예고' 행 중 판단 윈도우(예고일 + 10거래일)가
    # 아직 유효한 것을 찾는다. entries는 최신→과거 순 정렬.
    active_notice = _active_warning_notice(entries, today_date)

    base_fields = _caution_base_fields(name, warn, today_kst)
    krx_market = base_fields['krxMarket']
    latest_date = base_fields['latestDesignationDate']

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
        'forecastSignal': build_forecast_signal(escalation),
    }


def _forecast_base_item(warn: dict, active_notice: dict) -> dict:
    return {
        'level': 'watch',
        'levelLabel': '주의보',
        'stockName': warn['stockName'],
        'code': '',
        'market': warn.get('market', ''),
        'krxMarket': warn.get('market', ''),
        'noticeDate': active_notice['noticeDate'],
        'noticeReason': active_notice.get('noticeReason', ''),
        'firstJudgmentDate': active_notice['firstJudgmentDate'],
        'lastJudgmentDate': active_notice['lastJudgmentDate'],
        'judgmentDayIndex': active_notice['judgmentDayIndex'],
        'judgmentWindowTotal': active_notice['judgmentWindowTotal'],
        'designationReason': warn.get('latestDesignationReason', ''),
        'recent15dCount': warn.get('recent15dCount', 0),
        'calcStatus': 'pending',
        'calcStatusLabel': '계산 대기',
    }


def _forecast_needs_review(item: dict, detail: str) -> dict:
    item.update({
        'level': 'review',
        'levelLabel': '확인',
        'calcStatus': 'needs_review',
        'calcStatusLabel': '확인 필요',
        'calcDetail': detail,
        'riskScore': 0,
        'forecastSignal': {
            'riskLevel': 'review',
            'riskLabel': '확인 필요',
            'riskScore': 0,
            'primarySignal': detail,
            'remainingText': '공개 데이터만으로 자동 판단 불가',
        },
    })
    return item


def _forecast_source_error(source: str, message: str, *, stock_name: str = '') -> dict:
    error = {
        'source': source,
        'message': message,
    }
    if stock_name:
        error['stockName'] = stock_name
    return error


def _warning_history_still_active(row: dict, today_date: date) -> tuple[bool, dict | None]:
    stock_name = row.get('stockName', '')
    designation = row.get('designationDate', '')
    try:
        designation_date = date.fromisoformat(designation)
    except (TypeError, ValueError):
        return False, _forecast_source_error(
            'krx-warning-current-status',
            f'경고 지정일을 해석할 수 없습니다: {designation or "날짜 없음"}',
            stock_name=stock_name,
        )

    try:
        elapsed = count_trading_days(designation_date, today_date) - 1
    except Exception as e:
        return False, _forecast_source_error(
            'krx-warning-current-status',
            f'경고 경과 거래일 계산 실패: {safe_exception_text(e)}',
            stock_name=stock_name,
        )

    if elapsed < 10:
        return True, None

    try:
        codes = stock_code(stock_name)
        if not codes:
            return False, _forecast_source_error(
                'krx-warning-current-status',
                '현재 경고 여부 확인용 종목코드를 찾을 수 없습니다.',
                stock_name=stock_name,
            )
        code = codes[0].get('code', '')
        if not code:
            return False, _forecast_source_error(
                'krx-warning-current-status',
                '현재 경고 여부 확인용 종목코드가 비어 있습니다.',
                stock_name=stock_name,
            )
        thresholds = calc_thresholds(fetch_prices(code, count=20))
    except Exception as e:
        return False, _forecast_source_error(
            'krx-warning-current-status',
            f'현재 경고 여부 확인 실패: {safe_exception_text(e)}',
            stock_name=stock_name,
        )

    if 'error' in thresholds:
        return False, _forecast_source_error(
            'krx-warning-current-status',
            thresholds['error'],
            stock_name=stock_name,
        )
    still_active = bool(thresholds.get('cond1') and thresholds.get('cond2') and thresholds.get('cond3'))
    return still_active, None


def _current_warning_candidate_names(
    warning_rows: list,
    candidate_names: set[str],
    today_date: date,
) -> tuple[set[str], list[dict]]:
    current_names: set[str] = set()
    errors: list[dict] = []
    for row in warning_rows:
        stock_name = row.get('stockName', '')
        if stock_name not in candidate_names:
            continue
        if row.get('level') not in {'투자경고', '투자위험'}:
            continue
        still_active, error = _warning_history_still_active(row, today_date)
        if error:
            errors.append(error)
        if still_active:
            current_names.add(stock_name)
    return current_names, errors


def _forecast_item_from_notice(warn: dict, active_notice: dict) -> dict:
    item = _forecast_base_item(warn, active_notice)
    if _notice_requires_internal_review(active_notice):
        return _forecast_needs_review(
            item,
            'KRX 내부 감시 데이터가 필요한 지정예고 유형입니다.',
        )

    codes = stock_code(warn['stockName'])
    if not codes:
        return _forecast_needs_review(item, '종목코드를 찾을 수 없습니다.')

    code_item = codes[0]
    code = code_item.get('code', '')
    naver_market = code_item.get('market', '')
    idx_symbol = _market_to_index_symbol(warn.get('market', '') or naver_market)
    item.update({
        'code': code,
        'market': naver_market or warn.get('market', ''),
        'indexSymbol': idx_symbol,
    })
    if not idx_symbol:
        return _forecast_needs_review(
            item,
            f'시장 구분 판정 실패 ({warn.get("market", "") or naver_market!r})',
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            price_future = pool.submit(fetch_prices, code, count=FORECAST_PRICE_COUNT)
            index_future = pool.submit(fetch_index_prices, idx_symbol, count=FORECAST_PRICE_COUNT)
            prices = price_future.result()
            index_prices = index_future.result()
    except Exception as e:
        return _forecast_needs_review(item, f'주가/지수 조회 불가: {e}')

    escalation = calc_official_escalation(prices, index_prices)
    if 'error' in escalation:
        return _forecast_needs_review(item, escalation['error'])

    signal = build_forecast_signal(escalation)
    item.update({
        'level': signal.get('level', 'watch'),
        'levelLabel': signal.get('levelLabel', '주의보'),
        'riskScore': signal.get('riskScore', 0),
        'calcStatus': 'calculated',
        'calcStatusLabel': signal.get('riskLabel', '계산 완료'),
        'escalation': escalation,
        'forecastSignal': signal,
    })
    return item


def market_alert_forecast_payload() -> dict:
    """KRX 투자경고 지정예고 후보군을 경보/주의보로 보수 분류한다."""
    today_date = _today_kst_date()
    today_kst = today_date.isoformat()
    generated_at = datetime.now(KST).isoformat(timespec='seconds')

    errors: list[dict] = []
    try:
        caution_rows = search_kind_caution('', raise_on_error=True)
    except Exception as e:
        errors.append(_forecast_source_error(
            'krx-caution',
            f'KRX 투자주의/지정예고 조회 실패: {safe_exception_text(e)}',
        ))
        caution_rows = []

    candidates = []
    for warn in caution_rows:
        stock_name = warn.get('stockName', '')
        if not stock_name:
            continue
        active_notice = _active_warning_notice(warn.get('entries', []), today_date)
        if active_notice:
            candidates.append((warn, active_notice))

    candidate_names = {warn.get('stockName', '') for warn, _ in candidates if warn.get('stockName')}
    try:
        warning_rows = search_kind('', raise_on_error=True) if candidate_names else []
    except Exception as e:
        warning_rows = []
        errors.append(_forecast_source_error(
            'krx-warning',
            f'KRX 투자경고/위험 조회 실패: {safe_exception_text(e)}',
        ))
    current_warning_names, warning_status_errors = _current_warning_candidate_names(
        warning_rows,
        candidate_names,
        today_date,
    )
    errors.extend(warning_status_errors)

    excluded_current_warning = 0
    active_candidates = []
    for warn, active_notice in candidates:
        if warn.get('stockName', '') in current_warning_names:
            excluded_current_warning += 1
            continue
        active_candidates.append((warn, active_notice))

    items = []
    with ThreadPoolExecutor(max_workers=FORECAST_MAX_WORKERS) as pool:
        futures = [
            pool.submit(_forecast_item_from_notice, warn, active_notice)
            for warn, active_notice in active_candidates
        ]
        for future in futures:
            try:
                items.append(future.result())
            except Exception as e:
                items.append({
                    'level': 'review',
                    'levelLabel': '확인',
                    'stockName': '',
                    'riskScore': 0,
                    'calcStatus': 'needs_review',
                    'calcStatusLabel': '확인 필요',
                    'calcDetail': str(e),
                    'forecastSignal': {
                        'riskLevel': 'review',
                        'riskLabel': '확인 필요',
                        'riskScore': 0,
                        'primarySignal': str(e),
                        'remainingText': '공개 데이터만으로 자동 판단 불가',
                    },
                })

    level_rank = {'alert': 0, 'near': 1, 'watch': 2, 'review': 3}
    items.sort(key=lambda item: (
        level_rank.get(item.get('level'), 9),
        -int(item.get('riskScore', 0) or 0),
        item.get('lastJudgmentDate', ''),
        item.get('stockName', ''),
    ))
    summary = {
        'total': len(items),
        'alert': sum(1 for item in items if item.get('level') == 'alert'),
        'near': sum(1 for item in items if item.get('level') == 'near'),
        'watch': sum(1 for item in items if item.get('level') == 'watch'),
        'calculated': sum(1 for item in items if item.get('calcStatus') == 'calculated'),
        'needsReview': sum(1 for item in items if item.get('calcStatus') == 'needs_review'),
        'excludedCurrentWarning': excluded_current_warning,
    }
    summary['highRisk'] = summary['alert'] + summary['near']
    return {
        'todayKst': today_kst,
        'generatedAt': generated_at,
        'policy': FORECAST_POLICY,
        'summary': summary,
        'items': items,
        'errors': errors,
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
