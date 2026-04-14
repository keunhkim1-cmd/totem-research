"""네이버 금융 — 종목코드 검색 & 일별 주가 조회"""
import urllib.request, urllib.parse, json
from xml.etree import ElementTree as ET

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Referer': 'https://finance.naver.com/',
}


def stock_code(name: str) -> list:
    """종목명 → [{'code': '...', 'name': '...', 'market': '...'}, ...]"""
    params = urllib.parse.urlencode({'q': name, 'target': 'stock'})
    req = urllib.request.Request(
        f'https://ac.stock.naver.com/ac?{params}',
        headers={'User-Agent': HEADERS['User-Agent']})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode('utf-8'))
    return [{'code': it['code'], 'name': it['name'],
             'market': it.get('typeName', '')} for it in data.get('items', [])]


def fetch_prices(code: str, count: int = 20) -> list:
    """종목코드 → 일별 종가 리스트 (최신순) [{'date': 'YYYY-MM-DD', 'close': int}, ...]"""
    url = (f'https://fchart.stock.naver.com/sise.nhn'
           f'?symbol={code}&timeframe=day&count={count}&requestType=0')
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
    prices.reverse()
    return prices


def calc_thresholds(prices: list) -> dict:
    """최신순 가격 리스트 → 3가지 기준가 + 충족 여부"""
    if len(prices) < 16:
        return {'error': f'데이터 부족 ({len(prices)}일치, 최소 16일 필요)'}
    t_close, t_date = prices[0]['close'], prices[0]['date']
    t5_close, t5_date = prices[5]['close'], prices[5]['date']
    t15_close, t15_date = prices[15]['close'], prices[15]['date']
    recent15 = prices[:15]
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
