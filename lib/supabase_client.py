"""Supabase 클라이언트 싱글턴 — 환경변수에서 URL/KEY를 읽어 초기화."""
import os
from supabase import create_client, Client

_url = os.environ.get('SUPABASE_URL', '')
_key = os.environ.get('SUPABASE_KEY', '')

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not _url or not _key:
            raise RuntimeError('SUPABASE_URL / SUPABASE_KEY 환경변수가 설정되지 않았습니다.')
        _client = create_client(_url, _key)
    return _client
