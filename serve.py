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

from lib.krx import search_kind
from lib.naver import stock_code as naver_stock_code, fetch_prices, calc_thresholds

PORT = 5173
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, fmt, *args):
        print(f'[{self.address_string()}] {fmt % args}')

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/api/warn-search':
            name = qs.get('name', [''])[0].strip()
            if not name:
                self.send_json({'error': '종목명을 입력하세요.'}, 400); return
            try:
                results = search_kind(name)
                self.send_json({'results': results, 'query': name})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/stock-code':
            name = qs.get('name', [''])[0].strip()
            if not name:
                self.send_json({'error': '종목명을 입력하세요.'}, 400); return
            try:
                items = naver_stock_code(name)
                self.send_json({'items': items})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/stock-price':
            code = qs.get('code', [''])[0].strip()
            if not code:
                self.send_json({'error': '종목코드를 입력하세요.'}, 400); return
            try:
                prices = fetch_prices(code, count=20)
                thresholds = calc_thresholds(prices)
                self.send_json({'prices': prices[:16], 'thresholds': thresholds})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        super().do_GET()


if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', PORT), Handler) as httpd:
        print(f'✅ 서버 실행: http://localhost:{PORT}')
        httpd.serve_forever()
