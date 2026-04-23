"""DART Open API — 공시 검색 & 재무제표 조회"""
from lib.dart_base import fetch_json
from lib.timeouts import DART_LIST_TIMEOUT


def search_disclosure(corp_code: str = '', bgn_de: str = '', end_de: str = '',
                      page_no: int = 1, page_count: int = 20,
                      pblntf_ty: str = '') -> dict:
    """공시 목록 검색 (corp_code 기반)"""
    params = {
        'page_no': str(page_no),
        'page_count': str(page_count),
    }
    if corp_code:
        params['corp_code'] = corp_code
    if bgn_de:
        params['bgn_de'] = bgn_de
    if end_de:
        params['end_de'] = end_de
    if pblntf_ty:
        params['pblntf_ty'] = pblntf_ty

    return fetch_json('list.json', params, timeout=DART_LIST_TIMEOUT, retries=1)
