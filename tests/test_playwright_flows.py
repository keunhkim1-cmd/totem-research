from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, Route, expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope='session')
def local_server():
    port = _free_port()
    env = {
        **os.environ,
        'HOST': '127.0.0.1',
        'PORT': str(port),
        'PYTHONUNBUFFERED': '1',
    }
    proc = subprocess.Popen(
        [sys.executable, 'serve.py'],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f'http://127.0.0.1:{port}'
    deadline = time.time() + 10
    last_error: Exception | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ''
            pytest.fail(f'local server exited early with {proc.returncode}: {output}')
        try:
            with urllib.request.urlopen(base_url, timeout=0.5) as resp:
                if resp.status == 200:
                    break
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    else:
        pytest.fail(f'local server did not become ready: {last_error}')

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='ko-KR')
    page = context.new_page()
    yield page
    context.close()


def _fulfill_json(route: Route, payload: dict[str, Any]) -> None:
    route.fulfill(
        status=200,
        content_type='application/json; charset=utf-8',
        body=json.dumps(payload, ensure_ascii=False),
    )


def _prices() -> list[dict[str, int | str]]:
    closes = [
        65000,
        66000,
        67000,
        68000,
        69000,
        70000,
        71000,
        72000,
        73000,
        74000,
        75000,
        76000,
        78000,
        80000,
        83000,
        84000,
    ]
    return [
        {'date': f'2026-04-{day:02d}', 'close': close}
        for day, close in zip(range(1, 17), closes, strict=True)
    ]


def _stock_code_payload() -> dict[str, Any]:
    return {'ok': True, 'items': [{'code': '005930', 'name': '삼성전자', 'market': 'KOSPI'}]}


def _stock_price_payload() -> dict[str, Any]:
    prices = _prices()
    return {
        'ok': True,
        'prices': prices,
        'thresholds': {
            'tClose': 84000,
            'tDate': '2026-04-16',
            't5Close': 75000,
            't5Date': '2026-04-11',
            'thresh1': 108750,
            'cond1': False,
            't15Close': 66000,
            't15Date': '2026-04-02',
            'thresh2': 115500,
            'cond2': False,
            'max15': 84000,
            'max15Date': '2026-04-16',
            'thresh3': 84000,
            'cond3': True,
            'allMet': False,
            'policy': {
                't5Lookback': 5,
                't5Multiplier': 1.45,
                't15Lookback': 15,
                't15Multiplier': 1.75,
                'maxWindowDays': 15,
            },
        },
        'prevClose': 83000,
        'high': 85000,
        'low': 82000,
        'volume': 123456,
        'prevVolume': 100000,
    }


def _route_stock_dependencies(page: Page) -> None:
    page.route('**/api/stock-code?*', lambda route: _fulfill_json(route, _stock_code_payload()))
    page.route('**/api/stock-price?*', lambda route: _fulfill_json(route, _stock_price_payload()))


@pytest.mark.e2e
def test_empty_search_shows_inline_validation(local_server, page: Page):
    page.goto(local_server)
    page.get_by_role('button', name='search').click()

    expect(page.locator('#searchResults')).to_contain_text('종목명을 입력하세요')
    expect(page.locator('#searchInput')).to_be_focused()


@pytest.mark.e2e
def test_secondary_tabs_render_from_split_modules(local_server, page: Page):
    page.goto(local_server)

    page.get_by_role('tab', name='오늘의 운세').click()
    page.get_by_role('button', name='오늘의 운세 열기').click()
    expect(page.locator('#fortuneContent .fortune-message')).to_be_visible()
    expect(page.locator('#fortunePanelTitle')).to_contain_text('행운')

    page.get_by_role('tab', name='패치 노트').click()
    expect(page.locator('#patchnotesContent .patch-entry').first).to_be_visible()


@pytest.mark.e2e
def test_market_alert_forecast_tab_renders_and_checks_stock(local_server, page: Page):
    page.route(
        '**/api/market-alert-forecast',
        lambda route: _fulfill_json(
            route,
            {
                'ok': True,
                'todayKst': '2026-04-26',
                'generatedAt': '2026-04-26T09:10:00+09:00',
                'summary': {
                    'total': 2,
                    'alert': 1,
                    'watch': 1,
                    'calculated': 1,
                    'needsReview': 1,
                    'excludedCurrentWarning': 0,
                },
                'items': [
                    {
                        'level': 'alert',
                        'levelLabel': '경보',
                        'stockName': '테스트전자',
                        'code': '005930',
                        'market': 'KOSPI',
                        'noticeDate': '2026-04-24',
                        'firstJudgmentDate': '2026-04-27',
                        'lastJudgmentDate': '2026-05-11',
                        'judgmentDayIndex': 0,
                        'judgmentWindowTotal': 10,
                        'calcStatus': 'calculated',
                        'calcStatusLabel': '계산 완료',
                        'escalation': {
                            'headline': {'verdict': 'strong', 'matchedSet': 0},
                            'sets': [{'label': '단기급등', 'allMet': True}],
                        },
                    },
                    {
                        'level': 'watch',
                        'levelLabel': '주의보',
                        'stockName': '확인필요',
                        'market': 'KOSDAQ',
                        'noticeDate': '2026-04-24',
                        'firstJudgmentDate': '2026-04-27',
                        'lastJudgmentDate': '2026-05-11',
                        'judgmentDayIndex': 0,
                        'judgmentWindowTotal': 10,
                        'calcStatus': 'needs_review',
                        'calcStatusLabel': '확인 필요',
                        'calcDetail': 'KRX 내부 감시 데이터가 필요한 지정예고 유형입니다.',
                    },
                ],
                'errors': [],
            },
        ),
    )
    page.route('**/api/warn-search?*', lambda route: _fulfill_json(route, {'ok': True, 'results': []}))
    page.route(
        '**/api/caution-search?*',
        lambda route: _fulfill_json(route, {'ok': True, 'status': 'not_caution'}),
    )

    page.goto(local_server)
    page.get_by_role('tab', name='투자경고 예보 (개발중)').click()

    expect(page.locator('#forecastTitle')).to_contain_text('(개발중)')
    expect(page.locator('#forecastSummary')).to_contain_text('경보')
    expect(page.locator('#forecastContent')).to_contain_text('테스트전자')
    expect(page.locator('#forecastContent')).to_contain_text('단기급등 충족')
    expect(page.locator('#forecastContent')).to_contain_text('확인 필요')

    page.locator('#forecastContent .forecast-check').first.click()
    expect(page.locator('#nav-warning')).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#searchInput')).to_have_value('테스트전자')
    expect(page.locator('#searchResults')).to_contain_text('현재 투자경고/투자주의가 아님')


@pytest.mark.e2e
def test_market_alert_forecast_tab_surfaces_source_error(local_server, page: Page):
    page.route(
        '**/api/market-alert-forecast',
        lambda route: _fulfill_json(
            route,
            {
                'ok': True,
                'todayKst': '2026-04-26',
                'generatedAt': '2026-04-26T09:10:00+09:00',
                'summary': {
                    'total': 0,
                    'alert': 0,
                    'watch': 0,
                    'calculated': 0,
                    'needsReview': 0,
                    'excludedCurrentWarning': 0,
                },
                'items': [],
                'errors': [{
                    'source': 'krx-caution',
                    'message': 'KRX 투자주의/지정예고 조회 실패: timeout',
                }],
            },
        ),
    )

    page.goto(local_server)
    page.get_by_role('tab', name='투자경고 예보 (개발중)').click()

    expect(page.locator('#forecastContent')).to_contain_text('KRX 투자주의/지정예고 조회 실패')
    expect(page.locator('#forecastContent')).to_contain_text(
        'KRX 원천 조회가 일시적으로 제한되어 예보 후보를 확인할 수 없습니다'
    )
    expect(page.locator('#forecastContent')).not_to_contain_text('투자경고 예보를 불러올 수 없습니다')
    expect(page.locator('#forecastContent')).not_to_contain_text('활성 투자경고 지정예고 후보가 없습니다')


@pytest.mark.e2e
def test_warning_search_renders_price_thresholds_and_chart(local_server, page: Page):
    _route_stock_dependencies(page)
    page.route(
        '**/api/warn-search?*',
        lambda route: _fulfill_json(
            route,
            {
                'ok': True,
                'results': [
                    {
                        'level': '투자경고',
                        'stockName': '삼성전자',
                        'designationDate': '2026-04-22',
                    }
                ],
            },
        ),
    )

    page.goto(local_server)
    page.locator('#searchInput').fill('삼성전자')
    page.get_by_role('button', name='search').click()

    expect(page.locator('#sym-header .ticker')).to_have_text('005930')
    expect(page.locator('#conditionsTbody')).to_contain_text('T-5 종가')
    expect(page.locator('#sec-verdict')).to_be_visible()
    expect(page.locator('#sec-verdict .tag')).to_have_text('해제 예정')
    expect(page.locator('#sec-verdict .h')).to_contain_text('투자경고 해제 예정')
    expect(page.locator('#sec-verdict .b')).to_contain_text('해제 판단일')
    expect(page.locator('#sec-verdict')).not_to_contain_text('다음 거래일')
    expect(page.locator('#tvChartWarning svg')).to_be_visible()


@pytest.mark.e2e
def test_caution_fallback_renders_escalation_verdict(local_server, page: Page):
    _route_stock_dependencies(page)
    page.route(
        '**/api/warn-search?*', lambda route: _fulfill_json(route, {'ok': True, 'results': []})
    )
    page.route(
        '**/api/caution-search?*',
        lambda route: _fulfill_json(
            route,
            {
                'ok': True,
                'status': 'ok',
                'stockName': '테스트전자',
                'code': '005930',
                'market': 'KOSPI',
                'indexSymbol': 'KOSPI',
                'activeNotice': {
                    'noticeDate': '2026-04-20',
                    'firstJudgmentDate': '2026-04-21',
                    'lastJudgmentDate': '2026-04-24',
                    'judgmentDayIndex': 4,
                    'judgmentWindowTotal': 5,
                },
                'escalation': {
                    'tClose': 84000,
                    'tDate': '2026-04-24',
                    'indexClose': 2800.5,
                    'headline': {'verdict': 'strong', 'matchedSet': 0},
                    'sets': [
                        {
                            'label': '단기급등',
                            'allMet': True,
                            'conditions': [
                                {'met': True, 'label': '가격 상승률', 'detail': '기준가 충족'},
                                {'met': True, 'label': '최고가', 'detail': '최근 15일 최고'},
                                {'met': True, 'label': '지수 대비', 'detail': '지수 상승률 초과'},
                            ],
                        }
                    ],
                },
            },
        ),
    )

    page.goto(local_server)
    page.locator('#searchInput').fill('테스트전자')
    page.get_by_role('button', name='search').click()

    expect(page.locator('#cautionCard')).to_be_visible()
    expect(page.locator('#cautionVerdict')).to_contain_text('투자경고 지정 예상')
