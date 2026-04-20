"""텔레그램 봇 명령 드롭다운 등록 (setMyCommands API).

명령 목록을 수정한 뒤 이 스크립트를 한 번 실행하면 텔레그램 클라이언트
드롭다운이 갱신된다. .env 또는 환경변수에서 TELEGRAM_BOT_TOKEN을 읽는다.

실행:
    python3 scripts/set_telegram_commands.py
"""
import json
import os
import sys
import urllib.request

COMMANDS = [
    {'command': 'warning',    'description': '투자경고/위험 해제일 계산'},
    {'command': 'caution',    'description': '투자경고 지정 예상 점검 (투자주의 종목)'},
    {'command': 'bulgunjeon', 'description': '불건전 요건 안내'},
    {'command': 'info',       'description': '사업보고서 요약'},
    {'command': 'web',        'description': '웹버전 링크'},
    {'command': 'help',       'description': '사용법 안내'},
    {'command': 'start',      'description': '봇 시작'},
]


def load_token() -> str:
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if token:
        return token
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise RuntimeError('TELEGRAM_BOT_TOKEN not found in env or .env')


def main():
    token = load_token()
    body = json.dumps({'commands': COMMANDS}).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/setMyCommands',
        data=body,
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.loads(r.read())
    if not resp.get('ok'):
        print('FAIL:', resp, file=sys.stderr)
        sys.exit(1)
    print(f'OK — {len(COMMANDS)} commands registered:')
    for c in COMMANDS:
        print(f"  /{c['command']:<12} — {c['description']}")


if __name__ == '__main__':
    main()
