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
import re
import urllib.parse

from lib.krx import search_kind
from lib.naver import stock_code as naver_stock_code, fetch_prices, calc_thresholds, fetch_stock_overview
from lib.dart import search_disclosure
from lib.financial_model import build_model

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
            if not re.match(r'^\d{6}$', code):
                self.send_json({'error': '잘못된 종목코드 형식'}, 400); return
            try:
                prices = fetch_prices(code, count=20)
                thresholds = calc_thresholds(prices)
                self.send_json({'prices': prices[:16], 'thresholds': thresholds})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/stock-overview':
            code = qs.get('code', [''])[0].strip()
            if not re.match(r'^\d{6}$', code):
                self.send_json({'error': '잘못된 종목코드 형식'}, 400); return
            try:
                data = fetch_stock_overview(code)
                self.send_json(data)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/dart-search':
            try:
                data = search_disclosure(
                    corp_code=qs.get('corp_code', [''])[0],
                    bgn_de=qs.get('bgn_de', [''])[0].strip(),
                    end_de=qs.get('end_de', [''])[0].strip(),
                    page_no=int(qs.get('page_no', ['1'])[0]),
                    page_count=min(int(qs.get('page_count', ['20'])[0]), 100),
                    pblntf_ty=qs.get('pblntf_ty', [''])[0].strip(),
                )
                self.send_json(data)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if parsed.path == '/api/financial-model':
            corp_code = qs.get('corp_code', [''])[0].strip()
            fs_div = qs.get('fs_div', ['CFS'])[0].strip().upper()
            try:
                years = max(2, min(7, int(qs.get('years', ['5'])[0])))
            except ValueError:
                years = 5
            if not re.match(r'^\d{8}$', corp_code) or fs_div not in ('CFS', 'OFS'):
                self.send_json({'error': '잘못된 파라미터 형식'}, 400); return
            try:
                self.send_json(build_model(corp_code, fs_div=fs_div, years=years))
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        super().do_GET()

    def end_headers(self):
        # 정적 JSON 데이터에 캐시 헤더 추가
        path = urllib.parse.urlparse(self.path).path
        if path.startswith('/data/') and path.endswith('.json'):
            self.send_header('Cache-Control', 'public, max-age=3600')
        super().end_headers()


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    with ThreadedServer(('', PORT), Handler) as httpd:
        print(f'✅ 서버 실행: http://localhost:{PORT}')
        httpd.serve_forever()
