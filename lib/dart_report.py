"""DART 사업보고서 본문 추출 + Gemini 요약"""
import io, zipfile, re, time
from datetime import date, timedelta

from lib.cache import TTLCache
from lib.dart_base import fetch_bytes, fetch_json
from lib.dart_corp import find_corp_by_stock_code
from lib.gemini import generate as gemini_generate
from lib.http_utils import log_event, safe_exception_text
from lib.timeouts import DART_DOCUMENT_TIMEOUT, DART_LIST_TIMEOUT

# 사업보고서는 분기당 1회 갱신 — 24시간 캐시
_summary_cache = TTLCache(ttl=24 * 3600, name='dart-report-summary', durable=True)
_doc_cache = TTLCache(ttl=24 * 3600, name='dart-report-doc')
SUMMARY_PROMPT_VERSION = 'v1'

def _find_latest_business_report(corp_code: str) -> dict | None:
    """corp_code → 가장 최근 사업보고서(A001) 공시 1건 또는 None.
    사업보고서는 연 1회 발간되므로 최근 18개월 검색."""
    today = date.today()
    bgn = (today - timedelta(days=540)).strftime('%Y%m%d')
    end = today.strftime('%Y%m%d')

    params = {
        'corp_code': corp_code,
        'bgn_de': bgn,
        'end_de': end,
        'pblntf_detail_ty': 'A001',
        'page_count': '10',
        'sort': 'date',
        'sort_mth': 'desc',
    }

    data = fetch_json('list.json', params, timeout=DART_LIST_TIMEOUT, retries=1)
    items = data.get('list') or []
    if not items:
        return None
    return items[0]


def _fetch_document_text(rcept_no: str) -> str:
    """공시서류 원문 zip → 가장 큰 XML 파일만 텍스트 디코딩 (본문은 보통 메인 파일 1개에 집중)."""
    def _fetch():
        raw = fetch_bytes(
            'document.xml',
            {'rcept_no': rcept_no},
            timeout=DART_DOCUMENT_TIMEOUT,
            retries=1,
        )

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
        return text

    return _doc_cache.get_or_set(
        rcept_no,
        _fetch,
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )


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
    latest_cache_key = f'summary-latest:{stock_code}:{SUMMARY_PROMPT_VERSION}'
    cached = _summary_cache.get(latest_cache_key)
    if cached is not None:
        log_event('info', 'dart_report_summary_cache_hit', stock_code=stock_code)
        return cached

    t0 = time.time()
    corp = find_corp_by_stock_code(stock_code)
    log_event('info', 'dart_report_corp_mapped',
              stock_code=stock_code, elapsed=f'{time.time()-t0:.1f}', corp=corp)
    if not corp:
        return {'error': f'DART에 등록된 기업 정보 없음 (종목코드: {stock_code})'}

    t0 = time.time()
    report = _find_latest_business_report(corp['corp_code'])
    log_event('info', 'dart_report_found',
              elapsed=f'{time.time()-t0:.1f}',
              rcept_no=report.get('rcept_no') if report else '')
    if not report:
        return {'error': '최근 사업보고서를 찾을 수 없습니다.'}

    rcept_no = report['rcept_no']
    summary_cache_key = f'summary:{stock_code}:{rcept_no}:{SUMMARY_PROMPT_VERSION}'
    cached = _summary_cache.get(summary_cache_key)
    if cached is not None:
        log_event('info', 'dart_report_summary_cache_hit',
                  stock_code=stock_code, rcept_no=rcept_no)
        _summary_cache.set(latest_cache_key, cached)
        return cached

    t0 = time.time()
    full_text = _fetch_document_text(rcept_no)
    log_event('info', 'dart_report_document_fetched',
              elapsed=f'{time.time()-t0:.1f}', text_chars=len(full_text))
    if not full_text:
        return {'error': '사업보고서 본문을 가져올 수 없습니다.'}

    # 1. 사업의 내용 (II. 사업의 내용 ~ III. 직전)
    # 2. 이사의 경영진단 및 분석의견
    t0 = time.time()
    biz_content = _extract_section(full_text, [
        r'II\.\s*사업의\s*내용',
        r'2\.\s*사업의\s*내용',
    ], max_chars=8000)
    mgmt_analysis = _extract_section(full_text, [
        r'이사의\s*경영진단\s*및\s*분석\s*의견',
        r'경영진단\s*및\s*분석\s*의견',
    ], max_chars=5000)
    log_event('info', 'dart_report_sections_extracted',
              elapsed=f'{time.time()-t0:.1f}',
              business_chars=len(biz_content),
              management_chars=len(mgmt_analysis))

    if not biz_content and not mgmt_analysis:
        return {'error': '사업보고서에서 해당 섹션을 추출할 수 없습니다.'}

    prompt = f"""너는 기업 정보 카드를 작성하는 편집자다. 사업보고서에서 핵심 사실만 뽑아
"- 라벨: 명사구" 형식의 10줄 카드를 만든다. 문장(서술형)이 아니라 사전 항목처럼 써야 한다.

# 절대 규칙
1. 각 줄은 반드시 `- {{라벨}}: {{명사구}}` 형식으로 시작한다.
2. 라벨(콜론 앞)은 2~5자의 한국어 명사 (예: 주요사업, 주요제품, 판매망, 실적동향).
3. 콜론 뒤는 **명사구**로만 작성. 마침표·서술어 금지.
   ❌ "~합니다", "~이다", "~했습니다", "~한다", "~됩니다", "~을 영위", "~을 보유"
   ✅ 명사·명사구로 끝남 (예: "글로벌 선도 지위 확보", "전년 대비 XX% 증가")
4. 회사명(주어)을 문장 앞에 쓰지 않는다.
5. 정확히 10줄, 한 줄에 한 항목.
6. 카테고리 라벨은 서로 겹치지 않게 10개 다른 관점으로.

# 라벨 후보 (본문에 맞게 선택)
사업구조 · 주요사업 · 주요제품 · 주요서비스 · 매출구성 · 주요고객 · 시장지위 · 경쟁력
생산시설 · 원재료 · 판매망 · 해외진출 · 연구개발 · 신규사업 · 사업전략
실적동향 · 재무상태 · 리스크요인 · 향후전망 · 경영진의견

# 올바른 예시 (이 스타일 그대로 따라라)
- 주요사업: 나노 단위 미세물 분석용 주사전자현미경(SEM) 및 주변기기 제조·판매
- 주요제품: SEM, Tabletop SEM, 이온밀러(IP), 이온코터(SPT)
- 신규제품: IP-SEM, 대기압 SEM(A SEM), AI-SEM
- 판매망: 국내 직판·딜러 병행, 해외 41개국 20개 대리점 간접판매
- 시장지위: Tabletop SEM 분야 글로벌 선도
- 경쟁력: 고성능 이온건 기술 내재화, AI-SEM 선도 기술
- 고객구조: 특정 고객·지역 의존도 낮은 다변화 구조
- 실적동향: 전방 반도체 투자 회복에 따른 매출 증가
- 리스크요인: 반도체 설비투자 사이클 의존, 환율 변동
- 경영진의견: Tabletop SEM 주력 포지셔닝 강화 + 응용제품 확장

# 잘못된 예시 (이렇게 쓰면 안 됨)
❌ "- 코셈은 나노 단위 미세물 분석을 위한 주사전자현미경을 제조합니다."  (주어+서술어)
❌ "- SEM과 주변기기를 제조 및 판매하고 있습니다."  (서술어)
❌ "- 핵심 제품으로는 SEM이 있습니다."  (서술어)
❌ "- 주요사업은 SEM 제조·판매입니다."  (서술어, 라벨 누락)

# 섹션별 역할
- '사업의 내용' 섹션에서 → 사업구조·제품·판매망·시장지위·경쟁력 카테고리
- '이사의 경영진단' 섹션에서 → 실적동향·재무상태·리스크요인·향후전망·경영진의견 카테고리

# 데이터 원칙
본문에 명시된 숫자·비율·고유명사(제품명, 지역명, 금액)는 가능한 한 그대로 인용.

=== 사업의 내용 ===
{biz_content if biz_content else '(추출 실패)'}

=== 이사의 경영진단 및 분석의견 ===
{mgmt_analysis if mgmt_analysis else '(추출 실패)'}

=== 작성 지시 ===
위 두 섹션을 읽고 아래 형식으로만 출력하라. 다른 텍스트(인사말, 머리말, 꼬리말, 빈 줄) 금지.
정확히 10줄. 각 줄은 반드시 `- ` 로 시작한 뒤 `라벨: 명사구`.
서술어('합니다', '이다', '있습니다', '영위' 등)와 주어(회사명) 절대 금지.

지금 바로 10줄 카드를 출력:"""

    try:
        t0 = time.time()
        summary = gemini_generate(prompt, max_output_tokens=512)
        log_event('info', 'gemini_summary_completed',
                  elapsed=f'{time.time()-t0:.1f}', chars=len(summary))
    except Exception as e:
        message = safe_exception_text(e)
        log_event('warning', 'gemini_summary_failed', error=message)
        stale, state = _summary_cache.get_with_meta(
            summary_cache_key,
            allow_stale=True,
            max_stale=30 * 24 * 3600,
        )
        if state == 'stale':
            log_event('warning', 'gemini_summary_stale_returned',
                      stock_code=stock_code, rcept_no=rcept_no)
            return stale
        return {'error': f'Gemini 요약 실패: {message}'}

    result = {
        'corp_name': corp['corp_name'],
        'rcept_no': rcept_no,
        'rcept_dt': report.get('rcept_dt', ''),
        'report_nm': report.get('report_nm', ''),
        'summary': summary,
    }
    _summary_cache.set(summary_cache_key, result)
    _summary_cache.set(latest_cache_key, result)
    return result
