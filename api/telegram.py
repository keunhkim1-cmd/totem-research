"""
투자경고 해제일 계산기 — 텔레그램 봇 (Vercel Webhook)
종목명을 보내면 투자경고/위험 지정일, 해제 예상일, 기준가를 알려줍니다.
"""
from http.server import BaseHTTPRequestHandler
import json, os, urllib.request, re, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.holidays import add_trading_days, count_trading_days
from lib.krx import search_kind
from lib.naver import stock_code as naver_stock_code, fetch_prices, calc_thresholds

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_API    = f'https://api.telegram.org/bot{BOT_TOKEN}'

# ── 메시지 포맷 ──────────────────────────────────────────────
def sd(d: date) -> str:
    """date → M/D 형식"""
    return f'{d.month}/{d.day}'

def vlen(s: str) -> int:
    """모바일 모노스페이스 시각 너비 (한글·원문자·이모지=2, ASCII=1)"""
    w = 0
    for c in s:
        cp = ord(c)
        if (0xAC00 <= cp <= 0xD7AF or
            0x1100 <= cp <= 0x11FF or
            0x3000 <= cp <= 0x9FFF or
            0xF900 <= cp <= 0xFAFF or
            0x2460 <= cp <= 0x24FF or
            0x2700 <= cp <= 0x27BF or
            cp >= 0x1F000):
            w += 2
        else:
            w += 1
    return w

def vpad_l(s: str, width: int) -> str:
    return s + ' ' * max(0, width - vlen(s))

def vpad_r(s: str, width: int) -> str:
    return ' ' * max(0, width - vlen(s)) + s

def build_message(stock_name: str, warn: dict, thresholds: dict | None) -> str:
    d_str   = warn['designationDate']
    d_date  = date.fromisoformat(d_str)
    today   = date.today()
    release = add_trading_days(d_date, 10)
    elapsed = count_trading_days(d_date, today) - 1
    diff    = (release - today).days

    if diff > 0:
        dday = f'D-{diff}'
    elif diff == 0:
        dday = 'D-Day'
    else:
        dday = f'D+{abs(diff)}'

    level_emoji = '🟠' if warn['level'] == '투자경고' else '🔴'
    lines = [f'{level_emoji} {stock_name} {warn["level"]}  |  {dday}', '']

    if thresholds and 'error' not in thresholds:
        t_d   = date.fromisoformat(thresholds['tDate'])
        cur   = thresholds['tClose']
        c1, c2, c3 = thresholds['cond1'], thresholds['cond2'], thresholds['cond3']
        ci    = lambda c: '✅' if c else '❌'

        p1 = f"{thresholds['thresh1']:,}원"
        p2 = f"{thresholds['thresh2']:,}원"
        p3 = f"{thresholds['thresh3']:,}원"
        lw   = max(vlen('① T-5'), vlen('② T-15'), vlen('③ 고점')) + 1
        pw_v = max(vlen(p1), vlen(p2), vlen(p3))
        sep  = lw + 2 + pw_v + 3 + vlen('결과')

        def row(label, price, icon):
            return vpad_l(label, lw) + '  ' + vpad_r(price, pw_v) + '   ' + icon

        block = '\n'.join([
            f'현재가  {cur:,}원  ({sd(t_d)})',
            f'지정일  {sd(d_date)}  →  해제 판단일  {sd(release)}',
            f'경과    {elapsed} / 10 거래일',
            '',
            vpad_l('조건', lw) + '  ' + vpad_r('기준가', pw_v) + '   결과',
            '─' * sep,
            row('① T-5',  p1, ci(c1)),
            row('② T-15', p2, ci(c2)),
            row('③ 고점', p3, ci(c3)),
        ])
        lines.append(f'```\n{block}\n```')
        lines.append('')

        unmet = sum(1 for c in [c1, c2, c3] if not c)
        if thresholds['allMet']:
            lines.append('→ 3가지 모두 해당 · 경고 유지 중 🔴')
        else:
            lines.append(f'→ {unmet}가지 미해당 · {sd(release)} 해제 가능 🟢')
    else:
        block = '\n'.join([
            f'지정일  {sd(d_date)}  →  해제 판단일  {sd(release)}',
            f'경과    {elapsed} / 10 거래일',
        ])
        lines.append(f'```\n{block}\n```')
        if thresholds and 'error' in thresholds:
            lines.append(f'⚠️ 주가 조회 불가: {thresholds["error"]}')

    return '\n'.join(lines)

# ── Telegram API ─────────────────────────────────────────────
def tg_send(chat_id: int, text: str):
    body = json.dumps({
        'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown',
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{TG_API}/sendMessage', data=body,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def tg_send_plain(chat_id: int, text: str):
    body = json.dumps({'chat_id': chat_id, 'text': text}).encode('utf-8')
    req  = urllib.request.Request(
        f'{TG_API}/sendMessage', data=body,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# ── 업데이트 처리 ────────────────────────────────────────────
def do_search(chat_id: int, query: str):
    if not query:
        tg_send_plain(chat_id, '종목명을 입력해주세요.\n예: /warning 코셈')
        return

    try:
        tg_send_plain(chat_id, f'🔍 "{query}" 검색 중...')
    except Exception:
        pass

    try:
        results = search_kind(query)
    except Exception as e:
        tg_send_plain(chat_id, f'❌ KRX 조회 오류: {e}')
        return

    if not results:
        tg_send_plain(chat_id, f'"{query}" — 현재 투자경고가 아님.')
        return

    for warn in results[:3]:
        stock_name = warn['stockName']
        thresholds = None
        try:
            codes = naver_stock_code(stock_name)
            if codes:
                prices = fetch_prices(codes[0]['code'], count=20)
                thresholds = calc_thresholds(prices)
        except Exception as e:
            print(f'주가 조회 실패: {e}')

        try:
            tg_send(chat_id, build_message(stock_name, warn, thresholds))
        except Exception:
            try:
                tg_send_plain(chat_id, build_message(stock_name, warn, thresholds))
            except Exception as e:
                tg_send_plain(chat_id, f'⚠️ 결과 전송 오류: {e}')

    if len(results) > 3:
        tg_send_plain(chat_id,
            f'검색 결과 {len(results)}개 중 상위 3개만 표시했습니다.\n'
            '더 정확한 종목명으로 다시 검색해주세요.')


def process_update(update: dict):
    msg = update.get('message') or update.get('edited_message')
    if not msg:
        return
    chat_id = msg['chat']['id']
    text    = msg.get('text', '').strip()

    if not text:
        return

    text = re.sub(r'@\w+', '', text).strip()

    if text.startswith('/start'):
        tg_send(chat_id,
            '📈 *투자경고 해제일 계산기*\n\n'
            '투자경고/위험 종목의 해제 예상일과 기준가를 알려드립니다.\n\n'
            '*명령어*\n'
            '/warning `종목명` — 종목 투자경고 조회\n'
            '/help — 사용법 안내\n\n'
            '또는 종목명을 바로 입력해도 됩니다.\n'
            '예: `코셈`, `레이저쎌`')
        return

    if text.startswith('/help') or text.startswith('/도움말'):
        tg_send(chat_id,
            '📖 *사용법*\n\n'
            '*1. 종목 검색*\n'
            '`/warning 종목명` 또는 종목명을 직접 입력\n'
            '예: `/warning 코셈` 또는 `코셈`\n\n'
            '*해제 조건 안내*\n'
            '아래 3가지 중 하나라도 미해당 시 다음 거래일 해제:\n'
            '① 현재가 ≥ T\\-5 종가의 145%\n'
            '② 현재가 ≥ T\\-15 종가의 175%\n'
            '③ 현재가 ≥ 최근 15일 최고가\n\n'
            '📊 데이터 출처: KRX KIND, 네이버 금융')
        return

    if text.startswith('/warning'):
        query = re.sub(r'^/\S+\s*', '', text).strip()
        do_search(chat_id, query)
        return

    if text.startswith('/'):
        tg_send_plain(chat_id, '알 수 없는 명령어입니다.\n/help 로 사용법을 확인하세요.')
        return

    chat_type = msg['chat'].get('type', 'private')
    if chat_type == 'private':
        do_search(chat_id, text)

# ── Vercel Handler ───────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            update = json.loads(body)
            process_update(update)
        except Exception as e:
            print(f'Update error: {e}')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Telegram bot webhook is active.')

    def log_message(self, *args):
        pass
