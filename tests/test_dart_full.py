import unittest
from unittest.mock import patch

import lib.dart_full as dart_full
from lib.cache import TTLCache
from lib.retry import RetryableError


class DartFullCacheTests(unittest.TestCase):
    def setUp(self):
        self.original_cache = dart_full._cache
        dart_full._cache = TTLCache(ttl=60, name='test-dart-full')

    def tearDown(self):
        dart_full._cache = self.original_cache

    def test_cacheable_status_is_cached(self):
        response = {'status': '000', 'list': [{'account_id': 'ifrs-full_Revenue'}]}
        with patch.object(dart_full, 'fetch_json', return_value=response) as fetch_json:
            self.assertEqual(dart_full.fetch_all('00126380', '2024', '11011'), response)
            self.assertEqual(dart_full.fetch_all('00126380', '2024', '11011'), response)
        fetch_json.assert_called_once()

    def test_transient_status_is_not_cached(self):
        transient = {'status': '020', 'message': 'rate limited'}
        with patch.object(dart_full, 'fetch_json', return_value=transient):
            with self.assertRaises(RetryableError):
                dart_full.fetch_all('00126380', '2024', '11011')

        self.assertEqual(dart_full._cache.stats()['size'], 0)


if __name__ == '__main__':
    unittest.main()
