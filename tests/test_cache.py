import unittest

from lib.cache import TTLCache


class TTLCacheTests(unittest.TestCase):
    def test_returns_stale_value_on_error_when_allowed(self):
        cache = TTLCache(ttl=0, name='test-cache')
        cache.set('k', {'value': 1})

        def fail():
            raise RuntimeError('upstream down')

        self.assertEqual(
            cache.get_or_set(
                'k',
                fail,
                allow_stale_on_error=True,
                max_stale=60,
            ),
            {'value': 1},
        )
        self.assertEqual(cache.stats()['stale_hits'], 1)

    def test_miss_raises_when_no_stale_value(self):
        cache = TTLCache(ttl=0, name='test-cache')

        def fail():
            raise RuntimeError('upstream down')

        with self.assertRaises(RuntimeError):
            cache.get_or_set(
                'missing',
                fail,
                allow_stale_on_error=True,
                max_stale=60,
            )


if __name__ == '__main__':
    unittest.main()
