"""DART corporation registry shared by stock-code mapping and allowlists."""
import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lib.cache import TTLCache
from lib.dart_base import fetch_bytes
from lib.timeouts import DART_DOCUMENT_TIMEOUT


CORP_CODE_RE = re.compile(r'^\d{8}$')
ROOT = Path(__file__).resolve().parent.parent
PACKAGED_CORP_PATH = ROOT / 'data' / 'dart-corps.json'

_registry_cache = TTLCache(ttl=24 * 3600, name='dart-corp-registry')


def _normalize_row(corp_code: str, corp_name: str, stock_code: str) -> dict | None:
    corp_code = str(corp_code or '').strip()
    corp_name = str(corp_name or '').strip()
    stock_code = str(stock_code or '').strip()
    if not stock_code or not corp_code:
        return None
    return {'c': corp_code, 'n': corp_name, 's': stock_code}


def _parse_packaged_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        normalized = _normalize_row(row.get('c'), row.get('n'), row.get('s'))
        if normalized:
            out.append(normalized)
    return out


def load_packaged_corp_rows() -> list[dict]:
    """Load the bundled fallback registry from the repository."""
    with PACKAGED_CORP_PATH.open(encoding='utf-8') as f:
        return _parse_packaged_rows(json.load(f))


def parse_corp_code_zip(raw: bytes) -> list[dict]:
    """Parse DART corpCode.xml zip bytes into compact registry rows."""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open('CORPCODE.xml') as f:
            xml_data = f.read()

    root = ET.fromstring(xml_data)
    rows = []
    for item in root.iter('list'):
        normalized = _normalize_row(
            item.findtext('corp_code'),
            item.findtext('corp_name'),
            item.findtext('stock_code'),
        )
        if normalized:
            rows.append(normalized)
    return rows


def fetch_live_corp_rows() -> list[dict]:
    """Fetch the latest listed-company registry from DART."""
    raw = fetch_bytes('corpCode.xml', timeout=DART_DOCUMENT_TIMEOUT, retries=1)
    return parse_corp_code_zip(raw)


def load_corp_rows() -> list[dict]:
    """Return the latest DART registry, falling back to the bundled snapshot."""
    def _fetch():
        try:
            return fetch_live_corp_rows()
        except Exception:
            return load_packaged_corp_rows()

    return _registry_cache.get_or_set(
        'rows',
        _fetch,
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )


def corp_map_by_stock_code() -> dict:
    """Return {stock_code: {corp_code, corp_name}} using the shared registry."""
    return _registry_cache.get_or_set(
        'stock-map',
        lambda: {
            row['s']: {'corp_code': row['c'], 'corp_name': row['n']}
            for row in load_corp_rows()
            if row.get('s')
        },
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )


def known_corp_codes() -> set[str]:
    """Return valid 8-digit DART corp codes using the shared registry."""
    return _registry_cache.get_or_set(
        'corp-codes',
        lambda: {
            row['c']
            for row in load_corp_rows()
            if CORP_CODE_RE.fullmatch(row.get('c', ''))
        },
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )
