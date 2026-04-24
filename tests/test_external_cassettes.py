from __future__ import annotations

from datetime import date

import pytest

from lib import dart, krx, naver


@pytest.mark.vcr
def test_dart_disclosure_search_contract(monkeypatch):
    monkeypatch.setenv('DART_API_KEY', 'test-dart-key')
    data = dart.search_disclosure(
        corp_code='00126380',
        bgn_de='20260401',
        end_de='20260424',
        page_no=1,
        page_count=1,
    )

    assert isinstance(data, dict)
    assert 'status' in data
    assert 'message' in data


@pytest.mark.vcr
def test_krx_kind_warning_page_contract(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 24)

    monkeypatch.setattr(krx, 'date', FixedDate)
    monkeypatch.setattr(krx._krx_cache, '_durable', False)
    krx._krx_cache.clear()

    html = krx.fetch_kind_page('2', page=1, days_back=30, page_size=20)
    rows = krx.parse_kind_html(html, '투자경고')

    assert '<tbody' in html
    assert isinstance(rows, list)


@pytest.mark.vcr
def test_naver_stock_code_and_price_contract(monkeypatch):
    monkeypatch.setattr(naver._code_cache, '_durable', False)
    monkeypatch.setattr(naver._price_cache, '_durable', False)
    naver._code_cache.clear()
    naver._price_cache.clear()

    matches = naver.stock_code('삼성전자')
    assert any(item['code'] == '005930' for item in matches)

    prices = naver.fetch_prices('005930', count=16)
    assert len(prices) >= 16
    assert prices[-1]['date'].count('-') == 2
    assert isinstance(prices[-1]['close'], int)
