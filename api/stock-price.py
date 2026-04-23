from http.server import BaseHTTPRequestHandler
import urllib.parse, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.naver import fetch_prices, calc_thresholds
from lib.validation import validate_stock_code
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
            code = validate_stock_code(qs.get('code', [''])[0])
        except ValueError as e:
            send_api_error(self, 400, 'VALIDATION_ERROR', str(e))
            return
        try:
            prices = fetch_prices(code)
            thresholds = calc_thresholds(prices)
            payload = {'prices': prices[-16:], 'thresholds': thresholds}
            if 'error' in thresholds:
                payload['warnings'] = [{
                    'code': 'INSUFFICIENT_PRICE_DATA',
                    'message': thresholds['error'],
                }]
            send_json_response(self, 200, api_success_payload(payload))
        except Exception:
            log_exception('api_request_failed', endpoint='stock-price')
            send_api_error(self, 500, 'INTERNAL_ERROR', '서버 오류가 발생했습니다.')
