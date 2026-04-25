"""KRX 투자경고 해제 조건 정책 — 단일 소스.

세 조건의 lookback·multiplier·고가 윈도우를 한 곳에서 정의한다.
naver.calc_thresholds, telegram_messages, app.js renderConditions 모두
이 상수/payload만 참조해야 한다. 정책 변경 시 본 파일만 수정한다.
"""

T5_LOOKBACK = 5
T5_MULTIPLIER = 1.45
T15_LOOKBACK = 15
T15_MULTIPLIER = 1.75
MAX_WINDOW_DAYS = 15

# T 종가까지 포함해 비교할 수 있어야 하므로 윈도우 + 1일
MIN_PRICE_DATA_DAYS = MAX_WINDOW_DAYS + 1

# /api/stock-price 응답의 thresholds.policy 필드로 직렬화되는 메타.
# 프론트(app.js)와 텔레그램 메시지가 라벨 렌더링에 사용한다.
POLICY = {
    't5Lookback': T5_LOOKBACK,
    't5Multiplier': T5_MULTIPLIER,
    't15Lookback': T15_LOOKBACK,
    't15Multiplier': T15_MULTIPLIER,
    'maxWindowDays': MAX_WINDOW_DAYS,
}
