"""
진단용 엔드포인트 — 배포 후 /api/debug 를 브라우저에서 열어 확인
"""
from http.server import BaseHTTPRequestHandler
import json, os, urllib.request

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        result = {
            'token_set': bool(token),
        }

        # 토큰이 있으면 실제 Telegram API 호출 테스트
        if token:
            try:
                req = urllib.request.Request(
                    f'https://api.telegram.org/bot{token}/getMe',
                    headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read())
                result['telegram_api'] = 'OK'
                result['bot_name'] = data['result'].get('first_name', '')
                result['bot_username'] = data['result'].get('username', '')
            except Exception as e:
                result['telegram_api'] = f'ERROR: {e}'
        else:
            result['telegram_api'] = 'SKIP (토큰 없음)'

        body = json.dumps(result, ensure_ascii=False, indent=2).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
