"""Telegram command use cases."""
from concurrent.futures import ThreadPoolExecutor

from lib.http_utils import log_event, log_exception, safe_exception_text
from lib.krx import search_kind
from lib.naver import (
    calc_thresholds,
    fetch_prices,
    stock_code as naver_stock_code,
)
from lib.telegram_messages import build_caution_message, build_warning_message
from lib.telegram_transport import send_markdown as tg_send, send_plain as tg_send_plain
from lib.usecases import caution_search_payload
from lib.validation import normalize_query


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
        tg_send_plain(chat_id, f'❌ KRX 조회 오류: {safe_exception_text(e)}')
        return

    if not results:
        tg_send_plain(chat_id, f'"{query}" — 현재 투자경고가 아님.')
        return

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
            tg_send(chat_id, build_warning_message(warn['stockName'], warn, thresholds))
        except Exception:
            try:
                tg_send_plain(chat_id, build_warning_message(warn['stockName'], warn, thresholds))
            except Exception as e:
                tg_send_plain(chat_id, f'⚠️ 결과 전송 오류: {safe_exception_text(e)}')

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
        result = caution_search_payload(query)
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
