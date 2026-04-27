"""Market-alert forecast policy.

This module translates the public KRX warning-designation checks into a
conservative ranking signal for the forecast surface. It does not try to model
KRX-only surveillance inputs such as account concentration; callers must keep
those cases in a separate "needs review" bucket.
"""

FORECAST_NEAR_SCORE = 75

FORECAST_POLICY = {
    'name': 'krx-warning-designation-public-price-v1',
    'nearScore': FORECAST_NEAR_SCORE,
    'priceGapPctForFullCredit': 0.12,
    'max15GapPctForFullCredit': 0.08,
    'returnGapPctForFullCredit': 0.12,
    'source': 'KRX KIND 투자경고종목 지정예고 공시',
}


def _condition_met(set_data: dict, key: str) -> bool:
    for condition in set_data.get('conditions', []) or []:
        if condition.get('key') == key:
            return bool(condition.get('met'))
    return False


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _gap_score(gap: float, full_credit_gap: float, weight: int) -> float:
    if gap <= 0:
        return float(weight)
    if full_credit_gap <= 0:
        return 0.0
    return max(0.0, weight * (1 - min(gap / full_credit_gap, 1)))


def _format_pct(value: float) -> str:
    return f'{value * 100:.1f}%'


def _format_pp(value: float) -> str:
    return f'{value * 100:.1f}%p'


def _set_signal(escalation: dict, set_data: dict) -> dict:
    t_close = float(escalation.get('tClose') or 0)
    max15 = float(escalation.get('max15') or 0)
    threshold = float(set_data.get('thresholdPrice') or 0)
    stock_return = float(set_data.get('stockReturn') or 0)
    index_return = float(set_data.get('indexReturn') or 0)
    index_multiplier = float(set_data.get('indexMultiplier') or 0)
    required_return = index_return * index_multiplier

    price_gap = max(0.0, threshold - t_close)
    price_gap_pct = _safe_ratio(price_gap, threshold)
    max15_gap = max(0.0, max15 - t_close)
    max15_gap_pct = _safe_ratio(max15_gap, max15)
    return_gap_pct = max(0.0, required_return - stock_return)

    price_met = _condition_met(set_data, 'priceRise')
    max15_met = _condition_met(set_data, 'max15')
    index_met = _condition_met(set_data, 'vsIndex')
    condition_count = sum(1 for met in (price_met, max15_met, index_met) if met)
    total_conditions = 3

    if set_data.get('allMet'):
        score = 100
    else:
        score = round(
            (35 if price_met else _gap_score(price_gap_pct, 0.12, 35))
            + (25 if max15_met else _gap_score(max15_gap_pct, 0.08, 25))
            + (25 if index_met else _gap_score(return_gap_pct, 0.12, 25))
        )

    missing = []
    if not price_met:
        missing.append('priceRise')
    if not max15_met:
        missing.append('max15')
    if not index_met:
        missing.append('vsIndex')

    if set_data.get('allMet'):
        remaining = '공개 가격조건 충족'
    elif price_gap > 0:
        remaining = f'종가 +{_format_pct(price_gap_pct)} 필요 ({round(price_gap):,}원)'
    elif max15_gap > 0:
        remaining = f'15일 최고가까지 +{_format_pct(max15_gap_pct)} 필요'
    elif return_gap_pct > 0:
        remaining = f'지수 대비 상승률 +{_format_pp(return_gap_pct)} 필요'
    else:
        remaining = '공개 조건 재확인 필요'

    return {
        'label': set_data.get('label', ''),
        'window': set_data.get('window', ''),
        'score': int(score),
        'conditionCount': condition_count,
        'totalConditions': total_conditions,
        'missing': missing,
        'remainingText': remaining,
        'priceGap': round(price_gap),
        'priceGapPct': round(price_gap_pct, 4),
        'max15GapPct': round(max15_gap_pct, 4),
        'returnGapPct': round(return_gap_pct, 4),
        'stockReturn': round(stock_return, 4),
        'requiredIndexReturn': round(required_return, 4),
        'allMet': bool(set_data.get('allMet')),
    }


def build_forecast_signal(escalation: dict) -> dict:
    """Return a display/ranking signal from calc_official_escalation output."""
    sets = [s for s in escalation.get('sets', []) if isinstance(s, dict)]
    if not sets:
        return {
            'riskLevel': 'watch',
            'riskLabel': '관찰',
            'riskScore': 0,
            'level': 'watch',
            'levelLabel': '주의보',
            'primarySignal': '공개 가격조건 확인 불가',
            'remainingText': '조건 세트 없음',
            'bestSet': {},
            'sets': [],
        }

    set_signals = [_set_signal(escalation, set_data) for set_data in sets]
    best = max(set_signals, key=lambda item: (item['allMet'], item['score']))

    if best['allMet']:
        risk_level = 'triggered'
        risk_label = '공식 조건 충족'
        level = 'alert'
        level_label = '경보'
        primary = f'{best["label"] or "공개 가격조건"} 충족'
    elif best['score'] >= FORECAST_NEAR_SCORE and best['conditionCount'] >= 2:
        risk_level = 'near'
        risk_label = '근접'
        level = 'near'
        level_label = '근접'
        primary = (
            f'{best["label"] or "공개 가격조건"} 근접 · '
            f'{best["conditionCount"]}/{best["totalConditions"]}개 충족'
        )
    else:
        risk_level = 'watch'
        risk_label = '관찰'
        level = 'watch'
        level_label = '주의보'
        primary = (
            f'{best["label"] or "공개 가격조건"} 관찰 · '
            f'{best["conditionCount"]}/{best["totalConditions"]}개 충족'
        )

    return {
        'riskLevel': risk_level,
        'riskLabel': risk_label,
        'riskScore': best['score'],
        'level': level,
        'levelLabel': level_label,
        'primarySignal': primary,
        'remainingText': best['remainingText'],
        'bestSet': best,
        'sets': set_signals,
    }
