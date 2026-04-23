"""External-call timeout policy.

Values are per attempt. Retry counts are kept small so the total wall time
fits the Vercel function maxDuration configured for each endpoint.
"""
import os


def _env_float(name: str, default: float, min_value: float, max_value: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


DEFAULT_RETRIES = 1
NO_RETRY = 0

NAVER_CODE_TIMEOUT = _env_float('NAVER_CODE_TIMEOUT', 4.0, 1.0, 10.0)
NAVER_PRICE_TIMEOUT = _env_float('NAVER_PRICE_TIMEOUT', 5.0, 1.0, 12.0)
NAVER_OVERVIEW_TIMEOUT = _env_float('NAVER_OVERVIEW_TIMEOUT', 4.0, 1.0, 10.0)
KRX_KIND_TIMEOUT = _env_float('KRX_KIND_TIMEOUT', 5.0, 1.0, 12.0)

DART_LIST_TIMEOUT = _env_float('DART_LIST_TIMEOUT', 8.0, 2.0, 20.0)
DART_DOCUMENT_TIMEOUT = _env_float('DART_DOCUMENT_TIMEOUT', 20.0, 5.0, 45.0)
DART_FINANCIAL_TIMEOUT = _env_float('DART_FINANCIAL_TIMEOUT', 8.0, 2.0, 20.0)

GEMINI_TIMEOUT = _env_float('GEMINI_TIMEOUT', 45.0, 5.0, 60.0)
TELEGRAM_SEND_TIMEOUT = _env_float('TELEGRAM_SEND_TIMEOUT', 8.0, 2.0, 15.0)

# Provider-wide limiter knobs are kept here for discoverability. The actual
# values are read in lib.provider_rate_limit so tests can modify os.environ.
EXTERNAL_RATE_LIMIT_MAX_WAIT = _env_float(
    'EXTERNAL_RATE_LIMIT_MAX_WAIT',
    5.0,
    0.0,
    60.0,
)
