"""Optional Upstash Redis REST cache helpers.

Enabled when UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are present.
The helpers are intentionally best-effort callers; higher layers decide whether
a miss or write failure is fatal.
"""
import json
import os
import urllib.request


def _rest_url() -> str:
    return (
        os.environ.get('UPSTASH_REDIS_REST_URL', '').strip()
        or os.environ.get('KV_REST_API_URL', '').strip()
    )


def _rest_token() -> str:
    return (
        os.environ.get('UPSTASH_REDIS_REST_TOKEN', '').strip()
        or os.environ.get('KV_REST_API_TOKEN', '').strip()
    )


def enabled() -> bool:
    return bool(_rest_url() and _rest_token())


def _command(*args):
    if not enabled():
        return None
    url = _rest_url().rstrip('/')
    token = _rest_token()
    body = json.dumps(list(args)).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.loads(resp.read().decode('utf-8')).get('result')


def command(*args):
    return _command(*args)


def get_json(key: str):
    result = _command('GET', key)
    if result is None:
        return None
    return json.loads(result)


def set_json(key: str, value, *, ttl: int):
    return _command('SET', key, json.dumps(value, ensure_ascii=False), 'EX', int(ttl))


def set_json_nx(key: str, value, *, ttl: int) -> bool:
    result = _command(
        'SET',
        key,
        json.dumps(value, ensure_ascii=False),
        'EX',
        int(ttl),
        'NX',
    )
    return result == 'OK'


def delete(key: str):
    return _command('DEL', key)


def incrby_with_expiry(key: str, amount: int, *, ttl: int) -> int | None:
    result = _command('INCRBY', key, int(amount))
    if result is None:
        return None
    count = int(result)
    if count == int(amount):
        _command('EXPIRE', key, int(ttl))
    return count
