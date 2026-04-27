"""HTTP API 라우트 단일 소스.

Vercel 배포용 ``api/*.py`` 핸들러와 로컬 ``serve.py``가 공통으로 참조한다.
새 GET 엔드포인트는 ROUTES에 ApiRoute 한 줄을 추가하고
``api/<path>.py``에 4줄 shim만 두면 두 환경 모두 자동 지원된다.

본 모듈은 단순 GET 라우트만 담당한다. POST 웹훅(api/telegram.py),
크론(api/warm-cache.py), 토큰 보호 캐시 무효화(api/cache-bust.py),
디버그(api/debug.py)는 자체 핸들러를 유지한다.
"""
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from typing import Callable
import urllib.parse

from lib import usecases
from lib.errors import DartError
from lib.http_utils import (
    api_success_payload,
    log_exception,
    send_api_error,
    send_json_response,
    send_options_response,
)


@dataclass(frozen=True)
class ApiRoute:
    """단일 GET 엔드포인트 정의."""
    path: str
    endpoint: str
    payload: Callable[[dict], dict]
    legacy_key: str = 'error'
    status_value: str | None = None
    dart_errors: bool = False


def _q(qs: dict, key: str, default: str = '') -> str:
    return qs.get(key, [default])[0]


ROUTES: tuple[ApiRoute, ...] = (
    ApiRoute(
        path='/api/warn-search',
        endpoint='warn-search',
        payload=lambda qs: usecases.warning_search_payload(_q(qs, 'name')),
    ),
    ApiRoute(
        path='/api/caution-search',
        endpoint='caution-search',
        payload=lambda qs: usecases.caution_search_payload(_q(qs, 'name')),
        legacy_key='errorMessage',
        status_value='error',
    ),
    ApiRoute(
        path='/api/market-alert-forecast',
        endpoint='market-alert-forecast',
        payload=lambda qs: usecases.market_alert_forecast_payload(),
    ),
    ApiRoute(
        path='/api/stock-code',
        endpoint='stock-code',
        payload=lambda qs: usecases.stock_code_payload(_q(qs, 'name')),
    ),
    ApiRoute(
        path='/api/stock-price',
        endpoint='stock-price',
        payload=lambda qs: usecases.stock_price_payload(_q(qs, 'code')),
    ),
    ApiRoute(
        path='/api/stock-overview',
        endpoint='stock-overview',
        payload=lambda qs: usecases.stock_overview_payload(_q(qs, 'code')),
    ),
    ApiRoute(
        path='/api/dart-search',
        endpoint='dart-search',
        payload=lambda qs: usecases.dart_search_payload(
            corp_code=_q(qs, 'corp_code').strip(),
            bgn_de=_q(qs, 'bgn_de').strip(),
            end_de=_q(qs, 'end_de').strip(),
            page_no=_q(qs, 'page_no', '1').strip(),
            page_count=_q(qs, 'page_count', '20').strip(),
            pblntf_ty=_q(qs, 'pblntf_ty').strip(),
        ),
        dart_errors=True,
    ),
)

ROUTES_BY_PATH: dict[str, ApiRoute] = {r.path: r for r in ROUTES}


def _send_error(handler, route: ApiRoute, status: int, code: str, message: str, **extra) -> None:
    send_api_error(
        handler,
        status,
        code,
        message,
        legacy_key=route.legacy_key,
        status_value=route.status_value,
        **extra,
    )


def dispatch(handler, route: ApiRoute, qs: dict) -> None:
    """공통 디스패치 — payload 실행과 에러 매핑."""
    try:
        data = route.payload(qs)
    except ValueError as e:
        _send_error(handler, route, 400, 'VALIDATION_ERROR', str(e))
        return
    except DartError as e:
        if route.dart_errors:
            _send_error(handler, route, e.http_status, e.code, e.message, details=e.details)
            return
        log_exception('api_request_failed', endpoint=route.endpoint)
        _send_error(handler, route, 500, 'INTERNAL_ERROR', '서버 오류가 발생했습니다.')
        return
    except Exception:
        log_exception('api_request_failed', endpoint=route.endpoint)
        _send_error(handler, route, 500, 'INTERNAL_ERROR', '서버 오류가 발생했습니다.')
        return

    send_json_response(handler, 200, api_success_payload(data))


class RouteHandler(BaseHTTPRequestHandler):
    """``api/*.py`` shim의 베이스 클래스.

    Vercel ``@vercel/python`` 빌더는 정적 분석으로 ``class handler(...)``
    선언을 찾으므로 각 api 파일은 이 클래스를 상속한 ``class handler``를
    선언하고 클래스 변수 ``route``에 ``ROUTES_BY_PATH[...]``를 할당한다.
    """

    route: ApiRoute  # 서브클래스가 반드시 설정

    def do_OPTIONS(self):
        send_options_response(self)

    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        dispatch(self, self.route, qs)
