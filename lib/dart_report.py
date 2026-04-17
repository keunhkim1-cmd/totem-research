"""DART 사업보고서 본문 추출 + Gemini 요약"""
import urllib.request, urllib.parse, io, zipfile, json, os, re, time
from xml.etree import ElementTree as ET
from datetime import date, timedelta

from lib.retry import retry
from lib.cache import TTLCache
from lib.dart_corp import find_corp_by_stock_code
from lib.gemini import generate as gemini_generate

DART_BASE = 'https://opendart.fss.or.kr/api'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

# 사업보고서는 분기당 1회 갱신 — 24시간 캐시
_summary_cache = TTLCache(ttl=24 * 3600)
_doc_cache = TTLCache(ttl=24 * 3600)


def _api_key() -> str:
    key = os.environ.get('DART_API_KEY', '')
    if not key:
        raise ValueError('DART_API_KEY 환경변수가 설정되지 않았습니다.')
    return key


def _find_latest_business_report(corp_code: str) -> dict | None:
    """corp_code → 가장 최근 사업보고서(A001) 공시 1건 또는 None.
    사업보고서는 연 1회 발간되므로 최근 18개월 검색."""
    today = date.today()
    bgn = (today - timedelta(days=540)).strftime('%Y%m%d')
    end = today.strftime('%Y%m%d')

    params = urllib.parse.urlencode({
        'crtfc_key': _api_key(),
        'corp_code': corp_code,
        'bgn_de': bgn,
        'end_de': end,
        'pblntf_detail_ty': 'A001',
        'page_count': '10',
        'sort': 'date',
        'sort_mth': 'desc',
    })
    url = f'{DART_BASE}/list.json?{params}'

    def _call():
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode('utf-8'))

    data = retry(_call)
    items = data.get('list') or []
    if not items:
        return None
    return items[0]


def _fetch_document_text(rcept_no: str) -> str:
    """공시서류 원문 zip → 가장 큰 XML 파일만 텍스트 디코딩 (본문은 보통 메인 파일 1개에 집중)."""
    cached = _doc_cache.get(rcept_no)
    if cached is not None:
        return cached

    url = f'{DART_BASE}/document.xml?crtfc_key={_api_key()}&rcept_no={rcept_no}'

    def _call():
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    raw = retry(_call)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        xml_infos = [info for info in zf.infolist()
                     if info.filename.lower().endswith('.xml')]
        if not xml_infos:
            return ''
        # 파일 크기 내림차순 — 가장 큰 XML(본문)만 파싱
        xml_infos.sort(key=lambda i: i.file_size, reverse=True)
        main_info = xml_infos[0]
        with zf.open(main_info) as f:
            data = f.read()

    text = ''
    for enc in ('utf-8', 'euc-kr', 'cp949'):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    _doc_cache.set(rcept_no, text)
    return text


def _strip_tags(s: str) -> str:
    """간이 XML/HTML 태그 제거 + 공백 정리."""
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def _extract_business_overview(full_text: str, max_chars: int = 4000) -> str:
    """'1. 사업의 개요' 섹션만 추출 (다음 하위 항목 '2. 주요 제품 및 서비스' 직전까지).
    DART 원문 XML 구조: <TITLE>1. 사업의 개요</TITLE> ... <TITLE>2. 주요 제품 및 서비스</TITLE>."""
    start_patterns = [
        r'1\.\s*사업의\s*개요',
        r'가\.\s*사업의\s*개요',
    ]
    # 다음 하위 항목들 — 여러 표기 변형 허용
    end_patterns = [
        r'2\.\s*주요\s*제품',
        r'나\.\s*주요\s*제품',
        r'2\.\s*주요\s*서비스',
    ]

    start_m = None
    for p in start_patterns:
        m = re.search(p, full_text)
        if m:
            start_m = m
            break
    if not start_m:
        return ''

    rest = full_text[start_m.end():]
    end_pos = len(rest)
    for p in end_patterns:
        m = re.search(p, rest)
        if m and m.start() < end_pos:
            end_pos = m.start()

    section = full_text[start_m.start():start_m.end() + end_pos]
    cleaned = _strip_tags(section)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + ' …(이하 생략)'
    return cleaned


def _extract_section(full_text: str, header_patterns: list, max_chars: int = 8000) -> str:
    """본문에서 헤더 패턴부터 다음 대제목 전까지 추출.
    DART 사업보고서는 'I. 회사의 개요', 'II. 사업의 내용' 등 로마숫자 대제목 구조."""
    # 다음 대제목: 로마숫자 또는 한글 대문항
    next_header = r'(?:[IVX]+\.\s*[가-힣A-Za-z]|[가-힣]\.\s)'

    for pattern in header_patterns:
        # 헤더 매칭 — XML 태그 사이에 있을 수 있음
        m = re.search(pattern, full_text)
        if not m:
            continue
        start = m.start()
        # 헤더 다음 위치부터 다음 대제목 검색
        rest = full_text[m.end():]
        next_m = re.search(next_header, rest)
        end = m.end() + (next_m.start() if next_m else len(rest))
        section = full_text[start:end]
        cleaned = _strip_tags(section)
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars] + ' …(이하 생략)'
        return cleaned
    return ''


def summarize_business_report(stock_code: str, stock_name: str) -> dict:
    """종목코드 → 사업보고서 요약 결과.
    반환: {'corp_name', 'rcept_no', 'rcept_dt', 'report_nm', 'summary'} or {'error': ...}"""
    cache_key = f'summary:{stock_code}'
    cached = _summary_cache.get(cache_key)
    if cached is not None:
        print(f'[info] 캐시 히트: {stock_code}')
        return cached

    t0 = time.time()
    corp = find_corp_by_stock_code(stock_code)
    print(f'[info] corp 매핑 {time.time()-t0:.1f}s: {corp}')
    if not corp:
        return {'error': f'DART에 등록된 기업 정보 없음 (종목코드: {stock_code})'}

    t0 = time.time()
    report = _find_latest_business_report(corp['corp_code'])
    print(f'[info] 사업보고서 조회 {time.time()-t0:.1f}s: {report.get("rcept_no") if report else None}')
    if not report:
        return {'error': '최근 사업보고서를 찾을 수 없습니다.'}

    rcept_no = report['rcept_no']
    t0 = time.time()
    full_text = _fetch_document_text(rcept_no)
    print(f'[info] 본문 다운로드 {time.time()-t0:.1f}s: {len(full_text):,}자')
    if not full_text:
        return {'error': '사업보고서 본문을 가져올 수 없습니다.'}

    # '사업의 개요'만 추출 — 사업보고서 '사업의 내용' 하위 1번 항목.
    # 다음 하위 항목 '2. 주요 제품 및 서비스' 전까지가 범위.
    t0 = time.time()
    biz_overview = _extract_business_overview(full_text, max_chars=4000)
    print(f'[info] 개요 추출 {time.time()-t0:.1f}s: {len(biz_overview):,}자')

    if not biz_overview:
        return {'error': '사업보고서에서 "사업의 개요" 섹션을 추출할 수 없습니다.'}

    prompt = f"""다음은 {stock_name}({corp['corp_name']})의 가장 최근 사업보고서 '사업의 개요' 항목입니다.
핵심 내용을 한국어로 요약해주세요.

[요약 규칙]
- '-' 부호로 시작하는 불릿 포인트만 사용
- 정확히 10줄 이내
- 각 줄은 한 문장으로 간결하게
- 주요 사업, 제품/서비스, 시장 지위, 경쟁력 순으로 자연스럽게 배치
- 본문에 나온 숫자·비율은 가능한 한 그대로 인용

[사업의 개요]
{biz_overview}

위 내용을 10줄 이내 '-' 불릿으로 요약:"""

    try:
        t0 = time.time()
        summary = gemini_generate(prompt, max_output_tokens=512)
        print(f'[info] Gemini 요약 {time.time()-t0:.1f}s: {len(summary)}자')
    except Exception as e:
        print(f'[info] Gemini 요약 실패: {e}')
        return {'error': f'Gemini 요약 실패: {e}'}

    result = {
        'corp_name': corp['corp_name'],
        'rcept_no': rcept_no,
        'rcept_dt': report.get('rcept_dt', ''),
        'report_nm': report.get('report_nm', ''),
        'summary': summary,
    }
    _summary_cache.set(cache_key, result)
    return result
