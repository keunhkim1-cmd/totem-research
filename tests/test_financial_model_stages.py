"""build_model 분할 단계 함수 단위 테스트."""
import unittest
from unittest.mock import patch

from lib import financial_model


class ResolveSettledYearsTests(unittest.TestCase):
    @staticmethod
    def _full_cache(year: str) -> dict:
        suf = year[2:]
        return {
            ('annual', year): {'revenue': 100.0},
            **{('quarterly', f'{q}{suf}'): {'revenue': 25.0} for q in financial_model.QUARTERS},
        }

    def test_settled_year_with_full_cache_is_restored(self):
        cache = self._full_cache('2022')
        annual, by_year_period, fetch = financial_model._resolve_settled_years(
            ['2022', '2023', '2024'], end_year=2024, cache=cache,
        )
        self.assertIn('2022', annual)
        self.assertEqual(set(by_year_period['2022'].keys()), {'1Q', '2Q', '3Q', '4Q'})
        self.assertEqual(fetch, ['2023', '2024'])

    def test_end_year_is_never_treated_as_settled(self):
        cache = self._full_cache('2024')
        annual, _, fetch = financial_model._resolve_settled_years(
            ['2024'], end_year=2024, cache=cache,
        )
        self.assertEqual(fetch, ['2024'])
        self.assertEqual(annual, {})

    def test_partial_quarterly_cache_triggers_refetch(self):
        cache = {
            ('annual', '2022'): {'revenue': 100.0},
            ('quarterly', '1Q22'): {'revenue': 25.0},
            ('quarterly', '2Q22'): {'revenue': 25.0},
            ('quarterly', '3Q22'): {'revenue': 25.0},
            # 4Q22 누락 → 부분 캐시 → 재패치
        }
        _, _, fetch = financial_model._resolve_settled_years(
            ['2022'], end_year=2024, cache=cache,
        )
        self.assertEqual(fetch, ['2022'])

    def test_empty_cache_marks_all_years_for_fetch(self):
        _, by_year_period, fetch = financial_model._resolve_settled_years(
            ['2022', '2023', '2024'], end_year=2024, cache={},
        )
        self.assertEqual(fetch, ['2022', '2023', '2024'])
        self.assertEqual(by_year_period, {})


class FetchMissingYearsTests(unittest.TestCase):
    def test_empty_fetch_list_skips_dart_calls(self):
        with patch.object(financial_model, '_fetch_period_safe') as fetch:
            annual, periods = financial_model._fetch_missing_years(
                '00126380', 'CFS', year_list=['2024'], years_to_fetch=[],
            )
        self.assertEqual(annual, {})
        self.assertEqual(periods, {})
        fetch.assert_not_called()

    def test_one_year_fetch_emits_four_dart_calls_and_enriches_annual(self):
        is_revenue = {
            'status': '000',
            'list': [{
                'sj_div': 'IS',
                'account_id': 'ifrs-full_Revenue',
                'account_nm': '매출액',
                'thstrm_amount': '1000',
            }],
        }
        with patch.object(
            financial_model, '_fetch_period_safe', return_value=is_revenue,
        ) as fetch:
            annual, periods = financial_model._fetch_missing_years(
                '00126380', 'CFS', year_list=['2024'], years_to_fetch=['2024'],
            )
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual(set(periods['2024'].keys()), {'1Q', '2Q', '3Q', 'FY'})
        self.assertIn('revenue', annual['2024'])

    def test_failure_status_response_yields_empty_period(self):
        with patch.object(
            financial_model, '_fetch_period_safe', return_value={'status': 'ERR'},
        ):
            annual, periods = financial_model._fetch_missing_years(
                '00126380', 'CFS', year_list=['2024'], years_to_fetch=['2024'],
            )
        self.assertEqual(annual, {})
        self.assertEqual(periods['2024'], {'1Q': {}, '2Q': {}, '3Q': {}, 'FY': {}})


class DeriveQuarterlyTests(unittest.TestCase):
    def test_cached_year_is_passed_through_unchanged(self):
        by_year_period = {
            '2022': {q: {'revenue': 25.0, 'revenue_yoy': 0.1} for q in ['1Q', '2Q', '3Q', '4Q']},
        }
        out = financial_model._derive_quarterly(['2022'], years_to_fetch=[], by_year_period=by_year_period)
        self.assertEqual(out['1Q22']['revenue'], 25.0)
        self.assertEqual(out['4Q22']['revenue_yoy'], 0.1)

    def test_fetched_year_is_derived_via_periods_to_quarterly(self):
        by_year_period = {
            '2024': {
                '1Q': {'revenue': 100.0},
                '2Q': {'revenue': 200.0},
                '3Q': {'revenue': 300.0},
                'FY': {'revenue': 1000.0},
            },
        }
        out = financial_model._derive_quarterly(['2024'], years_to_fetch=['2024'], by_year_period=by_year_period)
        self.assertEqual(out['1Q24']['revenue'], 100.0)
        self.assertEqual(out['4Q24']['revenue'], 400.0)


class EnrichYoyTests(unittest.TestCase):
    def test_first_year_is_none_subsequent_uses_prior(self):
        annual = {'2022': {'revenue': 100.0}, '2023': {'revenue': 120.0}}
        quarterly = {f'{q}22': {'revenue': 25.0} for q in ['1Q', '2Q', '3Q', '4Q']}
        quarterly.update({f'{q}23': {'revenue': 30.0} for q in ['1Q', '2Q', '3Q', '4Q']})
        financial_model._enrich_yoy(['2022', '2023'], annual, quarterly)

        self.assertIsNone(annual['2022']['revenue_yoy'])
        self.assertAlmostEqual(annual['2023']['revenue_yoy'], 0.2)
        self.assertIsNone(quarterly['1Q22']['revenue_yoy'])
        self.assertAlmostEqual(quarterly['1Q23']['revenue_yoy'], 0.2)


class CollectSaveRowsTests(unittest.TestCase):
    def test_only_fetched_years_emit_rows_and_empty_quarters_dropped(self):
        annual = {'2024': {'revenue': 100.0}}
        quarterly = {
            '1Q24': {'revenue': 25.0},
            '2Q24': {'revenue': None, 'cfo': None},
            '3Q24': {'revenue': 25.0},
            '4Q24': {'revenue': 25.0},
        }
        rows = financial_model._collect_save_rows(['2024'], annual, quarterly)
        period_keys = sorted(r['period_key'] for r in rows)
        # 2Q24는 모두 None → 제외
        self.assertEqual(period_keys, ['1Q24', '2024', '3Q24', '4Q24'])

    def test_no_fetch_means_no_rows(self):
        rows = financial_model._collect_save_rows([], {'2022': {'revenue': 100}}, {})
        self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
