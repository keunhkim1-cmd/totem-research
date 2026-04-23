"""Shared DART Open API request helpers."""
import os
import random
import time

from lib.http_client import JSON_HEADERS, request_bytes, request_json
from lib.http_utils import build_url, log_event
from lib.timeouts import DART_DOCUMENT_TIMEOUT, DART_LIST_TIMEOUT

DART_BASE = 'https://opendart.fss.or.kr/api'
DART_HEADERS = dict(JSON_HEADERS)
DART_SECRET_PARAMS = ('crtfc_key',)
DART_RETRYABLE_STATUSES = frozenset({'800', '900'})


def api_key() -> str:
    key = os.environ.get('DART_API_KEY', '').strip()
    if not key:
        raise ValueError('DART_API_KEY 환경변수가 설정되지 않았습니다.')
    return key


def dart_url(path: str, params: dict | None = None) -> str:
    query = {'crtfc_key': api_key()}
    if params:
        query.update(params)
    return build_url(DART_BASE, path, query)


def fetch_json(path: str, params: dict | None = None, timeout: float = DART_LIST_TIMEOUT,
               retries: int = 1) -> dict:
    request_url = dart_url(path, params)
    last_data = None
    for attempt in range(retries + 1):
        data = request_json(
            'dart',
            request_url,
            headers=DART_HEADERS,
            timeout=timeout,
            retries=0,
            secret_query_keys=DART_SECRET_PARAMS,
        )
        last_data = data
        status = str(data.get('status', ''))
        if status in DART_RETRYABLE_STATUSES and attempt < retries:
            delay = 0.5 * (2 ** attempt) + random.uniform(0, 0.3)
            log_event(
                'warning',
                'dart_api_status_retry',
                path=path,
                status=status,
                attempt=attempt + 1,
                delay=f'{delay:.2f}',
                message=data.get('message', ''),
            )
            time.sleep(delay)
            continue
        return data
    return last_data or {}


def fetch_bytes(path: str, params: dict | None = None,
                timeout: float = DART_DOCUMENT_TIMEOUT, retries: int = 1) -> bytes:
    request_url = dart_url(path, params)
    return request_bytes(
        'dart',
        request_url,
        headers=DART_HEADERS,
        timeout=timeout,
        retries=retries,
        secret_query_keys=DART_SECRET_PARAMS,
    )
