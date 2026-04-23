"""간단한 재시도 유틸 (stdlib만 사용) — 지수 백오프."""
import socket
import time
import random
import urllib.error


class RetryableError(RuntimeError):
    """An error that is safe to retry."""

    def __init__(self, message: str, *, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class NonRetryableError(RuntimeError):
    """An error that should fail fast."""


def is_retryable_exception(exc: Exception) -> bool:
    """Default retry classifier for network-facing calls."""
    if isinstance(exc, NonRetryableError):
        return False
    if isinstance(exc, RetryableError):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 425, 429, 500, 502, 503, 504)
    if isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout)):
        return True
    return False


def retry(fn, retries=1, base_delay=0.5, deadline: float | None = None,
          retryable=None, max_delay: float = 8.0, jitter: float = 0.3,
          on_retry=None):
    """fn()을 최대 retries+1회 시도. 실패 시 지수 백오프(+jitter) 후 재시도."""
    retryable = retryable or is_retryable_exception
    for i in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            if (not retryable(exc) or i == retries
                    or (deadline is not None and time.monotonic() >= deadline)):
                raise
            retry_after = getattr(exc, 'retry_after', None)
            if retry_after is not None:
                delay = max(0.0, min(max_delay, float(retry_after)))
            else:
                delay = min(max_delay, base_delay * (2 ** i) + random.uniform(0, jitter))
            if deadline is not None:
                delay = min(delay, max(0, deadline - time.monotonic()))
            if on_retry:
                on_retry(i + 1, delay, exc)
            time.sleep(delay)
