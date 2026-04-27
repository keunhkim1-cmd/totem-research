from lib.forecast_policy import build_forecast_signal


def test_build_forecast_signal_marks_official_condition_hit_as_alert():
    signal = build_forecast_signal({
        'tClose': 160,
        'max15': 160,
        'sets': [{
            'label': '[1] 단기급등',
            'window': 'T-5',
            'thresholdPrice': 160,
            'stockReturn': 0.62,
            'indexReturn': 0.10,
            'indexMultiplier': 5,
            'conditions': [
                {'key': 'priceRise', 'met': True},
                {'key': 'max15', 'met': True},
                {'key': 'vsIndex', 'met': True},
            ],
            'allMet': True,
        }],
    })

    assert signal['level'] == 'alert'
    assert signal['riskScore'] == 100
    assert signal['primarySignal'] == '[1] 단기급등 충족'


def test_build_forecast_signal_marks_two_conditions_and_small_gap_as_near():
    signal = build_forecast_signal({
        'tClose': 158,
        'max15': 158,
        'sets': [{
            'label': '[1] 단기급등',
            'window': 'T-5',
            'thresholdPrice': 160,
            'stockReturn': 0.58,
            'indexReturn': 0.10,
            'indexMultiplier': 5,
            'conditions': [
                {'key': 'priceRise', 'met': False},
                {'key': 'max15', 'met': True},
                {'key': 'vsIndex', 'met': True},
            ],
            'allMet': False,
        }],
    })

    assert signal['level'] == 'near'
    assert signal['riskLabel'] == '근접'
    assert signal['riskScore'] >= 75
    assert '종가 +' in signal['remainingText']


def test_build_forecast_signal_keeps_distant_candidate_as_watch():
    signal = build_forecast_signal({
        'tClose': 120,
        'max15': 150,
        'sets': [{
            'label': '[1] 단기급등',
            'window': 'T-5',
            'thresholdPrice': 160,
            'stockReturn': 0.20,
            'indexReturn': 0.10,
            'indexMultiplier': 5,
            'conditions': [
                {'key': 'priceRise', 'met': False},
                {'key': 'max15', 'met': False},
                {'key': 'vsIndex', 'met': False},
            ],
            'allMet': False,
        }],
    })

    assert signal['level'] == 'watch'
    assert signal['riskScore'] < 75
