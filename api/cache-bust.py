from http.server import BaseHTTPRequestHandler
import hmac, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.durable_cache import delete, enabled
from lib.http_utils import (
    api_error_payload,
    api_success_payload,
    safe_exception_text,
    send_json_response,
    send_options_response,
)


ALLOWED_HEADERS = 'Authorization, X-API-Key, Content-Type'
KEY_RE = re.compile(r'^[A-Za-z0-9:_./|~-]{1,512}$')


def _expected_token() -> str:
    return (
        os.environ.get('CACHE_ADMIN_TOKEN', '').strip()
        or os.environ.get('FINANCIAL_MODEL_API_TOKEN', '').strip()
    )


def _presented_token(headers) -> str:
    auth = headers.get('Authorization', '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return headers.get('X-API-Key', '').strip()


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options_response(self, methods='POST, OPTIONS', allow_headers=ALLOWED_HEADERS)

    def do_POST(self):
        expected = _expected_token()
        if not expected:
            self._respond(503, api_error_payload(
                'ENDPOINT_NOT_CONFIGURED',
                '캐시 관리자 토큰이 설정되지 않았습니다.',
            ))
            return

        supplied = _presented_token(self.headers)
        if not supplied or not hmac.compare_digest(supplied, expected):
            self._respond(401, api_error_payload('AUTH_REQUIRED', '인증이 필요합니다.'))
            return

        if not enabled():
            self._respond(503, api_error_payload(
                'DURABLE_CACHE_NOT_CONFIGURED',
                'Durable cache가 설정되지 않았습니다.',
            ))
            return

        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self._respond(400, api_error_payload('VALIDATION_ERROR', '잘못된 본문 길이'))
            return
        if length <= 0 or length > 4096:
            self._respond(413, api_error_payload('PAYLOAD_TOO_LARGE', '본문이 너무 큽니다.'))
            return

        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._respond(400, api_error_payload('VALIDATION_ERROR', '잘못된 JSON'))
            return

        key = str(payload.get('key', '')).strip()
        if not KEY_RE.fullmatch(key):
            self._respond(400, api_error_payload('VALIDATION_ERROR', '잘못된 캐시 키'))
            return

        try:
            delete(key)
        except Exception as e:
            self._respond(502, api_error_payload(
                'DURABLE_CACHE_ERROR',
                f'Durable cache 삭제 실패: {safe_exception_text(e)}',
            ))
            return
        self._respond(200, api_success_payload({'busted': key}))

    def _respond(self, status: int, payload: dict):
        send_json_response(
            self,
            status,
            payload,
            methods='POST, OPTIONS',
            allow_headers=ALLOWED_HEADERS,
            cache_control='no-store',
        )

    def log_message(self, *args):
        pass
