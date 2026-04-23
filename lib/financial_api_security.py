"""Guards for the high-cost financial model API."""
import hmac
import json
import os
import re
from pathlib import Path

from lib.cache import TTLCache
from lib.validation import parse_int_range


CORP_CODE_RE = re.compile(r'^\d{8}$')
ALLOWED_FS_DIVS = frozenset({'CFS', 'OFS'})
DEFAULT_MAX_YEARS = 5
DEFAULT_RATE_LIMIT_PER_MINUTE = 20

_rate_cache = TTLCache(ttl=60)
_corp_codes: set[str] | None = None


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def max_years() -> int:
    return _env_int('FINANCIAL_MODEL_MAX_YEARS', DEFAULT_MAX_YEARS, 2, 7)


def _load_known_corp_codes() -> set[str]:
    global _corp_codes
    if _corp_codes is not None:
        return _corp_codes

    path = Path(__file__).resolve().parent.parent / 'data' / 'dart-corps.json'
    with path.open(encoding='utf-8') as f:
        rows = json.load(f)
    _corp_codes = {
        str(row.get('c', '')).strip()
        for row in rows
        if CORP_CODE_RE.fullmatch(str(row.get('c', '')).strip())
    }
    return _corp_codes


def is_known_corp_code(corp_code: str) -> bool:
    return corp_code in _load_known_corp_codes()


def validate_params(corp_code: str, fs_div: str, years_raw: str) -> tuple[str, str, int]:
    corp_code = (corp_code or '').strip()
    fs_div = (fs_div or 'CFS').strip().upper()

    if not CORP_CODE_RE.fullmatch(corp_code):
        raise ValueError('잘못된 corp_code 형식')
    if not is_known_corp_code(corp_code):
        raise ValueError('등록되지 않은 corp_code')
    if fs_div not in ALLOWED_FS_DIVS:
        raise ValueError('잘못된 fs_div 값')

    max_allowed = max_years()
    years = parse_int_range(years_raw, 'years', DEFAULT_MAX_YEARS, 2, max_allowed)
    return corp_code, fs_div, years


def _presented_token(headers) -> str:
    auth = headers.get('Authorization', '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return (
        headers.get('X-Financial-Model-Token', '').strip()
        or headers.get('X-API-Key', '').strip()
    )


def auth_error(headers) -> tuple[int, str] | None:
    expected = os.environ.get('FINANCIAL_MODEL_API_TOKEN', '').strip()
    if not expected:
        return 503, '엔드포인트가 설정되지 않았습니다.'

    supplied = _presented_token(headers)
    if not supplied or not hmac.compare_digest(supplied, expected):
        return 401, '인증이 필요합니다.'
    return None


def client_id(headers, client_address=None) -> str:
    forwarded = headers.get('X-Forwarded-For', '').split(',', 1)[0].strip()
    if forwarded:
        return forwarded
    if client_address:
        return str(client_address[0])
    return 'unknown'


def rate_limit_error(client: str) -> tuple[int, str] | None:
    limit = _env_int(
        'FINANCIAL_MODEL_RATE_LIMIT_PER_MINUTE',
        DEFAULT_RATE_LIMIT_PER_MINUTE,
        1,
        120,
    )
    key = f'financial-model:{client}'
    count = _rate_cache.get(key) or 0
    if count >= limit:
        return 429, '요청 한도를 초과했습니다.'
    _rate_cache.set(key, count + 1)
    return None
