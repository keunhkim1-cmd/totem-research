"""
진단용 엔드포인트 — 배포 후 /api/debug 를 브라우저에서 열어 확인
DEBUG_ENABLED=true 환경변수가 설정된 경우에만 동작
"""
from http.server import BaseHTTPRequestHandler
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.durable_cache import enabled as durable_cache_enabled
from lib.http_utils import api_success_payload, send_json_headers, send_text_headers
from lib.provider_rate_limit import DEFAULT_PER_MINUTE, provider_limit

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if os.environ.get('DEBUG_ENABLED', '') != 'true':
            self.send_response(404)
            send_text_headers(self, cors=False, cache_control='no-store')
            self.end_headers()
            return

        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        result = {
            'token_set': bool(token),
            'telegram_api': 'SKIP (token-bearing API check disabled)',
            'durable_cache_enabled': durable_cache_enabled(),
            'external_rate_limits_enabled': os.environ.get(
                'EXTERNAL_RATE_LIMITS_ENABLED',
                'true',
            ).strip().lower() in ('1', 'true', 'yes', 'on'),
            'provider_rate_limits_per_minute': {
                provider: provider_limit(provider)
                for provider in sorted(DEFAULT_PER_MINUTE)
            },
        }

        body = json.dumps(api_success_payload(result), ensure_ascii=False, indent=2).encode()
        self.send_response(200)
        send_json_headers(self, cors=False, cache_control='no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
