import unittest

from lib import financial_model


class FinancialModelPeriodTests(unittest.TestCase):
    def test_derive_q4_from_annual_subtracts_interim_quarters(self):
        self.assertEqual(
            financial_model.derive_q4_from_annual(100, 200, 300, 1000),
            400,
        )

    def test_derive_q4_from_annual_requires_all_interim_quarters(self):
        self.assertIsNone(financial_model.derive_q4_from_annual(100, None, 300, 1000))
        self.assertIsNone(financial_model.derive_q4_from_annual(100, 200, 300, None))

    def test_periods_to_quarterly_derives_flow_values_and_keeps_bs_fy_snapshot(self):
        quarterly = financial_model._periods_to_quarterly(
            {
                '1Q': {
                    'revenue': 100.0,
                    'cfo': 10.0,
                    'total_assets': 1_000.0,
                },
                '2Q': {
                    'revenue': 200.0,
                    'cfo': 20.0,
                    'total_assets': 1_100.0,
                },
                '3Q': {
                    'revenue': 300.0,
                    'cfo': 30.0,
                    'total_assets': 1_200.0,
                },
                'FY': {
                    'revenue': 1_000.0,
                    'cfo': 100.0,
                    'total_assets': 1_600.0,
                },
            },
        )

        self.assertEqual(quarterly['1Q']['revenue'], 100.0)
        self.assertEqual(quarterly['4Q']['revenue'], 400.0)
        self.assertEqual(quarterly['4Q']['cfo'], 40.0)
        self.assertEqual(quarterly['1Q']['total_assets'], 1_000.0)
        self.assertEqual(quarterly['4Q']['total_assets'], 1_600.0)


if __name__ == '__main__':
    unittest.main()
