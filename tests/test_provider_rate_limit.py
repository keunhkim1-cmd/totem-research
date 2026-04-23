import os
import unittest
from unittest.mock import patch

from lib.provider_rate_limit import ProviderRateLimitError, _local_counts, throttle


class ProviderRateLimitTests(unittest.TestCase):
    def setUp(self):
        self._old_env = dict(os.environ)
        _local_counts.clear()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_env)
        _local_counts.clear()

    def test_local_limiter_raises_when_budget_exceeded(self):
        os.environ['EXTERNAL_RATE_LIMITS_ENABLED'] = 'true'
        os.environ['EXTERNAL_RATE_NAVER_PER_MINUTE'] = '1'
        os.environ['EXTERNAL_RATE_LIMIT_MAX_WAIT'] = '0'

        self.assertEqual(throttle('naver'), 0.0)
        with patch('lib.provider_rate_limit.random.uniform', return_value=0):
            with self.assertRaises(ProviderRateLimitError):
                throttle('naver')

    def test_disabled_limiter_allows_calls(self):
        os.environ['EXTERNAL_RATE_LIMITS_ENABLED'] = 'false'
        os.environ['EXTERNAL_RATE_NAVER_PER_MINUTE'] = '1'

        self.assertEqual(throttle('naver'), 0.0)
        self.assertEqual(throttle('naver'), 0.0)


if __name__ == '__main__':
    unittest.main()
