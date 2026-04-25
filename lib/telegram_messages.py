"""Telegram response message builders."""
import unicodedata
from datetime import date

from lib.holidays import add_trading_days, count_trading_days
from lib.warning_policy import T5_LOOKBACK, T15_LOOKBACK


def sd(d: date) -> str:
    """Format a date as M/D for compact Telegram output."""
    return f'{d.month}/{d.day}'


def vlen(s: str) -> int:
    """Visual monospace width for Korean mobile Telegram clients."""
    width = 0
    for char in s:
        eaw = unicodedata.east_asian_width(char)
        width += 2 if eaw in ('W', 'F') else 1
    return width


def vpad_l(s: str, width: int) -> str:
    return s + ' ' * max(0, width - vlen(s))


def vpad_r(s: str, width: int) -> str:
    return ' ' * max(0, width - vlen(s)) + s


def build_warning_message(stock_name: str, warn: dict, thresholds: dict | None) -> str:
    d_str = warn['designationDate']
    d_date = date.fromisoformat(d_str)
    today = date.today()
    release = add_trading_days(d_date, 10)
    elapsed = count_trading_days(d_date, today) - 1
    diff = (release - today).days

    if diff > 0:
        dday = f'D-{diff}'
    elif diff == 0:
        dday = 'D-Day'
    else:
        dday = f'D+{abs(diff)}'

    level_emoji = '🟠' if warn['level'] == '투자경고' else '🔴'
    lines = [f'{level_emoji} {stock_name} {warn["level"]}  |  {dday}', '']

    if thresholds and 'error' not in thresholds:
        t_d = date.fromisoformat(thresholds['tDate'])
        cur = thresholds['tClose']
        c1, c2, c3 = thresholds['cond1'], thresholds['cond2'], thresholds['cond3']
        ci = lambda c: '✅' if c else '❌'

        p1 = f"{thresholds['thresh1']:,}원"
        p2 = f"{thresholds['thresh2']:,}원"
        p3 = f"{thresholds['thresh3']:,}원"
        l1 = f'① T-{T5_LOOKBACK}'
        l2 = f'② T-{T15_LOOKBACK}'
        l3 = '③ 고점'
        lw = max(vlen(l1), vlen(l2), vlen(l3)) + 1
        pw_v = max(vlen(p1), vlen(p2), vlen(p3))
        sep = lw + 2 + pw_v + 3 + vlen('결과')

        def row(label, price, icon):
            return vpad_l(label, lw) + '  ' + vpad_r(price, pw_v) + '   ' + icon

        block = '\n'.join([
            f'현재가  {cur:,}원  ({sd(t_d)})',
            f'지정일  {sd(d_date)}  →  해제 판단일  {sd(release)}',
            f'경과    {elapsed} / 10 거래일',
            '',
            vpad_l('조건', lw) + '  ' + vpad_r('기준가', pw_v) + '   결과',
            '─' * sep,
            row(l1, p1, ci(c1)),
            row(l2, p2, ci(c2)),
            row(l3, p3, ci(c3)),
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
    """Build a caution/escalation Telegram message from lib.usecases.caution_search_payload."""
    status = d.get('status')
    query = d.get('query', '')
    name = d.get('stockName', query)

    if status == 'not_caution':
        return f'"{query}" — 현재 투자경고가 아님.'

    reason = d.get('designationReason', '')
    d_str = d.get('latestDesignationDate', '')
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
            nd = a.get('noticeDate', '')
            fd = a.get('firstJudgmentDate', '')
            ld = a.get('lastJudgmentDate', '')
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
    t_date = date.fromisoformat(e['tDate'])
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


# Backward-compatible name while api/telegram.py is being reduced.
build_message = build_warning_message
