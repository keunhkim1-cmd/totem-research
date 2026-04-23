import unittest
from unittest.mock import patch

from lib.retry import NonRetryableError, RetryableError, retry


class RetryTests(unittest.TestCase):
    def test_retries_retryable_errors(self):
        calls = {'count': 0}

        def flaky():
            calls['count'] += 1
            if calls['count'] == 1:
                raise RetryableError('temporary')
            return 'ok'

        with patch('lib.retry.time.sleep') as sleep:
            self.assertEqual(retry(flaky, retries=1, jitter=0), 'ok')
            sleep.assert_called_once()
        self.assertEqual(calls['count'], 2)

    def test_does_not_retry_non_retryable_errors(self):
        calls = {'count': 0}

        def bad():
            calls['count'] += 1
            raise NonRetryableError('bad input')

        with patch('lib.retry.time.sleep') as sleep:
            with self.assertRaises(NonRetryableError):
                retry(bad, retries=3)
            sleep.assert_not_called()
        self.assertEqual(calls['count'], 1)


if __name__ == '__main__':
    unittest.main()
