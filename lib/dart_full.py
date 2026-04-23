"""DART 전체 재무제표 (fnlttSinglAcntAll) 어댑터"""
from lib.cache import TTLCache
from lib.dart_base import fetch_json
from lib.http_utils import log_event
from lib.retry import RetryableError
from lib.timeouts import DART_FINANCIAL_TIMEOUT, NO_RETRY

# 6시간 캐시 — 사업보고서는 자주 바뀌지 않음
_cache = TTLCache(ttl=6 * 3600, name='dart-full', durable=True)
_CACHEABLE_STATUSES = frozenset({'000', '013'})
_TRANSIENT_STATUSES = frozenset({'020', '800', '900'})

def fetch_all(corp_code: str, bsns_year: str, reprt_code: str, fs_div: str = 'CFS') -> dict:
    """전체 재무제표 조회.
    reprt_code: 11011=사업보고서, 11014=반기, 11012=1Q, 11013=3Q
    fs_div: CFS=연결, OFS=별도
    """
    key = f'all:{corp_code}:{bsns_year}:{reprt_code}:{fs_div}'
    cached = _cache.get(key)
    if cached is not None:
        return cached

    def _fetch():
        params = {
            'corp_code': corp_code,
            'bsns_year': bsns_year,
            'reprt_code': reprt_code,
            'fs_div': fs_div,
        }
        return fetch_json(
            'fnlttSinglAcntAll.json',
            params,
            timeout=DART_FINANCIAL_TIMEOUT,
            retries=NO_RETRY,
        )

    try:
        data = _fetch()
        status = str(data.get('status', ''))
        if status in _CACHEABLE_STATUSES:
            _cache.set(key, data)
        elif status in _TRANSIENT_STATUSES:
            log_event('warning', 'dart_financial_transient_status',
                      corp_code=corp_code, bsns_year=bsns_year,
                      reprt_code=reprt_code, status=status,
                      message=data.get('message', ''))
            raise RetryableError(f'DART transient status {status}')
        return data
    except Exception:
        stale, state = _cache.get_with_meta(
            key,
            allow_stale=True,
            max_stale=7 * 24 * 3600,
        )
        if state == 'stale':
            log_event('warning', 'dart_financial_stale_returned',
                      corp_code=corp_code, bsns_year=bsns_year,
                      reprt_code=reprt_code)
            return stale
        raise
