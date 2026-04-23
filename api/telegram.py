"""
투자경고 해제일 계산기 — 텔레그램 봇 (Vercel Webhook)
종목명을 보내면 투자경고/위험 지정일, 해제 예상일, 기준가를 알려줍니다.
"""
from http.server import BaseHTTPRequestHandler
import hmac, json, os, re, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.holidays import add_trading_days, count_trading_days
from lib.krx import search_kind
from lib.naver import stock_code as naver_stock_code, fetch_prices, calc_thresholds, caution_search
from lib.cache import TTLCache
from lib.http_client import request_json
from lib.telegram_idempotency import claim_update, mark_update_done
from lib.timeouts import TELEGRAM_SEND_TIMEOUT
from lib.http_utils import (
    log_event,
    log_exception,
    safe_exception_text,
    send_text_headers,
    telegram_bot_url,
)
from lib.validation import normalize_query

# 동일 update_id 중복 처리 차단 (텔레그램 재시도 방어)
_seen_updates = TTLCache(ttl=600)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')
MAX_WEBHOOK_BODY_BYTES = _env_int('TELEGRAM_MAX_BODY_BYTES', 64 * 1024)
MAX_UPDATE_AGE_SECONDS = _env_int('TELEGRAM_MAX_UPDATE_AGE_SECONDS', 600)
ADMIN_CHAT_IDS = {
    int(v.strip()) for v in os.environ.get('TELEGRAM_ADMIN_CHAT_IDS', '').split(',')
    if re.fullmatch(r'-?\d+', v.strip())
}

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


def build_caution_message(d: dict) -> str:
    """투자주의 / 투자경고 지정예고 응답 → 텔레그램 메시지.

    d: lib.naver.caution_search() 의 반환 dict — status 가 분기 키.
    """
    status = d.get('status')
    query  = d.get('query', '')
    name   = d.get('stockName', query)

    if status == 'not_caution':
        return f'"{query}" — 현재 투자경고가 아님.'

    reason = d.get('designationReason', '')
    d_str  = d.get('latestDesignationDate', '')
    head_date = ''
    if d_str:
        try:
            head_date = f' ({sd(date.fromisoformat(d_str))})'
        except ValueError:
            head_date = ''

    active = d.get('activeNotice') or None

    def _notice_line(a: dict) -> str:
        try:
            nd = sd(date.fromisoformat(a['noticeDate']))
            fd = sd(date.fromisoformat(a['firstJudgmentDate']))
            ld = sd(date.fromisoformat(a['lastJudgmentDate']))
        except Exception:
            nd = a.get('noticeDate', ''); fd = a.get('firstJudgmentDate', ''); ld = a.get('lastJudgmentDate', '')
        return (f'지정예고 {nd} · 판단 {fd}~{ld} '
                f'(판단일 {a.get("judgmentDayIndex", 0)}/{a.get("judgmentWindowTotal", 10)})')

    if status == 'non_price_reason':
        return (
            f'🟡 {name} 투자주의{head_date}\n'
            f'사유: {reason}\n\n'
            '활성 지정예고 없음 — 가격 기반 투자경고 격상 조건(단기/중장기급등)은 적용되지 않습니다.'
        )

    if status in ('code_not_found', 'price_error'):
        err = d.get('errorMessage', '알 수 없는 오류')
        header = f'🟡 {name} 투자주의{head_date}\n'
        if active:
            header += _notice_line(active) + '\n'
        else:
            header += f'사유: {reason}\n'
        header += '\n'
        if status == 'code_not_found':
            header += '종목코드를 찾을 수 없어 격상 조건을 계산할 수 없습니다.'
        else:
            header += f'⚠️ 주가/지수 조회 불가: {err}'
        return header

    if status != 'ok':
        return f'⚠️ 처리 중 오류: {d.get("errorMessage", status)}'

    e = d['escalation']
    t_close = e['tClose']
    t_date  = date.fromisoformat(e['tDate'])
    idx_close = e.get('indexClose', 0)
    idx_sym = d.get('indexSymbol', '')

    lines = [f'🟡 {name} 투자주의']
    if active:
        lines.append(_notice_line(active))
    else:
        lines.append(f'사유: {reason}{head_date}')
    lines.append('')
    idx_txt = f'{idx_close:,.2f}' if isinstance(idx_close, (int, float)) else '-'
    lines.append(f'현재가 {t_close:,}원 · {idx_sym} {idx_txt}  ({sd(t_date)})')
    lines.append('')

    def _set_block(s: dict) -> list:
        head = '모두 충족 ✅' if s['allMet'] else '해당 없음'
        out = [f"*{s['label']}* — {head}"]
        for c in s['conditions']:
            mark = '✅' if c['met'] else '❌'
            out.append(f'  {mark} {c["label"]}')
            out.append(f'     {c["detail"]}')
        return out

    for s in e['sets']:
        lines.extend(_set_block(s))
        lines.append('')

    h = e.get('headline', {'verdict': 'none'})
    if h.get('verdict') == 'strong':
        matched = e['sets'][h['matchedSet']]
        lines.append(f'→ 투자경고 지정 예상 · {matched["label"]} 충족 🔴')
    else:
        lines.append('→ 투자경고 지정 미해당 🟢')
    return '\n'.join(lines)

# ── Telegram API ─────────────────────────────────────────────
def tg_send(chat_id: int, text: str):
    body = json.dumps({
        'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown',
    }).encode('utf-8')
    return request_json(
        'telegram',
        telegram_bot_url(BOT_TOKEN, 'sendMessage'),
        data=body,
        headers={'Content-Type': 'application/json'},
        timeout=TELEGRAM_SEND_TIMEOUT,
        retries=0,
    )

def tg_send_plain(chat_id: int, text: str):
    body = json.dumps({'chat_id': chat_id, 'text': text}).encode('utf-8')
    return request_json(
        'telegram',
        telegram_bot_url(BOT_TOKEN, 'sendMessage'),
        data=body,
        headers={'Content-Type': 'application/json'},
        timeout=TELEGRAM_SEND_TIMEOUT,
        retries=0,
    )


def _is_admin_chat(chat_id: int) -> bool:
    return chat_id in ADMIN_CHAT_IDS


def _is_fresh_update(msg: dict) -> bool:
    """Drop stale Telegram updates to reduce replay and delayed retry abuse."""
    msg_ts = msg.get('date')
    if not isinstance(msg_ts, int):
        return True
    now_ts = int(datetime.now(timezone.utc).timestamp())
    return abs(now_ts - msg_ts) <= MAX_UPDATE_AGE_SECONDS

# ── 업데이트 처리 ────────────────────────────────────────────
def do_search(chat_id: int, query: str):
    try:
        query = normalize_query(query)
    except ValueError:
        tg_send_plain(chat_id, '종목명을 입력해주세요.\n예: /warning 코셈')
        return

    try:
        tg_send_plain(chat_id, f'🔍 "{query}" 검색 중...')
    except Exception as e:
        log_event('warning', 'telegram_send_search_notice_failed',
                  error=safe_exception_text(e))

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
            return {'error': '종목코드를 찾을 수 없어 기준가를 계산할 수 없습니다.'}
        except Exception as e:
            message = safe_exception_text(e)
            log_event('warning', 'telegram_threshold_fetch_failed',
                      stock_name=warn.get('stockName', ''), error=message)
            return {'error': f'주가 조회 실패: {message}'}

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
    try:
        query = normalize_query(query)
    except ValueError:
        tg_send_plain(chat_id, '종목명을 입력해주세요.\n예: /info 삼성전자')
        return

    try:
        tg_send_plain(chat_id, f'📑 "{query}" 사업보고서 조회 중...')
    except Exception as e:
        log_event('warning', 'telegram_send_info_notice_failed',
                  error=safe_exception_text(e))

    try:
        codes = naver_stock_code(query)
    except Exception as e:
        log_exception('telegram_info_stock_lookup_failed')
        tg_send_plain(chat_id, f'❌ 종목 조회 오류: {safe_exception_text(e)}')
        return

    if not codes:
        tg_send_plain(chat_id, f'"{query}" — 종목을 찾을 수 없습니다.')
        return

    target = codes[0]
    stock_code = target['code']
    stock_name = target['name']
    log_event('info', 'telegram_info_target_selected',
              stock_name=stock_name, stock_code=stock_code)

    try:
        from lib.dart_report import summarize_business_report
        result = summarize_business_report(stock_code, stock_name)
    except Exception as e:
        log_exception('telegram_info_summary_failed',
                      stock_name=stock_name, stock_code=stock_code)
        tg_send_plain(chat_id, f'❌ 사업보고서 요약 실패: {safe_exception_text(e)}')
        return

    if 'error' in result:
        log_event('warning', 'telegram_info_summary_returned_error',
                  stock_name=stock_name, stock_code=stock_code,
                  error=result['error'])
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
            tg_send_plain(chat_id, f'⚠️ 결과 전송 오류: {safe_exception_text(e)}')


def do_caution(chat_id: int, query: str):
    try:
        query = normalize_query(query)
    except ValueError:
        tg_send_plain(chat_id, '종목명을 입력해주세요.\n예: /caution 코셈')
        return

    try:
        tg_send_plain(chat_id, f'🔍 "{query}" 투자주의 조회 중...')
    except Exception as e:
        log_event('warning', 'telegram_send_caution_notice_failed',
                  error=safe_exception_text(e))

    try:
        result = caution_search(query)
    except Exception as e:
        tg_send_plain(chat_id, f'❌ 조회 오류: {safe_exception_text(e)}')
        return

    msg = build_caution_message(result)
    try:
        tg_send(chat_id, msg)
    except Exception:
        try:
            tg_send_plain(chat_id, msg)
        except Exception as e:
            tg_send_plain(chat_id, f'⚠️ 결과 전송 오류: {safe_exception_text(e)}')


def _process_update_body(update: dict):
    if not isinstance(update, dict):
        return

    msg = update.get('message') or update.get('edited_message')
    if not msg:
        return
    if not _is_fresh_update(msg):
        return

    chat = msg.get('chat') or {}
    chat_id = chat.get('id')
    if not isinstance(chat_id, int):
        return
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
            '/info `종목명` — 사업보고서 요약 (관리자)\n'
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
            '`/caution 종목명` — "투자경고 지정예고" 종목의 실제 지정 여부 점검\n'
            '예: `/caution 코셈`\n'
            'KRX 공식 [1] 또는 [2] 중 하나라도 모두 충족 시 "지정 예상":\n'
            '  \\[1] 단기급등: T/T\\-5 ≥ 160%, 15일 최고, 지수 ×5\n'
            '  \\[2] 중장기급등: T/T\\-15 ≥ 200%, 15일 최고, 지수 ×3\n'
            '지정예고 외 사유(소수계좌 등)는 가격 조건 적용되지 않음\n\n'
            '*3. 불건전 요건 안내*\n'
            '`/bulgunjeon` — KRX 불공정거래 판단 기준 참고용\n\n'
            '*4. 사업보고서 요약*\n'
            '`/info 종목명` — 가장 최근 사업보고서를 10줄로 요약 (관리자 전용)\n'
            '예: `/info 삼성전자`\n\n'
            '*투자경고 해제 조건 안내*\n'
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
        if not _is_admin_chat(chat_id):
            tg_send_plain(chat_id, '이 명령어는 관리자만 사용할 수 있습니다.')
            return
        try:
            do_info(chat_id, query)
        except Exception as e:
            log_exception('telegram_info_unhandled')
            try:
                tg_send_plain(chat_id, f'❌ 처리 중 오류: {safe_exception_text(e)}')
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

    chat_type = chat.get('type', 'private')
    if chat_type == 'private':
        do_search(chat_id, text)


def process_update(update: dict):
    if not isinstance(update, dict):
        return

    update_id = update.get('update_id')
    local_key = f'upd:{update_id}' if update_id is not None else ''
    claimed = False
    if update_id is not None:
        if _seen_updates.get(local_key):
            return  # 이미 처리한 update — 텔레그램 재시도 중복 방지
        if not claim_update(update_id):
            _seen_updates.set(local_key, True)
            return
        _seen_updates.set(local_key, 'processing')
        claimed = True

    try:
        _process_update_body(update)
    except Exception:
        if local_key:
            _seen_updates.delete(local_key)
        raise

    if claimed:
        mark_update_done(update_id)
        _seen_updates.set(local_key, True)

# ── Vercel Handler ───────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def _respond_text(self, status: int, body: bytes):
        self.send_response(status)
        send_text_headers(self, cors=False, cache_control='no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not WEBHOOK_SECRET:
            self._respond_text(503, b'Webhook secret is not configured.')
            return

        token = self.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not hmac.compare_digest(token, WEBHOOK_SECRET):
            self._respond_text(403, b'Forbidden')
            return

        ctype = self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if ctype != 'application/json':
            self._respond_text(415, b'Unsupported Media Type')
            return

        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self._respond_text(400, b'Bad Content-Length')
            return

        if length <= 0 or length > MAX_WEBHOOK_BODY_BYTES:
            self._respond_text(413, b'Payload Too Large')
            return

        body   = self.rfile.read(length)

        # Vercel Python runtime은 HTTP 응답 완료 후 함수를 suspend하므로
        # 처리를 먼저 끝낸 뒤 200 OK를 반환해야 한다.
        # 60초 초과 시 텔레그램이 재시도를 보내지만 update_id 중복 차단으로 방어.
        try:
            update = json.loads(body)
            process_update(update)
        except json.JSONDecodeError:
            self._respond_text(400, b'Invalid JSON')
            return
        except Exception as e:
            log_event('error', 'telegram_update_failed', error=safe_exception_text(e))

        self._respond_text(200, b'OK')

    def do_GET(self):
        status = b'configured' if WEBHOOK_SECRET else b'missing secret'
        self._respond_text(200, b'Telegram bot webhook is ' + status + b'.')

    def log_message(self, *args):
        pass
