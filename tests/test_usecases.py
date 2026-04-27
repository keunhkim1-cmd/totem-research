import unittest
from datetime import date, datetime
from unittest.mock import patch

from lib.errors import DartError
from lib import usecases


class UsecaseTests(unittest.TestCase):
    def test_warning_search_normalizes_query_and_returns_contract(self):
        with patch.object(usecases, 'search_kind', return_value=[{'stockName': '삼성전자'}]) as search:
            payload = usecases.warning_search_payload(' 삼성전자 ')

        search.assert_called_once_with('삼성전자')
        self.assertEqual(payload, {
            'results': [{'stockName': '삼성전자'}],
            'query': '삼성전자',
        })

    def test_stock_price_returns_latest_sixteen_prices(self):
        prices = [
            {'date': f'2026-01-{day:02d}', 'close': 100 + day}
            for day in range(1, 21)
        ]
        with patch.object(usecases, 'fetch_prices', return_value=prices) as fetch:
            payload = usecases.stock_price_payload('005930')

        fetch.assert_called_once_with('005930', count=20)
        self.assertEqual(payload['prices'], prices[-16:])
        self.assertNotIn('warnings', payload)
        self.assertTrue(payload['thresholds'])

    def test_stock_price_surfaces_insufficient_data_warning(self):
        prices = [{'date': '2026-01-01', 'close': 100}]
        with patch.object(usecases, 'fetch_prices', return_value=prices):
            payload = usecases.stock_price_payload('005930')

        self.assertEqual(payload['prices'], prices[-16:])
        self.assertEqual(payload['warnings'][0]['code'], 'INSUFFICIENT_PRICE_DATA')

    def test_dart_search_validates_and_passes_typed_params(self):
        with patch.object(usecases, 'search_disclosure', return_value={'status': '013'}) as search:
            payload = usecases.dart_search_payload(
                corp_code='00126380',
                bgn_de='20250101',
                end_de='20250131',
                page_no='2',
                page_count='10',
                pblntf_ty='A',
            )

        self.assertEqual(payload, {'status': '013'})
        search.assert_called_once_with(
            corp_code='00126380',
            bgn_de='20250101',
            end_de='20250131',
            page_no=2,
            page_count=10,
            pblntf_ty='A',
        )

    def test_dart_search_raises_typed_error_for_provider_status(self):
        with patch.object(
            usecases,
            'search_disclosure',
            return_value={'status': '999', 'message': 'bad request'},
        ):
            with self.assertRaises(DartError) as raised:
                usecases.dart_search_payload(corp_code='00126380')

        self.assertEqual(raised.exception.code, 'DART_API_ERROR')
        self.assertEqual(raised.exception.details['dartStatus'], '999')


class CautionSearchPayloadTests(unittest.TestCase):
    def test_blank_query_returns_not_caution_without_calling_krx(self):
        with patch.object(usecases, 'search_kind_caution') as krx:
            payload = usecases.caution_search_payload('   ')
        self.assertEqual(payload['status'], 'not_caution')
        self.assertEqual(payload['query'], '')
        self.assertIn('todayKst', payload)
        krx.assert_not_called()

    def test_no_krx_results_returns_not_caution(self):
        with patch.object(usecases, 'search_kind_caution', return_value=[]):
            payload = usecases.caution_search_payload('알 수 없는 종목')
        self.assertEqual(payload['status'], 'not_caution')
        self.assertEqual(payload['query'], '알 수 없는 종목')

    def test_today_designation_without_active_notice_is_non_price_reason(self):
        today = datetime.now(usecases.KST).date().isoformat()
        warn = {
            'stockName': '테스트',
            'latestDesignationDate': today,
            'latestDesignationReason': '소수계좌 매수관여 과다',
            'recent15dCount': 1,
            'allDates': [today],
            'entries': [{'date': today, 'reason': '소수계좌 매수관여 과다'}],
            'market': 'KOSPI',
        }
        with patch.object(usecases, 'search_kind_caution', return_value=[warn]):
            payload = usecases.caution_search_payload('테스트')
        self.assertEqual(payload['status'], 'non_price_reason')
        self.assertEqual(payload['stockName'], '테스트')

    def test_active_notice_without_stock_code_returns_code_not_found(self):
        today = date.today()
        notice = today.isoformat()
        warn = {
            'stockName': '코드없음',
            'latestDesignationDate': notice,
            'latestDesignationReason': '투자경고 지정예고',
            'recent15dCount': 1,
            'allDates': [notice],
            'entries': [{'date': notice, 'reason': '투자경고 지정예고'}],
            'market': 'KOSPI',
        }
        with (
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'stock_code', return_value=[]),
        ):
            payload = usecases.caution_search_payload('코드없음')
        self.assertEqual(payload['status'], 'code_not_found')
        self.assertIn('activeNotice', payload)

    def test_full_pipeline_returns_ok_with_escalation(self):
        today = date.today()
        notice = today.isoformat()
        warn = {
            'stockName': '풀파이프',
            'latestDesignationDate': notice,
            'latestDesignationReason': '투자경고 지정예고',
            'recent15dCount': 1,
            'allDates': [notice],
            'entries': [{'date': notice, 'reason': '투자경고 지정예고'}],
            'market': 'KOSPI',
        }
        escalation = {
            'tClose': 100,
            'sets': [{'allMet': False}, {'allMet': False}],
            'headline': {'verdict': 'none'},
        }
        with (
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(
                usecases,
                'stock_code',
                return_value=[{'code': '005930', 'name': '풀파이프', 'market': 'KOSPI'}],
            ),
            patch.object(usecases, 'fetch_prices', return_value=[]),
            patch.object(usecases, 'fetch_index_prices', return_value=[]),
            patch.object(usecases, 'calc_official_escalation', return_value=escalation),
        ):
            payload = usecases.caution_search_payload('풀파이프')
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['code'], '005930')
        self.assertEqual(payload['indexSymbol'], 'KOSPI')
        self.assertEqual(payload['escalation'], escalation)

    def test_market_to_index_symbol_handles_known_markets(self):
        self.assertEqual(usecases._market_to_index_symbol('KOSDAQ'), 'KOSDAQ')
        self.assertEqual(usecases._market_to_index_symbol('코스닥'), 'KOSDAQ')
        self.assertEqual(usecases._market_to_index_symbol('KOSPI'), 'KOSPI')
        self.assertEqual(usecases._market_to_index_symbol('유가증권시장'), 'KOSPI')
        self.assertEqual(usecases._market_to_index_symbol(''), '')
        self.assertEqual(usecases._market_to_index_symbol('UNKNOWN'), '')

    def test_active_warning_notice_uses_notice_date_as_judgment_day_one(self):
        notice = usecases._active_warning_notice(
            [{'date': '2026-04-24', 'reason': '투자경고 지정예고'}],
            date(2026, 4, 24),
        )

        self.assertEqual(notice['firstJudgmentDate'], '2026-04-24')
        self.assertEqual(notice['lastJudgmentDate'], '2026-05-11')
        self.assertEqual(notice['judgmentDayIndex'], 1)
        self.assertEqual(notice['judgmentWindowRule'], '지정예고일 포함 10거래일')


class MarketAlertForecastPayloadTests(unittest.TestCase):
    def _warn(self, name: str, notice: str, reason: str = '투자경고 지정예고'):
        return {
            'stockName': name,
            'latestDesignationDate': notice,
            'latestDesignationReason': reason,
            'recent15dCount': 1,
            'allDates': [notice],
            'entries': [{'date': notice, 'reason': reason}],
            'market': 'KOSPI',
        }

    def test_forecast_filters_active_notices_and_excludes_current_warning(self):
        today = date(2026, 4, 24)
        notice = '2026-04-23'

        def codes(name):
            return [{'code': '000001' if name == '경보종목' else '000002', 'name': name, 'market': 'KOSPI'}]

        def prices(code, count=30):
            close = 1 if code == '000001' else 2
            return [{'date': '2026-04-24', 'close': close} for _ in range(16)]

        def escalation(stock_prices, index_prices):
            if stock_prices[-1]['close'] == 1:
                return {
                    'headline': {'verdict': 'strong', 'matchedSet': 0},
                    'sets': [{'label': '단기급등', 'allMet': True}],
                }
            return {
                'headline': {'verdict': 'none', 'matchedSet': None},
                'sets': [{'label': '단기급등', 'allMet': False}],
            }

        rows = [
            self._warn('경보종목', notice),
            self._warn('주의종목', notice),
            self._warn('현재경고', notice),
        ]
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[{
                'stockName': '현재경고',
                'level': '투자경고',
                'designationDate': notice,
            }]),
            patch.object(usecases, 'search_kind_caution', return_value=rows),
            patch.object(usecases, 'stock_code', side_effect=codes),
            patch.object(usecases, 'fetch_prices', side_effect=prices),
            patch.object(usecases, 'fetch_index_prices', return_value=[{'date': '2026-04-24', 'close': 1.0} for _ in range(16)]),
            patch.object(usecases, 'calc_official_escalation', side_effect=escalation),
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 2)
        self.assertEqual(payload['summary']['alert'], 1)
        self.assertEqual(payload['summary']['watch'], 1)
        self.assertEqual(payload['summary']['excludedCurrentWarning'], 1)
        self.assertEqual(payload['items'][0]['stockName'], '경보종목')
        self.assertEqual(payload['items'][0]['levelLabel'], '경보')

    def test_forecast_keeps_released_warning_history_as_candidate(self):
        today = date(2026, 4, 24)
        warn = self._warn('재예고종목', '2026-04-23')
        released_prices = [
            {'date': f'2026-04-{day:02d}', 'close': 100}
            for day in range(1, 21)
        ]

        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[{
                'stockName': '재예고종목',
                'level': '투자경고',
                'designationDate': '2026-03-02',
            }]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'stock_code', return_value=[{
                'code': '000004',
                'name': '재예고종목',
                'market': 'KOSPI',
            }]),
            patch.object(usecases, 'fetch_prices', return_value=released_prices),
            patch.object(usecases, 'fetch_index_prices', return_value=[
                {'date': '2026-04-20', 'close': 1.0}
                for _ in range(16)
            ]),
            patch.object(usecases, 'calc_official_escalation', return_value={
                'headline': {'verdict': 'none', 'matchedSet': None},
                'sets': [{'label': '단기급등', 'allMet': False}],
            }),
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['summary']['excludedCurrentWarning'], 0)
        self.assertEqual(payload['summary']['total'], 1)
        self.assertEqual(payload['items'][0]['stockName'], '재예고종목')

    def test_forecast_caution_fetch_failure_surfaces_error(self):
        today = date(2026, 4, 24)
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind_caution', side_effect=RuntimeError('krx down')),
            patch.object(usecases, 'search_kind') as search_kind,
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 0)
        self.assertEqual(payload['items'], [])
        self.assertEqual(payload['errors'][0]['source'], 'krx-caution')
        self.assertIn('krx down', payload['errors'][0]['message'])
        search_kind.assert_not_called()

    def test_forecast_warning_fetch_failure_surfaces_error(self):
        today = date(2026, 4, 24)
        warn = self._warn('조회오류후보', '2026-04-23')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'search_kind', side_effect=RuntimeError('warning down')),
            patch.object(usecases, 'stock_code', return_value=[{
                'code': '000005',
                'name': '조회오류후보',
                'market': 'KOSPI',
            }]),
            patch.object(usecases, 'fetch_prices', return_value=[
                {'date': f'2026-04-{day:02d}', 'close': 100}
                for day in range(1, 21)
            ]),
            patch.object(usecases, 'fetch_index_prices', return_value=[
                {'date': '2026-04-20', 'close': 1.0}
                for _ in range(16)
            ]),
            patch.object(usecases, 'calc_official_escalation', return_value={
                'headline': {'verdict': 'none', 'matchedSet': None},
                'sets': [{'label': '단기급등', 'allMet': False}],
            }),
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 1)
        self.assertEqual(payload['errors'][0]['source'], 'krx-warning')
        self.assertIn('warning down', payload['errors'][0]['message'])

    def test_forecast_marks_internal_review_reason_without_price_calls(self):
        today = date(2026, 4, 24)
        warn = self._warn('불건전종목', '2026-04-23', '투자경고 지정예고 · 단기상승·불건전요건')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'stock_code') as stock_code,
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['summary']['needsReview'], 1)
        self.assertEqual(payload['items'][0]['calcStatus'], 'needs_review')
        stock_code.assert_not_called()

    def test_forecast_price_failure_is_review_needs_review(self):
        today = date(2026, 4, 24)
        warn = self._warn('가격오류', '2026-04-23')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'stock_code', return_value=[{'code': '000003', 'name': '가격오류', 'market': 'KOSPI'}]),
            patch.object(usecases, 'fetch_prices', side_effect=RuntimeError('timeout')),
            patch.object(usecases, 'fetch_index_prices', return_value=[{'date': '2026-04-24', 'close': 1.0} for _ in range(16)]),
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['summary']['needsReview'], 1)
        self.assertEqual(payload['items'][0]['level'], 'review')
        self.assertEqual(payload['items'][0]['calcStatus'], 'needs_review')
        self.assertIn('timeout', payload['items'][0]['calcDetail'])

    def test_forecast_ignores_expired_notice(self):
        today = date(2026, 4, 24)
        warn = self._warn('만료종목', '2026-03-01')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 0)


if __name__ == '__main__':
    unittest.main()
