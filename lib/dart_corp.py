"""DART corp_code 매핑 — 종목코드 → DART 고유번호"""
import io, json, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lib.cache import TTLCache
from lib.dart_base import fetch_bytes
from lib.timeouts import DART_DOCUMENT_TIMEOUT

# corp_code 매핑은 거의 변하지 않음 — 24시간 캐시
_cache = TTLCache(ttl=24 * 3600, name='dart-corp-map')


def _load_packaged_corp_map() -> dict:
    path = Path(__file__).resolve().parent.parent / 'data' / 'dart-corps.json'
    with path.open(encoding='utf-8') as f:
        rows = json.load(f)
    return {
        str(row.get('s', '')).strip(): {
            'corp_code': str(row.get('c', '')).strip(),
            'corp_name': str(row.get('n', '')).strip(),
        }
        for row in rows
        if str(row.get('s', '')).strip()
    }

def _load_corp_map() -> dict:
    """DART corpCode.xml zip 다운로드 → {stock_code: {corp_code, corp_name}} 매핑."""
    def _fetch():
        try:
            raw = fetch_bytes('corpCode.xml', timeout=DART_DOCUMENT_TIMEOUT, retries=1)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                with zf.open('CORPCODE.xml') as f:
                    xml_data = f.read()

            root = ET.fromstring(xml_data)
            mapping = {}
            for item in root.iter('list'):
                stock = (item.findtext('stock_code') or '').strip()
                if not stock:
                    continue
                mapping[stock] = {
                    'corp_code': (item.findtext('corp_code') or '').strip(),
                    'corp_name': (item.findtext('corp_name') or '').strip(),
                }
            return mapping
        except Exception:
            return _load_packaged_corp_map()

    return _cache.get_or_set(
        'corp_map',
        _fetch,
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )


def find_corp_by_stock_code(stock_code: str) -> dict | None:
    """종목코드(6자리) → {'corp_code': ..., 'corp_name': ...} 또는 None."""
    return _load_corp_map().get(stock_code)
