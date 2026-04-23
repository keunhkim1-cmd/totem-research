"""네이버 금융 — 종목코드 검색 & 일별 주가 조회"""
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone, timedelta
from xml.etree import ElementTree as ET

from lib.cache import TTLCache
from lib.http_client import JSON_HEADERS, request_json, request_text
from lib.timeouts import NAVER_CODE_TIMEOUT, NAVER_OVERVIEW_TIMEOUT, NAVER_PRICE_TIMEOUT

KST = timezone(timedelta(hours=9))

HEADERS = {
    **JSON_HEADERS,
    'Referer': 'https://finance.naver.com/',
}

# 종목코드는 잘 바뀌지 않으므로 서버 내부 캐시는 길게 유지
_code_cache = TTLCache(ttl=24 * 3600, name='naver-code', durable=True)
# 주가는 장중 변동하므로 2분 캐시
_price_cache = TTLCache(ttl=120)


def stock_code(name: str) -> list:
    """종목명 → [{'code': '...', 'name': '...', 'market': '...'}, ...]"""
    def _fetch():
        params = urllib.parse.urlencode({'q': name, 'target': 'stock'})

        def _call():
            data = request_json(
                'naver',
                f'https://ac.stock.naver.com/ac?{params}',
                headers=JSON_HEADERS,
                timeout=NAVER_CODE_TIMEOUT,
                retries=1,
            )
            return [{'code': it['code'], 'name': it['name'],
                     'market': it.get('typeName', '')} for it in data.get('items', [])]

        return _call()

    return _code_cache.get_or_set(
        f'code:{name}',
        _fetch,
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )


def fetch_prices(code: str, count: int = 20) -> list:
    """종목코드 → 일별 종가 리스트 (시간순: 오래된→최신) [{'date': 'YYYY-MM-DD', 'close': int}, ...]"""
    def _fetch():
        url = (f'https://fchart.stock.naver.com/sise.nhn'
               f'?symbol={code}&timeframe=day&count={count}&requestType=0')

        def _call():
            raw = request_text(
                'naver',
                url,
                headers=HEADERS,
                timeout=NAVER_PRICE_TIMEOUT,
                retries=1,
                encoding='euc-kr',
                errors='replace',
            )
            root = ET.fromstring(raw)
            prices = []
            for item in root.iter('item'):
                parts = item.get('data', '').split('|')
                if len(parts) < 5 or not parts[4] or parts[4] == '0':
                    continue
                d = parts[0]
                prices.append({'date': f'{d[:4]}-{d[4:6]}-{d[6:8]}', 'close': int(parts[4])})
            return prices

        return _call()

    return _price_cache.get_or_set(
        f'price:{code}:{count}',
        _fetch,
        allow_stale_on_error=True,
        max_stale=300,
    )


def fetch_index_prices(symbol: str, count: int = 20) -> list:
    """종합주가지수(KOSPI/KOSDAQ) 일별 종가 — float 보존."""
    def _fetch():
        url = (f'https://fchart.stock.naver.com/sise.nhn'
               f'?symbol={symbol}&timeframe=day&count={count}&requestType=0')

        def _call():
            raw = request_text(
                'naver',
                url,
                headers=HEADERS,
                timeout=NAVER_PRICE_TIMEOUT,
                retries=1,
                encoding='euc-kr',
                errors='replace',
            )
            root = ET.fromstring(raw)
            prices = []
            for item in root.iter('item'):
                parts = item.get('data', '').split('|')
                if len(parts) < 5 or not parts[4]:
                    continue
                try:
                    close = float(parts[4])
                except ValueError:
                    continue
                if close == 0:
                    continue
                d = parts[0]
                prices.append({'date': f'{d[:4]}-{d[4:6]}-{d[6:8]}', 'close': close})
            return prices

        return _call()

    return _price_cache.get_or_set(
        f'idx:{symbol}:{count}',
        _fetch,
        allow_stale_on_error=True,
        max_stale=300,
    )


_overview_cache = TTLCache(ttl=120)


def fetch_stock_overview(code: str) -> dict:
    """종목코드 → 시가총액·PER·PBR·52주 고저 등 기업 개요"""
    def _fetch():
        url = f'https://m.stock.naver.com/api/stock/{code}/integration'

        def _call():
            data = request_json(
                'naver',
                url,
                headers=JSON_HEADERS,
                timeout=NAVER_OVERVIEW_TIMEOUT,
                retries=1,
            )
            infos = {it['code']: it['value'] for it in (data.get('totalInfos') or [])}
            deals = data.get('dealTrendInfos') or []
            close_price = deals[0].get('closePrice', '-') if deals else '-'
            return {
                'stockName': data.get('stockName', ''),
                'closePrice': close_price,                             # 현재가(당일종가)
                'marketCap': infos.get('marketValue', '-'),            # 시가총액
                'per': infos.get('per', '-'),
                'pbr': infos.get('pbr', '-'),
                'eps': infos.get('eps', '-'),
                'bps': infos.get('bps', '-'),
                'dividendYield': infos.get('dividendYieldRatio', '-'), # 배당수익률
                'high52w': infos.get('highPriceOf52Weeks', '-'),       # 52주 최고
                'low52w': infos.get('lowPriceOf52Weeks', '-'),         # 52주 최저
                'foreignRate': infos.get('foreignRate', '-'),          # 외인소진율
                'volume': infos.get('accumulatedTradingVolume', '-'),  # 거래량
                'tradingValue': infos.get('accumulatedTradingValue', '-'),  # 거래대금
            }

        return _call()

    return _overview_cache.get_or_set(
        f'overview:{code}',
        _fetch,
        allow_stale_on_error=True,
        max_stale=600,
    )


def calc_thresholds(prices: list) -> dict:
    """시간순(오래된→최신) 가격 리스트 → 3가지 기준가 + 충족 여부
    prices[-1]=최신(오늘), prices[-6]=5거래일 전, prices[-16]=15거래일 전"""
    if len(prices) < 16:
        return {'error': f'데이터 부족 ({len(prices)}일치, 최소 16일 필요)'}
    t_close, t_date = prices[-1]['close'], prices[-1]['date']
    t5_close, t5_date = prices[-6]['close'], prices[-6]['date']
    t15_close, t15_date = prices[-16]['close'], prices[-16]['date']
    recent15 = prices[-15:]
    max15 = max(p['close'] for p in recent15)
    max15_date = next(p['date'] for p in recent15 if p['close'] == max15)
    thresh1 = round(t5_close * 1.45)
    thresh2 = round(t15_close * 1.75)
    thresh3 = max15
    cond1, cond2, cond3 = t_close >= thresh1, t_close >= thresh2, t_close >= thresh3
    return {
        'tClose': t_close, 'tDate': t_date,
        't5Close': t5_close, 't5Date': t5_date, 'thresh1': thresh1, 'cond1': cond1,
        't15Close': t15_close, 't15Date': t15_date, 'thresh2': thresh2, 'cond2': cond2,
        'max15': max15, 'max15Date': max15_date, 'thresh3': thresh3, 'cond3': cond3,
        'allMet': cond1 and cond2 and cond3,
    }


# 시장명(한글/영문) → 네이버 fchart 지수 심볼
def _market_to_index_symbol(market: str) -> str:
    if not market:
        return ''
    m = market.upper()
    if 'KOSDAQ' in m or '코스닥' in market:
        return 'KOSDAQ'
    if 'KOSPI' in m or '코스피' in market or '유가증권' in market:
        return 'KOSPI'
    return ''


def calc_official_escalation(stock_prices: list, index_prices: list) -> dict:
    """KRX 공식 [1] 단기급등 / [2] 중장기급등 조건 점검.

    [1] 단기급등(모두 해당): ① T/T-5 ≥ 1.60  ② T가 최근 15일 최고 종가  ③ 상승률 ≥ 지수 상승률 × 5
    [2] 중장기급등(모두 해당): ① T/T-15 ≥ 2.00  ② T가 최근 15일 최고 종가  ③ 상승률 ≥ 지수 상승률 × 3
    [1] 또는 [2] 중 하나 이상의 세트가 모두 충족되면 투자경고 지정 예상.

    stock_prices: 오래된→최신, int 종가.
    index_prices: 오래된→최신, float 종가 (같은 날짜들이 다 있어야 함).
    """
    if len(stock_prices) < 16:
        return {'error': f'주가 데이터 부족 ({len(stock_prices)}일치, 최소 16일 필요)'}
    if len(index_prices) < 16:
        return {'error': f'지수 데이터 부족 ({len(index_prices)}일치, 최소 16일 필요)'}

    # 날짜 정렬 — 최신(T)이 같아야 함. 다르면 판단 보류.
    t_date_s = stock_prices[-1]['date']
    t_date_i = index_prices[-1]['date']
    if t_date_s != t_date_i:
        return {'error': f'종목/지수 최신 날짜 불일치 ({t_date_s} vs {t_date_i})'}

    t_close = stock_prices[-1]['close']
    t_idx   = index_prices[-1]['close']
    t5      = stock_prices[-6]
    t15     = stock_prices[-16]
    t5_idx  = index_prices[-6]
    t15_idx = index_prices[-16]

    recent15 = stock_prices[-15:]
    max15 = max(p['close'] for p in recent15)
    max15_date = next(p['date'] for p in recent15 if p['close'] == max15)
    is_max15 = t_close >= max15  # 당일 포함 15일 최고 (>= 로 허용)

    def _set(mult_price: float, base_s: dict, base_i: dict, mult_idx: float, label_prefix: str, window_lbl: str):
        stock_ret = (t_close - base_s['close']) / base_s['close']
        idx_ret   = (t_idx   - base_i['close']) / base_i['close']
        threshold_price = round(base_s['close'] * mult_price)
        cond1 = t_close >= threshold_price
        cond2 = is_max15
        cond3 = stock_ret >= mult_idx * idx_ret
        all_met = cond1 and cond2 and cond3
        return {
            'label': label_prefix,
            'window': window_lbl,
            'baseDate': base_s['date'],
            'baseClose': base_s['close'],
            'thresholdPrice': threshold_price,
            'priceMultiplier': mult_price,
            'stockReturn': stock_ret,
            'indexBaseClose': base_i['close'],
            'indexReturn': idx_ret,
            'indexMultiplier': mult_idx,
            'conditions': [
                {'key': 'priceRise',  'label': f'{window_lbl} 대비 {int((mult_price-1)*100)}% 이상 상승',
                 'met': cond1,
                 'detail': f'T={t_close:,}원 vs 기준가 {threshold_price:,}원 (상승률 {stock_ret*100:.1f}%)'},
                {'key': 'max15',      'label': '당일 종가가 최근 15일 최고 종가',
                 'met': cond2,
                 'detail': f'T={t_close:,}원 vs 최고 {max15:,}원 ({max15_date})'},
                {'key': 'vsIndex',    'label': f'상승률이 지수 상승률의 {int(mult_idx)}배 이상',
                 'met': cond3,
                 'detail': f'종목 {stock_ret*100:+.1f}% vs 지수 {idx_ret*100:+.2f}%×{int(mult_idx)} = {idx_ret*mult_idx*100:+.2f}%'},
            ],
            'allMet': all_met,
        }

    set1 = _set(1.60, t5,  t5_idx,  5, '[1] 단기급등',   'T-5')
    set2 = _set(2.00, t15, t15_idx, 3, '[2] 중장기급등', 'T-15')

    verdict = 'strong' if (set1['allMet'] or set2['allMet']) else 'none'

    return {
        'tClose': t_close,
        'tDate': t_date_s,
        'indexClose': t_idx,
        'max15': max15,
        'max15Date': max15_date,
        'sets': [set1, set2],
        'headline': {
            'verdict': verdict,
            'matchedSet': 0 if set1['allMet'] else (1 if set2['allMet'] else None),
        },
    }


def caution_search(name: str) -> dict:
    """투자주의 → 투자경고 격상 여부 점검 (웹 API).

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
    # lib.krx / lib.holidays 는 런타임에 import — 순환 import 회피
    from lib.krx import search_kind_caution
    from lib.holidays import add_trading_days, count_trading_days

    today_kst = datetime.now(KST).date().isoformat()
    name = (name or '').strip()
    if not name:
        return {'status': 'not_caution', 'query': '', 'todayKst': today_kst}

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
            # 오늘이 몇 번째 판단일인지 (예고일 포함 거래일수 − 1)
            try:
                elapsed = count_trading_days(notice_date, today_date) - 1
            except Exception:
                elapsed = 0
            active_notice = {
                'noticeDate': e['date'],
                'firstJudgmentDate': first_judgment.isoformat(),
                'lastJudgmentDate': last_judgment.isoformat(),
                'judgmentDayIndex': max(0, elapsed),  # 0=예고 당일, 1=첫 판단일…
                'judgmentWindowTotal': 10,
            }
            break

    krx_market = warn.get('market', '')
    latest_reason = warn.get('latestDesignationReason', '')
    latest_date   = warn.get('latestDesignationDate', '')

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

    # 활성 지정예고 없음 → 오늘 지정된 다른 사유가 있으면 안내, 없으면 not_caution
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
