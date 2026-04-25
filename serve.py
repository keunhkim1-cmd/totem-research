#!/usr/bin/env python3
"""
투자경고 해제일 계산기 - 로컬 개발 서버
- 정적 파일 서빙 (index.html)
- API 프록시 (/api/warn-search, /api/stock-code, /api/stock-price)
"""
import http.server
import socketserver
import os
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

from lib.api_routes import ROUTES_BY_PATH, dispatch
from lib.http_utils import (
    STATIC_CSP,
    send_options_response,
    send_security_headers,
)

HOST = os.environ.get('HOST', '127.0.0.1')
PORT = _env_int('PORT', 5173)
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

    def do_OPTIONS(self):
        parsed = urllib.parse.urlparse(self.path)
        route = ROUTES_BY_PATH.get(parsed.path)
        if route:
            send_options_response(self, allow_headers=route.allow_headers)
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
        route = ROUTES_BY_PATH.get(parsed.path)
        if route:
            qs = urllib.parse.parse_qs(parsed.query)
            dispatch(self, route, qs)
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
