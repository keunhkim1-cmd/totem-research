#!/usr/bin/env python3
"""
투자경고 해제일 계산기 - 로컬 개발 서버
- 정적 파일 서빙 (index.html)
- API 프록시 (/api/warn-search, /api/stock-code, /api/stock-price)
"""
import http.server
import socketserver
import os
import json
import urllib.parse

DIRECTORY = os.path.dirname(os.path.abspath(__file__))


def _load_local_env(path: str = '.env') -> None:
    env_path = os.path.join(DIRECTORY, path)
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            if line.startswith('export '):
                line = line[len('export '):].strip()
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


_load_local_env('.env.local')
_load_local_env('.env')

from lib.krx import search_kind
from lib.naver import stock_code as naver_stock_code, fetch_prices, calc_thresholds, fetch_stock_overview, caution_search
from lib.dart import search_disclosure
from lib.financial_model import build_model
from lib.financial_api_security import auth_error, client_id, rate_limit_error, validate_params
from lib.http_utils import (
    STATIC_CSP,
    send_json_headers,
    send_options_response,
    send_security_headers,
)
from lib.validation import (
    normalize_query,
    parse_int_range,
    validate_corp_code,
    validate_dart_pblntf_ty,
    validate_date_range,
    validate_stock_code,
)

HOST = os.environ.get('HOST', '127.0.0.1')
PORT = _env_int('PORT', 5173)
FINANCIAL_ALLOWED_HEADERS = 'Authorization, X-API-Key, X-Financial-Model-Token, Content-Type'
FORBIDDEN_PATH_PARTS = {
    '.env',
    '.git',
    '.vercel',
    '.claude',
    '__pycache__',
}
SERVER_ONLY_STATIC_PATHS = {
    '/data/account-mapping.json',
    '/data/dart-corps.json',
}
SERVER_ONLY_PATH_PREFIXES = (
    '/supabase/',
)


def is_forbidden_static_path(request_path: str) -> bool:
    path = urllib.parse.unquote(urllib.parse.urlparse(request_path).path)
    if path in SERVER_ONLY_STATIC_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in SERVER_ONLY_PATH_PREFIXES):
        return True
    parts = [p for p in path.split('/') if p]
    for part in parts:
        if part in FORBIDDEN_PATH_PARTS or part.startswith('.'):
            return True
        if part.endswith(('.pyc', '.pyo')):
            return True
    return False


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, fmt, *args):
        print(f'[{self.address_string()}] {fmt % args}')

    def send_json(self, data, status=200, allow_headers=None, cache_control=None):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        send_json_headers(self, allow_headers=allow_headers, cache_control=cache_control)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_financial_json(self, data, status=200):
        self.send_json(
            data,
            status,
            allow_headers=FINANCIAL_ALLOWED_HEADERS,
            cache_control='no-store',
        )

    def do_OPTIONS(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/financial-model':
            send_options_response(self, allow_headers=FINANCIAL_ALLOWED_HEADERS)
            return
        if parsed.path.startswith('/api/'):
            send_options_response(self)
            return
        self.send_error(405, 'Method Not Allowed')

    def do_HEAD(self):
        if is_forbidden_static_path(self.path):
            self.send_error(404)
            return
        super().do_HEAD()

    def do_GET(self):
        if is_forbidden_static_path(self.path):
            self.send_error(404)
            return

        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/api/warn-search':
            try:
                name = normalize_query(qs.get('name', [''])[0])
                results = search_kind(name)
                self.send_json({'results': results, 'query': name})
            except ValueError as e:
                self.send_json({'error': str(e)}, 400)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/caution-search':
            try:
                name = normalize_query(qs.get('name', [''])[0])
                self.send_json(caution_search(name))
            except ValueError as e:
                self.send_json({'status': 'error', 'errorMessage': str(e)}, 400)
            except Exception as e:
                self.send_json({'status': 'error', 'errorMessage': str(e)}, 500)
            return

        if parsed.path == '/api/stock-code':
            try:
                name = normalize_query(qs.get('name', [''])[0])
                items = naver_stock_code(name)
                self.send_json({'items': items})
            except ValueError as e:
                self.send_json({'error': str(e)}, 400)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/stock-price':
            try:
                code = validate_stock_code(qs.get('code', [''])[0])
                prices = fetch_prices(code, count=20)
                thresholds = calc_thresholds(prices)
                self.send_json({'prices': prices[:16], 'thresholds': thresholds})
            except ValueError as e:
                self.send_json({'error': str(e)}, 400)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/stock-overview':
            try:
                code = validate_stock_code(qs.get('code', [''])[0])
                data = fetch_stock_overview(code)
                self.send_json(data)
            except ValueError as e:
                self.send_json({'error': str(e)}, 400)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/dart-search':
            try:
                bgn_de, end_de = validate_date_range(
                    qs.get('bgn_de', [''])[0],
                    qs.get('end_de', [''])[0],
                )
                data = search_disclosure(
                    corp_code=validate_corp_code(qs.get('corp_code', [''])[0], required=False),
                    bgn_de=bgn_de,
                    end_de=end_de,
                    page_no=parse_int_range(qs.get('page_no', ['1'])[0], 'page_no', 1, 1, 1000),
                    page_count=parse_int_range(qs.get('page_count', ['20'])[0], 'page_count', 20, 1, 100),
                    pblntf_ty=validate_dart_pblntf_ty(qs.get('pblntf_ty', [''])[0]),
                )
                self.send_json(data)
            except ValueError as e:
                self.send_json({'error': str(e)}, 400)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/financial-model':
            auth = auth_error(self.headers)
            if auth:
                status, message = auth
                self.send_financial_json({'error': message}, status); return
            limited = rate_limit_error(client_id(self.headers, getattr(self, 'client_address', None)))
            if limited:
                status, message = limited
                self.send_financial_json({'error': message}, status); return
            try:
                corp_code, fs_div, years = validate_params(
                    qs.get('corp_code', [''])[0],
                    qs.get('fs_div', ['CFS'])[0],
                    qs.get('years', ['5'])[0],
                )
            except ValueError:
                self.send_financial_json({'error': '잘못된 파라미터 형식'}, 400); return
            try:
                self.send_financial_json(build_model(corp_code, fs_div=fs_div, years=years))
            except Exception as e:
                self.send_financial_json({'error': str(e)}, 500)
            return

        super().do_GET()

    def end_headers(self):
        # 정적 자산은 versioned URL(query string)로 참조하므로 길게 캐시한다.
        path = urllib.parse.urlparse(getattr(self, 'path', '')).path
        if path.startswith('/assets/'):
            self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
        elif path in ('/', '/index.html'):
            self.send_header('Cache-Control', 'public, max-age=0, must-revalidate')
        elif path in ('/robots.txt', '/sitemap.xml'):
            self.send_header('Cache-Control', 'public, max-age=3600')
        elif path in ('/data/holidays.json', '/data/patchnotes.json'):
            self.send_header('Cache-Control', 'public, max-age=3600')
        if not path.startswith('/api/'):
            send_security_headers(self, csp=STATIC_CSP)
        super().end_headers()


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    with ThreadedServer((HOST, PORT), Handler) as httpd:
        print(f'✅ 서버 실행: http://{HOST}:{PORT}')
        httpd.serve_forever()
