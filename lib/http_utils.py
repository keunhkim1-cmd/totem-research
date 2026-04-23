"""HTTP helpers for requests, responses, and safe error reporting."""
import json
import os
import re
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


DEFAULT_SECRET_QUERY_KEYS = frozenset({
    'access_token',
    'api_key',
    'apikey',
    'crtfc_key',
    'key',
    'token',
})

SECRET_ENV_NAMES = (
    'CACHE_ADMIN_TOKEN',
    'DART_API_KEY',
    'ECOS_API_KEY',
    'FINANCIAL_MODEL_API_TOKEN',
    'GEMINI_API_KEY',
    'KRX_API_KEY',
    'SUPABASE_ANON_KEY',
    'SUPABASE_KEY',
    'SUPABASE_SERVICE_ROLE_KEY',
    'TELEGRAM_BOT_TOKEN',
    'TELEGRAM_WEBHOOK_SECRET',
    'UPSTASH_REDIS_REST_TOKEN',
)

_TELEGRAM_BOT_TOKEN_RE = re.compile(r'(/bot)([^/?#]+)')
_ORIGIN_RE = re.compile(r'^https?://[A-Za-z0-9.-]+(?::\d{1,5})?$')

DEFAULT_ALLOWED_ORIGINS = (
    'https://shamanism-research.vercel.app',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
)

STATIC_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "script-src-attr 'none'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

API_CSP = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"
PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), payment=(), usb=()'


def _configured_allowed_origins() -> tuple[str, ...]:
    raw = os.environ.get('ALLOWED_ORIGINS') or os.environ.get('ALLOWED_ORIGIN', '')
    values = [v.strip().rstrip('/') for v in raw.split(',') if v.strip()]
    if not values:
        values = list(DEFAULT_ALLOWED_ORIGINS)
    return tuple(v for v in values if v != '*' and _ORIGIN_RE.fullmatch(v))


def cors_origin(request_origin: str | None) -> str | None:
    """Return the exact allowed CORS origin for a request, if any."""
    allowed = _configured_allowed_origins()
    origin = (request_origin or '').strip().rstrip('/')
    if origin:
        return origin if origin in allowed else None
    return None


def send_security_headers(handler, *, csp: str = API_CSP):
    """Attach browser hardening headers common to API and static responses."""
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('Content-Security-Policy', csp)
    handler.send_header('Permissions-Policy', PERMISSIONS_POLICY)


def send_cors_headers(handler, *, methods='GET, OPTIONS', allow_headers=None):
    origin = cors_origin(handler.headers.get('Origin'))
    if origin:
        handler.send_header('Access-Control-Allow-Origin', origin)
    handler.send_header('Vary', 'Origin')
    handler.send_header('Access-Control-Allow-Methods', methods)
    if allow_headers:
        handler.send_header('Access-Control-Allow-Headers', allow_headers)
    handler.send_header('Access-Control-Max-Age', '600')


def send_json_headers(handler, *, cors=True, methods='GET, OPTIONS',
                      allow_headers=None, cache_control=None):
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    if cors:
        send_cors_headers(handler, methods=methods, allow_headers=allow_headers)
    if cache_control:
        handler.send_header('Cache-Control', cache_control)
    send_security_headers(handler)


def send_text_headers(handler, *, cors=False, methods='GET, OPTIONS',
                      allow_headers=None, cache_control='no-store'):
    handler.send_header('Content-Type', 'text/plain; charset=utf-8')
    if cors:
        send_cors_headers(handler, methods=methods, allow_headers=allow_headers)
    if cache_control:
        handler.send_header('Cache-Control', cache_control)
    send_security_headers(handler)


def send_options_response(handler, *, methods='GET, OPTIONS', allow_headers=None):
    handler.send_response(204)
    send_cors_headers(handler, methods=methods, allow_headers=allow_headers)
    send_security_headers(handler)
    handler.send_header('Content-Length', '0')
    handler.end_headers()


def api_success_payload(payload: dict | None = None) -> dict:
    """Return a success payload without breaking existing top-level fields."""
    out = dict(payload or {})
    out.setdefault('ok', True)
    return out


def api_error_payload(code: str, message: str, *, details=None,
                      legacy_key: str | None = 'error',
                      status_value: str | None = None) -> dict:
    """Build the transitional API error shape.

    New clients should read errorInfo. Existing clients may still read the
    legacy top-level `error` or `errorMessage` string during migration.
    """
    payload = {
        'ok': False,
        'errorInfo': {
            'code': code,
            'message': message,
        },
    }
    if details is not None:
        payload['errorInfo']['details'] = details
    if legacy_key:
        payload[legacy_key] = message
    if status_value:
        payload['status'] = status_value
    return payload


def send_json_response(handler, status: int, payload: dict, *, cors=True,
                       methods='GET, OPTIONS', allow_headers=None,
                       cache_control=None):
    body = json.dumps(payload, ensure_ascii=False).encode()
    handler.send_response(status)
    send_json_headers(
        handler,
        cors=cors,
        methods=methods,
        allow_headers=allow_headers,
        cache_control=cache_control,
    )
    handler.end_headers()
    handler.wfile.write(body)


def send_api_error(handler, status: int, code: str, message: str, *, details=None,
                   legacy_key: str | None = 'error',
                   status_value: str | None = None,
                   cors=True, methods='GET, OPTIONS', allow_headers=None,
                   cache_control=None):
    send_json_response(
        handler,
        status,
        api_error_payload(
            code,
            message,
            details=details,
            legacy_key=legacy_key,
            status_value=status_value,
        ),
        cors=cors,
        methods=methods,
        allow_headers=allow_headers,
        cache_control=cache_control,
    )


def build_url(base: str, path: str = '', params: dict | None = None) -> str:
    """Build a URL from a base, path, and query params."""
    root = base.rstrip('/')
    url = f'{root}/{path.lstrip("/")}' if path else root
    if not params:
        return url
    separator = '&' if urllib.parse.urlsplit(url).query else '?'
    return f'{url}{separator}{urllib.parse.urlencode(params)}'


def redact_url(url: str, secret_query_keys=()) -> str:
    """Redact known secret-bearing URL locations for logs and exceptions."""
    if not url:
        return url

    parts = urllib.parse.urlsplit(url)
    secret_keys = {k.lower() for k in DEFAULT_SECRET_QUERY_KEYS}
    secret_keys.update(k.lower() for k in secret_query_keys)

    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    safe_query = urllib.parse.urlencode([
        (key, 'REDACTED' if key.lower() in secret_keys else value)
        for key, value in query
    ])
    safe_path = _TELEGRAM_BOT_TOKEN_RE.sub(r'\1[REDACTED]', parts.path)
    return urllib.parse.urlunsplit((
        parts.scheme,
        parts.netloc,
        safe_path,
        safe_query,
        parts.fragment,
    ))


def redact_text(value, secret_query_keys=()) -> str:
    """Best-effort redaction for exception messages that may contain URLs."""
    text = str(value)
    url_re = re.compile(r'https?://[^\s\'"<>]+')
    return redact_known_secrets(
        url_re.sub(lambda m: redact_url(m.group(0), secret_query_keys), text))


def redact_known_secrets(value) -> str:
    """Redact configured secret values from log text."""
    text = str(value)
    for name in SECRET_ENV_NAMES:
        secret = os.environ.get(name, '').strip()
        if len(secret) >= 8:
            text = text.replace(secret, '[REDACTED]')
    return text


def safe_exception_text(value, secret_query_keys=()) -> str:
    return redact_text(value, secret_query_keys)


def safe_traceback(secret_query_keys=()) -> str:
    return redact_text(traceback.format_exc(), secret_query_keys)


def log_event(level: str, event: str, **fields):
    """Emit one structured JSON log record to stdout."""
    record = {
        'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'level': level,
        'event': event,
    }
    for key, value in fields.items():
        record[key] = redact_text(value)
    print(json.dumps(record, ensure_ascii=False, default=str), flush=True)


def log_exception(event: str, *, secret_query_keys=(), **fields):
    fields['traceback'] = safe_traceback(secret_query_keys)
    log_event('error', event, **fields)


def urlopen_sanitized(req: urllib.request.Request, timeout: float, secret_query_keys=()):
    """Open a request, replacing URL-bearing urllib errors with safe messages."""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        safe_url = redact_url(e.geturl() or getattr(req, 'full_url', ''), secret_query_keys)
        raise RuntimeError(f'HTTP {e.code} while requesting {safe_url}') from None
    except urllib.error.URLError as e:
        safe_url = redact_url(getattr(req, 'full_url', ''), secret_query_keys)
        reason = redact_text(getattr(e, 'reason', type(e).__name__), secret_query_keys)
        raise RuntimeError(f'HTTP request failed for {safe_url}: {reason}') from None


def telegram_bot_url(token: str, method: str) -> str:
    """Build a Telegram Bot API method URL; redact_url knows this token path."""
    if not token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.')
    method = method.lstrip('/')
    return f'https://api.telegram.org/bot{token}/{method}'
