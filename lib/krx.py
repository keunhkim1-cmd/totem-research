"""KRX KIND 투자경고/위험 종목 검색"""
import urllib.request, urllib.parse, re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from lib.retry import retry
from lib.cache import TTLCache

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kind.krx.co.kr/',
}

# KRX 데이터는 일중 변동이 적으므로 10분 캐시
_krx_cache = TTLCache(ttl=600)


def fetch_kind_page(menu_index: str, page: int = 1) -> str:
    cache_key = f'kind:{menu_index}:{page}:{date.today().isoformat()}'

    def _fetch():
        end_date = date.today().strftime('%Y%m%d')
        start_date = (date.today() - timedelta(days=365)).strftime('%Y%m%d')
        params = urllib.parse.urlencode({
            'method': 'investattentwarnriskySub', 'menuIndex': menu_index,
            'marketType': '', 'searchCorpName': '',
            'startDate': start_date, 'endDate': end_date,
            'pageIndex': str(page), 'currentPageSize': '100',
            'orderMode': '3', 'orderStat': 'D',
        })

        def _call():
            req = urllib.request.Request(
                f'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do?{params}',
                headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as r:
                return r.read().decode('utf-8', errors='replace')

        return retry(_call)

    return _krx_cache.get_or_set(cache_key, _fetch)


def parse_kind_html(html: str, level_name: str) -> list:
    results = []
    tbody_m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
    if not tbody_m:
        return results
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_m.group(1), re.DOTALL):
        name_m = re.search(r'<td\s+title="([^"]+)"', row)
        if not name_m or not name_m.group(1).strip():
            continue
        dates = re.findall(
            r'<td[^>]*class="[^"]*txc[^"]*"[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</td>', row)
        if dates:
            results.append({
                'level': level_name,
                'stockName': name_m.group(1).strip(),
                'designationDate': dates[-1],
            })
    return results


def search_kind(stock_name: str) -> list:
    all_results = []

    # 투자경고/투자위험 두 페이지를 병렬 조회
    def _fetch_level(args):
        idx, level = args
        try:
            html = fetch_kind_page(idx)
            rows = parse_kind_html(html, level)
            if stock_name:
                rows = [r for r in rows if stock_name in r['stockName']]
            return rows
        except Exception as e:
            print(f'KIND error menu={idx}: {e}')
            return []

    with ThreadPoolExecutor(max_workers=2) as pool:
        results_list = list(pool.map(_fetch_level, [('2', '투자경고'), ('3', '투자위험')]))

    for rows in results_list:
        all_results.extend(rows)

    all_results.sort(key=lambda x: x.get('designationDate', ''), reverse=True)
    # 종목+레벨별 최근 경고만 유지 (같은 종목이 경고/위험 동시 지정 가능)
    seen = set()
    deduped = []
    for r in all_results:
        key = (r['stockName'], r['level'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped
