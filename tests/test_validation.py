import unittest

from lib.validation import (
    normalize_query,
    parse_int_range,
    validate_corp_code,
    validate_dart_pblntf_ty,
    validate_date_range,
    validate_stock_code,
    validate_yyyymmdd,
)


class ValidationTests(unittest.TestCase):
    def test_normalize_query_strips_and_collapses_whitespace(self):
        self.assertEqual(normalize_query('  삼성전자    우  '), '삼성전자 우')

    def test_normalize_query_rejects_empty_control_and_oversized_values(self):
        with self.assertRaises(ValueError):
            normalize_query('   ')
        with self.assertRaises(ValueError):
            normalize_query('삼성\x00전자')
        with self.assertRaises(ValueError):
            normalize_query('가' * 81, max_chars=80, max_bytes=400)

    def test_validate_stock_and_corp_codes(self):
        self.assertEqual(validate_stock_code(' 005930 '), '005930')
        self.assertEqual(validate_corp_code(' 00126380 '), '00126380')
        self.assertEqual(validate_corp_code('', required=False), '')

        for value in ('5930', '00593A', '0059300'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_stock_code(value)

        for value in ('126380', '0012638A', '001263800'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_corp_code(value)

    def test_validate_date_range_rejects_bad_dates_reverse_and_excessive_ranges(self):
        self.assertEqual(validate_yyyymmdd('20260424', 'bgn_de'), '20260424')

        for value in ('20260230', '2026-04-24', '2026042A'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_yyyymmdd(value, 'bgn_de')

        with self.assertRaises(ValueError):
            validate_date_range('20260425', '20260424')
        with self.assertRaises(ValueError):
            validate_date_range('20200101', '20260424', max_days=100)

    def test_parse_int_range_and_dart_notice_type(self):
        self.assertEqual(parse_int_range('', 'page_no', 1, 1, 1000), 1)
        self.assertEqual(parse_int_range('20', 'page_count', 10, 1, 100), 20)
        self.assertEqual(validate_dart_pblntf_ty('a'), 'A')
        self.assertEqual(validate_dart_pblntf_ty(''), '')

        with self.assertRaises(ValueError):
            parse_int_range('x', 'page_no', 1, 1, 1000)
        with self.assertRaises(ValueError):
            parse_int_range('0', 'page_no', 1, 1, 1000)
        with self.assertRaises(ValueError):
            validate_dart_pblntf_ty('Z')


if __name__ == '__main__':
    unittest.main()
