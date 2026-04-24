#!/usr/bin/env python3
"""Refresh data/dart-corps.json from DART corpCode.xml."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.dart_registry import CORP_CODE_RE, PACKAGED_CORP_PATH, fetch_live_corp_rows


def _validate(rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError('DART corp registry is empty.')

    seen = set()
    for row in rows:
        corp_code = row.get('c', '')
        stock_code = row.get('s', '')
        if not CORP_CODE_RE.fullmatch(corp_code):
            raise RuntimeError(f'invalid corp_code: {corp_code!r}')
        if not stock_code:
            raise RuntimeError(f'missing stock_code for corp_code={corp_code}')
        key = (corp_code, stock_code)
        if key in seen:
            raise RuntimeError(f'duplicate corp/stock pair: {key!r}')
        seen.add(key)


def main() -> int:
    rows = fetch_live_corp_rows()
    _validate(rows)
    PACKAGED_CORP_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(',', ':')) + '\n',
        encoding='utf-8',
    )
    print(f'updated {PACKAGED_CORP_PATH.relative_to(ROOT)} ({len(rows)} rows)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
