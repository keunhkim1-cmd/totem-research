from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

import serve
from lib import usecases


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def local_api_server():
    port = _free_port()
    httpd = serve.ThreadedServer(('127.0.0.1', port), serve.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8')
        return exc.code, json.loads(body)


def test_public_api_routes_return_success_envelopes(monkeypatch, local_api_server):
    monkeypatch.setattr(
        usecases,
        'warning_search_payload',
        lambda name: {'query': name, 'results': [{'stockName': '삼성전자'}]},
    )
    monkeypatch.setattr(
        usecases,
        'caution_search_payload',
        lambda name: {'stockName': name, 'status': 'not_caution'},
    )
    monkeypatch.setattr(
        usecases,
        'market_alert_forecast_payload',
        lambda: {'todayKst': '2026-04-26', 'summary': {'total': 0}, 'items': [], 'errors': []},
    )
    monkeypatch.setattr(
        usecases,
        'stock_code_payload',
        lambda name: {'query': name, 'items': [{'code': '005930', 'name': name}]},
    )
    monkeypatch.setattr(
        usecases,
        'stock_price_payload',
        lambda code: {'code': code, 'prices': [], 'thresholds': {'error': '데이터 부족'}},
    )
    monkeypatch.setattr(usecases, 'stock_overview_payload', lambda code: {'code': code})
    monkeypatch.setattr(usecases, 'dart_search_payload', lambda **kwargs: {'status': '013'})

    routes = [
        '/api/warn-search?name=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90',
        '/api/caution-search?name=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90',
        '/api/market-alert-forecast',
        '/api/stock-code?name=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90',
        '/api/stock-price?code=005930',
        '/api/stock-overview?code=005930',
        '/api/dart-search?corp_code=00126380&page_no=1',
    ]

    for route in routes:
        status, payload = _get_json(local_api_server + route)
        assert status == 200, route
        assert payload['ok'] is True, route


def test_public_api_validation_errors_use_error_envelope(monkeypatch, local_api_server):
    monkeypatch.setattr(
        usecases,
        'stock_code_payload',
        lambda name: (_ for _ in ()).throw(ValueError('종목명을 입력하세요.')),
    )

    status, payload = _get_json(local_api_server + '/api/stock-code?name=')

    assert status == 400
    assert payload['ok'] is False
    assert payload['errorInfo']['code'] == 'VALIDATION_ERROR'
    assert payload['error'] == '종목명을 입력하세요.'


def test_public_api_options_preflight_returns_no_content(local_api_server):
    req = urllib.request.Request(
        local_api_server + '/api/stock-code?name=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90',
        headers={'Origin': 'http://127.0.0.1:5173'},
        method='OPTIONS',
    )

    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 204
        assert resp.headers['Access-Control-Allow-Methods'] == 'GET, OPTIONS'
        assert resp.headers['Access-Control-Allow-Origin'] == 'http://127.0.0.1:5173'
        assert resp.read() == b''
