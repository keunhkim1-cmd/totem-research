"""DART corp_code 매핑 — 종목코드 → DART 고유번호"""
from lib.dart_registry import corp_map_by_stock_code


def find_corp_by_stock_code(stock_code: str) -> dict | None:
    """종목코드(6자리) → {'corp_code': ..., 'corp_name': ...} 또는 None."""
    return corp_map_by_stock_code().get(stock_code)
