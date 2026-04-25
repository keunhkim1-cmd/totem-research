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


if __name__ == '__main__':
    unittest.main()
