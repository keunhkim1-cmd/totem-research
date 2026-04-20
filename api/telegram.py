"""
투자경고 해제일 계산기 — 텔레그램 봇 (Vercel Webhook)
종목명을 보내면 투자경고/위험 지정일, 해제 예상일, 기준가를 알려줍니다.
"""
from http.server import BaseHTTPRequestHandler
import json, os, urllib.request, re, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.holidays import add_trading_days, count_trading_days
from lib.krx import search_kind, search_kind_caution
from lib.naver import stock_code as naver_stock_code, fetch_prices, calc_thresholds, calc_caution_escalation
from lib.dart_report import summarize_business_report
from lib.cache import TTLCache

# 동일 update_id 중복 처리 차단 (텔레그램 재시도 방어)
_seen_updates = TTLCache(ttl=600)

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TG_API    = f'https://api.telegram.org/bot{BOT_TOKEN}'
WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')

# ── 메시지 포맷 ──────────────────────────────────────────────
def sd(d: date) -> str:
    """date → M/D 형식"""
    return f'{d.month}/{d.day}'

def vlen(s: str) -> int:
    """모바일 모노스페이스 시각 너비 (전각=2, 반각=1)"""
    w = 0
    for c in s:
        eaw = unicodedata.east_asian_width(c)
        w += 2 if eaw in ('W', 'F') else 1
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


def build_caution_message(stock_name: str, warn: dict, escalation: dict | None) -> str:
    """투자주의 → 투자경고 격상 여부 메시지."""
    d_str  = warn['latestDesignationDate']
    d_date = date.fromisoformat(d_str)
    lines  = [f'🟡 {stock_name} 투자주의', '']

    if not escalation or 'error' in (escalation or {}):
        lines.append(f'```\n지정일  {sd(d_date)}\n```')
        if escalation and 'error' in escalation:
            lines.append(f'⚠️ 주가 조회 불가: {escalation["error"]}')
        lines.append('')
        lines.append('불건전 요건은 /bulgunjeon 을 참고')
        return '\n'.join(lines)

    criteria = escalation['criteria']
    count15  = warn.get('recent15dCount', 0)

    # 각 조건의 최종 결과(met) 확정
    for c in criteria:
        if c['gating'] == 'count':
            c['countActual'] = count15
            c['met'] = bool(c['priceMet']) and count15 >= c['countRequired']
        else:
            # 'none' & 'bulgunjeon' 모두 가격 결과만 표기.
            # 불건전은 시스템에서 판정 불가 — 사용자가 /bulgunjeon 로 수동 확인.
            c['met'] = bool(c['priceMet'])

    # 헤드라인 계층화: 확정 매칭(가격만/가격+카운트) vs 조건부 매칭(가격+불건전)
    strong_idx = next((i for i, c in enumerate(criteria)
                       if c['met'] and c['gating'] != 'bulgunjeon'), None)
    soft_idx   = next((i for i, c in enumerate(criteria)
                       if c['met'] and c['gating'] == 'bulgunjeon'), None)

    cur = escalation['tClose']
    t_d = date.fromisoformat(escalation['tDate'])

    lines.append(f'현재가 {cur:,}원 ({sd(t_d)})')
    lines.append('')

    # 상세 표
    def ci(c):
        if c.get('threshold') is None:
            return '—'
        return '✅' if c['met'] else '❌'

    row_labels = [
        '① 초단기(3일 100%)',
        '② 단기(5일 60%)',
        '③ 단기&불건전(5일 45%)',
        '④ 장기(15일 100%)',
        '⑤ 장기&불건전(15일 75%)',
        '⑥ 반복(15일 75%)',
        '⑦ 초장기&불건전(1년 200%)',
    ]
    price_strs = []
    for c in criteria:
        if c.get('threshold') is None:
            price_strs.append('—')
        elif c['gating'] == 'count':
            price_strs.append(f"{c['threshold']:,}원·{c['countActual']}/{c['countRequired']}회")
        else:
            price_strs.append(f"{c['threshold']:,}원")

    lw   = max(vlen(lbl) for lbl in row_labels) + 1
    pw_v = max(vlen(p) for p in price_strs)
    sep  = lw + 2 + pw_v + 3 + vlen('결과')

    def row(label, price, icon):
        return vpad_l(label, lw) + '  ' + vpad_r(price, pw_v) + '   ' + icon

    block_lines = [
        vpad_l('조건', lw) + '  ' + vpad_r('기준가', pw_v) + '   결과',
        '─' * sep,
    ]
    for lbl, p, c in zip(row_labels, price_strs, criteria):
        block_lines.append(row(lbl, p, ci(c)))
    lines.append('```\n' + '\n'.join(block_lines) + '\n```')
    lines.append('')

    if strong_idx is not None:
        thresh = criteria[strong_idx]['threshold']
        lines.append(f'→ 투자경고 지정 예상 (기준가 {thresh:,}원) 🔴')
    elif soft_idx is not None:
        thresh = criteria[soft_idx]['threshold']
        lines.append(f'→ 불건전 요건 시 투자경고 지정 예상 (기준가 {thresh:,}원) 🟠')
    else:
        lines.append('→ 투자경고 미해당 🟢')
    lines.append('')
    lines.append('불건전 요건은 /bulgunjeon 을 참고')

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
    except Exception as e:
        print(f'검색 중 메시지 전송 실패: {e}', flush=True)

    try:
        results = search_kind(query)
    except Exception as e:
        tg_send_plain(chat_id, f'❌ KRX 조회 오류: {e}')
        return

    if not results:
        tg_send_plain(chat_id, f'"{query}" — 현재 투자경고가 아님.')
        return

    # 주가 조회를 병렬 실행하여 응답 속도 개선
    def _fetch_thresholds(warn):
        try:
            codes = naver_stock_code(warn['stockName'])
            if codes:
                prices = fetch_prices(codes[0]['code'], count=20)
                return calc_thresholds(prices)
        except Exception as e:
            print(f'주가 조회 실패: {e}', flush=True)
        return None

    targets = results[:3]
    with ThreadPoolExecutor(max_workers=3) as pool:
        threshold_list = list(pool.map(_fetch_thresholds, targets))

    for warn, thresholds in zip(targets, threshold_list):
        try:
            tg_send(chat_id, build_message(warn['stockName'], warn, thresholds))
        except Exception:
            try:
                tg_send_plain(chat_id, build_message(warn['stockName'], warn, thresholds))
            except Exception as e:
                tg_send_plain(chat_id, f'⚠️ 결과 전송 오류: {e}')

    if len(results) > 3:
        tg_send_plain(chat_id,
            f'검색 결과 {len(results)}개 중 상위 3개만 표시했습니다.\n'
            '더 정확한 종목명으로 다시 검색해주세요.')


def do_info(chat_id: int, query: str):
    import traceback
    if not query:
        tg_send_plain(chat_id, '종목명을 입력해주세요.\n예: /info 삼성전자')
        return

    try:
        tg_send_plain(chat_id, f'📑 "{query}" 사업보고서 조회 중...')
    except Exception as e:
        print(f'/info 안내 메시지 전송 실패: {e}', flush=True)

    try:
        codes = naver_stock_code(query)
    except Exception as e:
        print(f'[info] 네이버 종목조회 오류: {traceback.format_exc()}', flush=True)
        tg_send_plain(chat_id, f'❌ 종목 조회 오류: {e}')
        return

    if not codes:
        tg_send_plain(chat_id, f'"{query}" — 종목을 찾을 수 없습니다.')
        return

    target = codes[0]
    stock_code = target['code']
    stock_name = target['name']
    print(f'[info] 대상 종목: {stock_name} ({stock_code})', flush=True)

    try:
        result = summarize_business_report(stock_code, stock_name)
    except Exception as e:
        print(f'[info] summarize 예외: {traceback.format_exc()}', flush=True)
        tg_send_plain(chat_id, f'❌ 사업보고서 요약 실패: {e}')
        return

    if 'error' in result:
        print(f'[info] 요약 실패: {result["error"]}', flush=True)
        tg_send_plain(chat_id, f'❌ {result["error"]}')
        return

    rcept_dt = result.get('rcept_dt', '')
    date_str = f'{rcept_dt[:4]}.{rcept_dt[4:6]}.{rcept_dt[6:8]}' if len(rcept_dt) == 8 else rcept_dt
    rcept_no = result.get('rcept_no', '')
    viewer_url = f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}' if rcept_no else ''

    body = (
        f'📑 *{stock_name} 사업보고서 요약*\n\n'
        f'{result["summary"]}\n\n'
        f'_공시일: {date_str}_'
    )
    if viewer_url:
        body += f'\n[원문 보기]({viewer_url})'

    try:
        tg_send(chat_id, body)
    except Exception:
        try:
            plain = f'📑 {stock_name} 사업보고서 요약\n\n{result["summary"]}\n\n공시일: {date_str}'
            if viewer_url:
                plain += f'\n원문: {viewer_url}'
            tg_send_plain(chat_id, plain)
        except Exception as e:
            tg_send_plain(chat_id, f'⚠️ 결과 전송 오류: {e}')


def do_caution(chat_id: int, query: str):
    if not query:
        tg_send_plain(chat_id, '종목명을 입력해주세요.\n예: /caution 코셈')
        return

    try:
        tg_send_plain(chat_id, f'🔍 "{query}" 투자주의 조회 중...')
    except Exception as e:
        print(f'/caution 안내 메시지 전송 실패: {e}', flush=True)

    try:
        results = search_kind_caution(query)
    except Exception as e:
        tg_send_plain(chat_id, f'❌ KRX 조회 오류: {e}')
        return

    if not results:
        tg_send_plain(chat_id, f'"{query}" — 현재 투자주의가 아님.')
        return

    warn = results[0]
    escalation = None
    try:
        codes = naver_stock_code(warn['stockName'])
        if codes:
            # 초장기(1년 200%) 조건 판정을 위해 250거래일 이상 필요 → 260일로 여유 있게 조회
            prices = fetch_prices(codes[0]['code'], count=260)
            escalation = calc_caution_escalation(prices)
    except Exception as e:
        print(f'주가 조회 실패: {e}', flush=True)
        escalation = {'error': str(e)}

    try:
        tg_send(chat_id, build_caution_message(warn['stockName'], warn, escalation))
    except Exception:
        try:
            tg_send_plain(chat_id, build_caution_message(warn['stockName'], warn, escalation))
        except Exception as e:
            tg_send_plain(chat_id, f'⚠️ 결과 전송 오류: {e}')


def process_update(update: dict):
    update_id = update.get('update_id')
    if update_id is not None:
        key = f'upd:{update_id}'
        if _seen_updates.get(key):
            return  # 이미 처리한 update — 텔레그램 재시도 중복 방지
        _seen_updates.set(key, True)

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
            '/caution `종목명` — 투자경고 지정 예상 점검\n'
            '/bulgunjeon — 불건전 요건 안내\n'
            '/info `종목명` — 사업보고서 요약\n'
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
            '*2. 투자경고 지정 예상*\n'
            '`/caution 종목명` — 투자주의 종목의 경고 격상 요건 점검\n'
            '예: `/caution 코셈`\n'
            '4가지 요건 중 하나라도 충족 시 "지정 예상":\n'
            '① 초단기 3일 100% ② 단기 5일 60%\n'
            '③ 장기 15일 100% ④ 반복 15일 75% \\+ 5회\n\n'
            '*3. 불건전 요건 안내*\n'
            '`/bulgunjeon` — 불공정거래 판단 기준 참고용\n\n'
            '*4. 사업보고서 요약*\n'
            '`/info 종목명` — 가장 최근 사업보고서를 10줄로 요약\n'
            '예: `/info 삼성전자`\n\n'
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

    if text.startswith('/info'):
        query = re.sub(r'^/\S+\s*', '', text).strip()
        try:
            do_info(chat_id, query)
        except Exception as e:
            import traceback
            print(f'[info] do_info 최상위 예외: {traceback.format_exc()}', flush=True)
            try:
                tg_send_plain(chat_id, f'❌ 처리 중 오류: {e}')
            except Exception:
                pass
        return

    if text.startswith('/caution'):
        query = re.sub(r'^/\S+\s*', '', text).strip()
        do_caution(chat_id, query)
        return

    if text.startswith('/bulgunjeon'):
        body = (
            '📋 *불건전 요건*\n\n'
            '*1. 5일 or 15일 상승 & 불건전요건*\n'
            '• 최근 5일(15일) 중 전일 대비 주가 상승하고, 특정 계좌(군)이 일중 전체 최고가 매수거래량의 10% 이상 매수일수가 2일(4일) 이상\n'
            '• 최근 5일(15일) 중 특정 계좌(군)의 시세영향력을 고려한 매수관여율이 위원장이 정하는 기준에 해당하는 일수가 2일(4일) 이상\n'
            '• 최근 5일(15일) 중 특정계좌(군)의 시가 또는 종가의 매수관여율이 20% 이상인 일수가 2일(4일) 이상\n'
            '→ 3가지 요건 중 하나에 해당하는 경우\n\n'
            '*2. 1년간 상승 & 불건전요건*\n'
            '• 최근 15일 중 시세영향력을 고려한 매수관여율 상위 10개 계좌의 관여율이 일정 수준 이상인 경우에 해당하는 일수가 4일 이상'
        )
        try:
            tg_send(chat_id, body)
        except Exception:
            tg_send_plain(chat_id, body.replace('*', ''))
        return

    if text.startswith('/web'):
        tg_send(chat_id,
            '🌐 *투자경고 계산기 웹버전*\n'
            'https://shamanism-research.vercel.app/')
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
        if WEBHOOK_SECRET:
            token = self.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
            if token != WEBHOOK_SECRET:
                self.send_response(403)
                self.end_headers()
                return
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)

        # Vercel Python runtime은 HTTP 응답 완료 후 함수를 suspend하므로
        # 처리를 먼저 끝낸 뒤 200 OK를 반환해야 한다.
        # 60초 초과 시 텔레그램이 재시도를 보내지만 update_id 중복 차단으로 방어.
        try:
            update = json.loads(body)
            process_update(update)
        except Exception as e:
            print(f'Update error: {e}', flush=True)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Telegram bot webhook is active.')

    def log_message(self, *args):
        pass
