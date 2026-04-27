"""Small stdlib HTTP client for external API calls.

Centralizes headers, retry classification, latency logging, and secret-safe
error messages for DART, KRX, Naver, Gemini, and Telegram.
"""

from email.utils import parsedate_to_datetime
import json
import time
import urllib.error
import urllib.request

from lib.http_utils import log_event, redact_url, safe_exception_text
from lib.retry import NonRetryableError, RetryableError, retry


DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/125.0.0.0 Safari/537.36'
)

JSON_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': DEFAULT_USER_AGENT,
}
BROWSER_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'User-Agent': DEFAULT_USER_AGENT,
}

TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
PROVIDER_TRANSIENT_HTTP_STATUSES = {
    # KIND occasionally returns edge/WAF 403s from Vercel even when the same
    # request succeeds moments later. Treat it as retryable for KRX only.
    'krx': frozenset({403}),
}


class ExternalAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status: int | None = None,
        url: str = '',
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status = status
        self.url = url
        self.retry_after = retry_after


class RetryableHTTPError(ExternalAPIError, RetryableError):
    pass


class NonRetryableHTTPError(ExternalAPIError, NonRetryableError):
    pass


def _retry_after_seconds(headers) -> float | None:
    raw = headers.get('Retry-After') if headers else None
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        return max(0.0, dt.timestamp() - time.time())
    except Exception:
        return None


def _error_from_http_error(provider: str, err: urllib.error.HTTPError, secret_query_keys=()):
    safe_url = redact_url(err.geturl(), secret_query_keys)
    retry_after = _retry_after_seconds(err.headers)
    message = f'{provider} HTTP {err.code} while requesting {safe_url}'
    provider_transient = PROVIDER_TRANSIENT_HTTP_STATUSES.get(provider, frozenset())
    if err.code in TRANSIENT_HTTP_STATUSES or err.code in provider_transient:
        return RetryableHTTPError(
            message,
            provider=provider,
            status=err.code,
            url=safe_url,
            retry_after=retry_after,
        )
    return NonRetryableHTTPError(
        message,
        provider=provider,
        status=err.code,
        url=safe_url,
        retry_after=retry_after,
    )


def request_bytes(
    provider: str,
    url: str,
    *,
    headers: dict | None = None,
    data: bytes | None = None,
    method: str | None = None,
    timeout: float = 10.0,
    retries: int = 1,
    secret_query_keys=(),
) -> bytes:
    """Perform an HTTP request with retry and structured logging."""
    request_headers = dict(headers or {})
    request_headers.setdefault('User-Agent', DEFAULT_USER_AGENT)
    attempts = 0
    rate_waited = 0.0
    start = time.perf_counter()
    safe_url = redact_url(url, secret_query_keys)

    def _call():
        nonlocal attempts, rate_waited
        from lib.provider_rate_limit import throttle

        rate_waited += throttle(provider)
        attempts += 1
        req = urllib.request.Request(
            url,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise _error_from_http_error(provider, e, secret_query_keys) from None
        except urllib.error.URLError as e:
            reason = safe_exception_text(getattr(e, 'reason', type(e).__name__))
            raise RetryableHTTPError(
                f'{provider} request failed for {safe_url}: {reason}',
                provider=provider,
                url=safe_url,
            ) from None

    def _on_retry(attempt, delay, exc):
        log_event(
            'warning',
            'external_api_retry',
            provider=provider,
            url=safe_url,
            attempt=attempt,
            delay=f'{delay:.2f}',
            error=safe_exception_text(exc),
        )

    try:
        body = retry(_call, retries=retries, on_retry=_on_retry)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        log_event(
            'info',
            'external_api_call',
            provider=provider,
            url=safe_url,
            result='success',
            elapsed_ms=elapsed_ms,
            attempts=attempts,
            rate_wait_ms=int(rate_waited * 1000),
            bytes=len(body),
        )
        return body
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status = getattr(e, 'status', '')
        log_event(
            'warning',
            'external_api_call',
            provider=provider,
            url=safe_url,
            result='failure',
            status=status,
            elapsed_ms=elapsed_ms,
            attempts=attempts,
            rate_wait_ms=int(rate_waited * 1000),
            error=safe_exception_text(e),
        )
        raise


def request_text(provider: str, url: str, *, encoding='utf-8', errors='replace', **kwargs) -> str:
    return request_bytes(provider, url, **kwargs).decode(encoding, errors=errors)


def request_json(provider: str, url: str, **kwargs):
    return json.loads(request_bytes(provider, url, **kwargs).decode('utf-8'))
