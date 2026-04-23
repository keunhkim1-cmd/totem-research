"""KRX KIND 투자경고/위험 종목 검색"""
import urllib.parse, re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from lib.cache import TTLCache
from lib.holidays import count_trading_days
from lib.http_client import BROWSER_HEADERS, request_text
from lib.http_utils import log_event, safe_exception_text
from lib.timeouts import KRX_KIND_TIMEOUT

HEADERS = {
    **BROWSER_HEADERS,
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kind.krx.co.kr/',
}

# KRX 데이터는 일중 변동이 적으므로 10분 캐시
_krx_cache = TTLCache(ttl=600, name='krx-kind', durable=True)


def fetch_kind_page(menu_index: str, page: int = 1, days_back: int = 365, page_size: int = 100) -> str:
    cache_key = f'kind:{menu_index}:{page}:{days_back}:{page_size}:{date.today().isoformat()}'

    def _fetch():
        end_date = date.today().strftime('%Y%m%d')
        start_date = (date.today() - timedelta(days=days_back)).strftime('%Y%m%d')
        params = urllib.parse.urlencode({
            'method': 'investattentwarnriskySub', 'menuIndex': menu_index,
            'marketType': '', 'searchCorpName': '',
            'startDate': start_date, 'endDate': end_date,
            'pageIndex': str(page), 'currentPageSize': str(page_size),
            'orderMode': '3', 'orderStat': 'D',
        })

        def _call():
            return request_text(
                'krx',
                f'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do?{params}',
                headers=HEADERS,
                timeout=KRX_KIND_TIMEOUT,
                retries=1,
                encoding='utf-8',
                errors='replace',
            )

        return _call()

    return _krx_cache.get_or_set(
        cache_key,
        _fetch,
        allow_stale_on_error=True,
        max_stale=3600,
    )


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
            log_event('warning', 'krx_kind_fetch_failed',
                      menu_index=idx, error=safe_exception_text(e))
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


def search_kind_caution(stock_name: str) -> list:
    """투자주의(menuIndex=1) 페이지에서 stock_name 부분일치 종목의 지정 이력 집계.

    반환 각 항목:
      {'stockName', 'latestDesignationDate', 'latestDesignationReason',
       'market', 'recent15dCount', 'allDates': [YYYY-MM-DD, ...]}
    - `latestDesignationReason`: 최신 지정의 사유 (예: '투자경고 지정예고', '소수계좌 매수관여 과다' 등)
    - `market`: 시장 구분 ('KOSPI' | 'KOSDAQ' | '')  — 행의 아이콘(icn_t_yu/icn_t_ko)으로 판정
    - `recent15dCount`: 오늘 포함 15거래일 윈도우 안의 지정 행 수 (참고용)
    """
    # 투자주의는 일일 지정 건수가 많아(일 20~40건) 기본 pageSize=100으로는
    # 페이지 1에 오래된 데이터만 들어온다. 21일치를 한 번에 받도록 pageSize를 키운다.
    try:
        html = fetch_kind_page('1', days_back=21, page_size=1000)
    except Exception as e:
        log_event('warning', 'krx_caution_fetch_failed',
                  error=safe_exception_text(e))
        return []

    # rows_by_stock[name] = [(date_str, reason, market), ...]
    rows_by_stock: dict[str, list[tuple]] = {}
    tbody_m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
    if not tbody_m:
        return []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_m.group(1), re.DOTALL):
        name_m = re.search(r'<td\s+title="([^"]+)"', row)
        if not name_m or not name_m.group(1).strip():
            continue
        dates = re.findall(
            r'<td[^>]*class="[^"]*txc[^"]*"[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</td>', row)
        if not dates:
            continue
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        reason = ''
        if len(tds) >= 3:
            reason = re.sub(r'<[^>]+>', '', tds[2]).strip()
        if 'icn_t_yu' in row:
            market = 'KOSPI'
        elif 'icn_t_ko' in row:
            market = 'KOSDAQ'
        else:
            market = ''
        name = name_m.group(1).strip()
        if stock_name and stock_name not in name:
            continue
        rows_by_stock.setdefault(name, []).append((dates[-1], reason, market))

    today = date.today()
    results = []
    for name, row_entries in rows_by_stock.items():
        row_entries.sort(key=lambda e: e[0], reverse=True)
        entry_list = [{'date': d, 'reason': r} for (d, r, _) in row_entries]
        sorted_dates = [e['date'] for e in entry_list]
        recent15 = 0
        for d_str in sorted_dates:
            try:
                d_obj = date.fromisoformat(d_str)
            except ValueError:
                continue
            if count_trading_days(d_obj, today) <= 15:
                recent15 += 1
        latest_date, latest_reason, latest_market = row_entries[0]
        results.append({
            'stockName': name,
            'latestDesignationDate': latest_date,
            'latestDesignationReason': latest_reason,
            'market': latest_market,
            'recent15dCount': recent15,
            'allDates': sorted_dates,
            'entries': entry_list,  # [{'date': 'YYYY-MM-DD', 'reason': '...'}, ...] 최신→과거
        })

    results.sort(key=lambda x: x['latestDesignationDate'], reverse=True)
    return results
