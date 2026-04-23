"""Provider-wide rate limiting for external APIs.

Uses Upstash Redis when configured, otherwise falls back to per-process fixed
windows. The local fallback is intentionally best effort; it protects warm
instances from bursts but cannot coordinate Vercel cold starts.
"""
import os
import random
import threading
import time

from lib.http_utils import log_event, safe_exception_text
from lib.retry import RetryableError


DEFAULT_PER_MINUTE = {
    'dart': 900,
    # Optional estimate-based budget. Units are 1K tokens per minute.
    'gemini_tokens': 0,
    'krx': 120,
    'naver': 180,
    'gemini': 10,
    'telegram': 900,
}

_local_lock = threading.Lock()
_local_counts: dict[str, tuple[int, float]] = {}


class ProviderRateLimitError(RetryableError):
    def __init__(self, provider: str, retry_after: float):
        super().__init__(
            f'{provider} provider rate limit exceeded',
            retry_after=retry_after,
        )
        self.provider = provider
        self.status = 'local-rate-limit'


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def provider_limit(provider: str) -> int:
    default = DEFAULT_PER_MINUTE.get(provider, 60)
    env_name = f'EXTERNAL_RATE_{provider.upper()}_PER_MINUTE'
    return _env_int(env_name, default, 0, 100000)


def _max_wait() -> float:
    try:
        value = float(os.environ.get('EXTERNAL_RATE_LIMIT_MAX_WAIT', '5'))
    except ValueError:
        return 5.0
    return max(0.0, min(60.0, value))


def _local_increment(key: str, units: int, window_seconds: int) -> int:
    now = time.time()
    with _local_lock:
        count, reset_at = _local_counts.get(key, (0, 0.0))
        if now >= reset_at:
            reset_at = (int(now // window_seconds) + 1) * window_seconds
            count = 0
        count += units
        _local_counts[key] = (count, reset_at)
        return count


def _distributed_increment(key: str, units: int, window_seconds: int) -> int | None:
    try:
        from lib.durable_cache import enabled, incrby_with_expiry
        if not enabled():
            return None
        return incrby_with_expiry(key, units, ttl=window_seconds + 5)
    except Exception as e:
        log_event('warning', 'provider_rate_limit_store_failed',
                  key=key, error=safe_exception_text(e))
        return None


def throttle(provider: str, *, units: int = 1) -> float:
    """Wait or raise before an external API call if the provider budget is used."""
    if not _env_bool('EXTERNAL_RATE_LIMITS_ENABLED', True):
        return 0.0

    provider = (provider or 'unknown').lower()
    limit = provider_limit(provider)
    if limit <= 0:
        return 0.0

    window_seconds = 60
    waited = 0.0
    max_wait = _max_wait()

    while True:
        now = time.time()
        window = int(now // window_seconds)
        reset_at = (window + 1) * window_seconds
        key = f'provider-rate:{provider}:{window}'

        count = _distributed_increment(key, units, window_seconds)
        scope = 'distributed'
        if count is None:
            count = _local_increment(key, units, window_seconds)
            scope = 'local'

        if count <= limit:
            if waited:
                log_event('info', 'provider_rate_limit_resumed',
                          provider=provider, scope=scope,
                          waited=f'{waited:.2f}', count=count, limit=limit)
            return waited

        sleep_for = max(0.0, reset_at - now) + random.uniform(0, 0.25)
        if waited + sleep_for > max_wait:
            log_event('warning', 'provider_rate_limit_exceeded',
                      provider=provider, scope=scope, count=count, limit=limit,
                      retry_after=f'{sleep_for:.2f}', waited=f'{waited:.2f}')
            raise ProviderRateLimitError(provider, sleep_for)

        log_event('warning', 'provider_rate_limit_wait',
                  provider=provider, scope=scope, count=count, limit=limit,
                  sleep=f'{sleep_for:.2f}')
        time.sleep(sleep_for)
        waited += sleep_for
