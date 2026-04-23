"""Optional durable Telegram update idempotency.

Set TELEGRAM_IDEMPOTENCY_SUPABASE=true and create a telegram_updates table with
update_id as a unique key to make webhook retries safe across instances.
If Upstash Redis REST variables are present, Redis SET NX is used first so
"processing" claims can expire after a short timeout.
"""
import os

from lib.http_utils import log_event, safe_exception_text


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def durable_idempotency_enabled() -> bool:
    raw = os.environ.get('TELEGRAM_IDEMPOTENCY_SUPABASE', '')
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _redis_key(update_id: int | str) -> str:
    return f'telegram:update:{update_id}'


def _claim_update_redis(update_id: int | str) -> bool | None:
    try:
        from lib.durable_cache import enabled, set_json_nx
        if not enabled():
            return None
        ttl = _env_int('TELEGRAM_IDEMPOTENCY_PROCESSING_TTL', 900, 60, 3600)
        return set_json_nx(
            _redis_key(update_id),
            {'state': 'processing'},
            ttl=ttl,
        )
    except Exception as e:
        log_event('warning', 'telegram_idempotency_redis_claim_failed',
                  error=safe_exception_text(e))
        return None


def claim_update(update_id: int | str) -> bool:
    redis_claimed = _claim_update_redis(update_id)
    if redis_claimed is not None:
        return redis_claimed

    if not durable_idempotency_enabled():
        return True

    try:
        from lib.supabase_client import cache_enabled, get_client
        if not cache_enabled():
            return True
        (get_client().table('telegram_updates')
         .insert({'update_id': str(update_id)})
         .execute())
        return True
    except Exception as e:
        message = safe_exception_text(e)
        if 'duplicate' in message.lower() or '23505' in message:
            return False
        log_event('warning', 'telegram_idempotency_store_failed', error=message)
        return True


def mark_update_done(update_id: int | str):
    try:
        from lib.durable_cache import enabled, set_json
        if not enabled():
            return
        ttl = _env_int('TELEGRAM_IDEMPOTENCY_DONE_TTL', 24 * 3600, 3600, 7 * 24 * 3600)
        set_json(_redis_key(update_id), {'state': 'done'}, ttl=ttl)
    except Exception as e:
        log_event('warning', 'telegram_idempotency_done_failed',
                  error=safe_exception_text(e))
