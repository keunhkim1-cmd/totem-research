from http.server import BaseHTTPRequestHandler
import urllib.parse, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.naver import caution_search
from lib.validation import normalize_query
from lib.http_utils import (
    api_success_payload,
    log_exception,
    send_api_error,
    send_json_response,
    send_options_response,
)

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options_response(self)

    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            name = normalize_query(qs.get('name', [''])[0])
            result = caution_search(name)
            send_json_response(self, 200, api_success_payload(result))
        except ValueError as e:
            send_api_error(
                self,
                400,
                'VALIDATION_ERROR',
                str(e),
                legacy_key='errorMessage',
                status_value='error',
            )
        except Exception:
            log_exception('api_request_failed', endpoint='caution-search')
            send_api_error(
                self,
                500,
                'INTERNAL_ERROR',
                '서버 오류가 발생했습니다.',
                legacy_key='errorMessage',
                status_value='error',
            )
