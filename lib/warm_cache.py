"""Scheduled cache warming use case."""
import time
from datetime import datetime, timezone

from lib.dart_corp import find_corp_by_stock_code
from lib.durable_cache import delete, enabled as durable_cache_enabled, set_json_nx
from lib.http_utils import log_event, safe_exception_text
from lib.krx import search_kind, search_kind_caution
from lib.naver import fetch_index_prices, fetch_prices, stock_code
from lib.usecases import market_alert_forecast_payload


LOCK_KEY = 'cron:warm-cache:lock'
LOCK_TTL_SECONDS = 15 * 60


def _claim_lock() -> tuple[str, str]:
    if not durable_cache_enabled():
        return 'unavailable', ''
    try:
        claimed = set_json_nx(
            LOCK_KEY,
            {'startedAt': datetime.now(timezone.utc).isoformat()},
            ttl=LOCK_TTL_SECONDS,
        )
    except Exception as e:
        return 'error', safe_exception_text(e)
    return ('claimed', '') if claimed else ('busy', '')


def _release_lock() -> None:
    try:
        delete(LOCK_KEY)
    except Exception:
        pass


def _run_task(name: str, fn) -> dict:
    t0 = time.time()
    try:
        result = fn()
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            'name': name,
            'ok': True,
            'elapsedMs': elapsed_ms,
            'result': result,
        }
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        message = safe_exception_text(e)
        log_event('warning', 'warm_cache_task_failed',
                  task=name, elapsed_ms=elapsed_ms, error=message)
        return {
            'name': name,
            'ok': False,
            'elapsedMs': elapsed_ms,
            'error': message,
        }


def warm_cache() -> list[dict]:
    tasks = [
        ('krx-warning-risky', lambda: {'items': len(search_kind(''))}),
        ('krx-caution', lambda: {'items': len(search_kind_caution(''))}),
        ('market-alert-forecast', lambda: market_alert_forecast_payload()['summary']),
        ('naver-code-samsung', lambda: {'items': len(stock_code('삼성전자'))}),
        ('naver-price-samsung', lambda: {'items': len(fetch_prices('005930', count=30))}),
        ('naver-index-kospi', lambda: {'items': len(fetch_index_prices('KOSPI', count=30))}),
        ('naver-index-kosdaq', lambda: {'items': len(fetch_index_prices('KOSDAQ', count=30))}),
        ('dart-corp-map', lambda: {'found': bool(find_corp_by_stock_code('005930'))}),
    ]
    return [_run_task(name, fn) for name, fn in tasks]


def run_warm_cache_job() -> tuple[int, dict]:
    lock_state, lock_error = _claim_lock()
    if lock_state == 'busy':
        return 202, {
            'ok': True,
            'skipped': True,
            'reason': 'warm cache job already running',
        }
    if lock_state == 'error':
        log_event('warning', 'warm_cache_lock_failed', error=lock_error)

    t0 = time.time()
    try:
        results = warm_cache()
    finally:
        if lock_state == 'claimed':
            _release_lock()

    success = all(item.get('ok') for item in results)
    payload = {
        'ok': success,
        'lock': lock_state,
        'elapsedMs': int((time.time() - t0) * 1000),
        'tasks': results,
    }
    log_event('info', 'warm_cache_completed',
              ok=success, elapsed_ms=payload['elapsedMs'],
              lock=lock_state)
    return 200, payload
