"""네이버 금융 — 종목코드 검색 & 일별 주가 조회"""
import urllib.request, urllib.parse, json
from xml.etree import ElementTree as ET

from lib.retry import retry
from lib.cache import TTLCache

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Referer': 'https://finance.naver.com/',
}

# 종목코드는 잘 바뀌지 않으므로 10분 캐시
_code_cache = TTLCache(ttl=600)
# 주가는 장중 변동하므로 2분 캐시
_price_cache = TTLCache(ttl=120)


def stock_code(name: str) -> list:
    """종목명 → [{'code': '...', 'name': '...', 'market': '...'}, ...]"""
    def _fetch():
        params = urllib.parse.urlencode({'q': name, 'target': 'stock'})

        def _call():
            req = urllib.request.Request(
                f'https://ac.stock.naver.com/ac?{params}',
                headers={'User-Agent': HEADERS['User-Agent']})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode('utf-8'))
            return [{'code': it['code'], 'name': it['name'],
                     'market': it.get('typeName', '')} for it in data.get('items', [])]

        return retry(_call)

    return _code_cache.get_or_set(f'code:{name}', _fetch)


def fetch_prices(code: str, count: int = 20) -> list:
    """종목코드 → 일별 종가 리스트 (시간순: 오래된→최신) [{'date': 'YYYY-MM-DD', 'close': int}, ...]"""
    def _fetch():
        url = (f'https://fchart.stock.naver.com/sise.nhn'
               f'?symbol={code}&timeframe=day&count={count}&requestType=0')

        def _call():
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read().decode('euc-kr', errors='replace')
            root = ET.fromstring(raw)
            prices = []
            for item in root.iter('item'):
                parts = item.get('data', '').split('|')
                if len(parts) < 5 or not parts[4] or parts[4] == '0':
                    continue
                d = parts[0]
                prices.append({'date': f'{d[:4]}-{d[4:6]}-{d[6:8]}', 'close': int(parts[4])})
            return prices

        return retry(_call)

    return _price_cache.get_or_set(f'price:{code}:{count}', _fetch)


_overview_cache = TTLCache(ttl=120)


def fetch_stock_overview(code: str) -> dict:
    """종목코드 → 시가총액·PER·PBR·52주 고저 등 기업 개요"""
    def _fetch():
        url = f'https://m.stock.naver.com/api/stock/{code}/integration'

        def _call():
            req = urllib.request.Request(url, headers={'User-Agent': HEADERS['User-Agent']})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode('utf-8'))
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

        return retry(_call)

    return _overview_cache.get_or_set(f'overview:{code}', _fetch)


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
