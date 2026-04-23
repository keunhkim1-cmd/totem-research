"""TTL 기반 인메모리 캐시 (stdlib만 사용)."""
import os
import time
import threading


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


class TTLCache:
    """스레드 안전한 TTL 캐시. ttl 초 이내 동일 키 요청 시 캐시 반환."""

    def __init__(self, ttl: int = 300, *, name: str = '', durable: bool = False):
        self._ttl = ttl
        self._name = name
        self._durable = durable
        self._store: dict = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._stale_hits = 0

    def _durable_key(self, key: str) -> str:
        return f'{self._name}:{key}' if self._name else key

    def _durable_get(self, key: str):
        if not self._durable:
            return None
        try:
            from lib.durable_cache import get_json
            return get_json(self._durable_key(key))
        except Exception:
            return None

    def _durable_set(self, key: str, value):
        if not self._durable:
            return
        try:
            from lib.durable_cache import set_json
            set_json(self._durable_key(key), value, ttl=self._ttl)
        except Exception:
            return

    def _set_local(self, key: str, value):
        with self._lock:
            self._store[key] = (value, time.time())

    def _log_access(self, key: str, state: str):
        if not self._name or not _env_bool('CACHE_ACCESS_LOGS_ENABLED'):
            return
        try:
            from lib.http_utils import log_event
            log_event('info', 'cache_access',
                      cache=self._name, key=key, state=state,
                      durable=self._durable)
        except Exception:
            return

    def get(self, key: str):
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry and now - entry[1] < self._ttl:
                self._hits += 1
                self._log_access(key, 'hit')
                return entry[0]
        value = self._durable_get(key)
        if value is not None:
            self._set_local(key, value)
            with self._lock:
                self._hits += 1
            self._log_access(key, 'durable_hit')
            return value
        with self._lock:
            self._misses += 1
        self._log_access(key, 'miss')
        return None

    def get_with_meta(self, key: str, *, allow_stale: bool = False,
                      max_stale: int | None = None):
        """Return (value, state), where state is hit, stale, or miss."""
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry:
                age = now - entry[1]
                if age < self._ttl:
                    self._hits += 1
                    self._log_access(key, 'hit')
                    return entry[0], 'hit'
                stale_budget = self._ttl + (max_stale if max_stale is not None else 0)
                if allow_stale and age < stale_budget:
                    self._stale_hits += 1
                    self._log_access(key, 'stale')
                    return entry[0], 'stale'
        value = self._durable_get(key)
        if value is not None:
            self._set_local(key, value)
            with self._lock:
                self._hits += 1
            self._log_access(key, 'durable_hit')
            return value, 'hit'
        with self._lock:
            self._misses += 1
        self._log_access(key, 'miss')
        return None, 'miss'

    def set(self, key: str, value):
        self._set_local(key, value)
        self._durable_set(key, value)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)
        if self._durable:
            try:
                from lib.durable_cache import delete
                delete(self._durable_key(key))
            except Exception:
                return

    def clear(self):
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                'name': self._name,
                'ttl': self._ttl,
                'size': len(self._store),
                'hits': self._hits,
                'misses': self._misses,
                'stale_hits': self._stale_hits,
                'durable': self._durable,
            }

    def get_or_set(self, key: str, fn, *, allow_stale_on_error: bool = False,
                   max_stale: int | None = None):
        """캐시에 있으면 반환, 없으면 fn() 호출 후 저장."""
        cached = self.get(key)
        if cached is not None:
            return cached
        try:
            value = fn()
        except Exception:
            if allow_stale_on_error:
                stale, state = self.get_with_meta(
                    key,
                    allow_stale=True,
                    max_stale=max_stale,
                )
                if state == 'stale':
                    try:
                        from lib.http_utils import log_event
                        log_event('warning', 'cache_stale_returned',
                                  cache=self._name, key=key)
                    except Exception:
                        pass
                    return stale
            raise
        self.set(key, value)
        return value
