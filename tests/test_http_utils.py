import os
import unittest
from unittest.mock import patch

from lib.http_utils import (
    api_error_payload,
    api_success_payload,
    cors_origin,
    redact_known_secrets,
    redact_text,
    redact_url,
    telegram_bot_url,
)


class HttpUtilsTests(unittest.TestCase):
    def test_api_payloads_keep_transitional_contract(self):
        self.assertEqual(api_success_payload({'results': []}), {'results': [], 'ok': True})

        payload = api_error_payload(
            'VALIDATION_ERROR',
            'bad input',
            details={'field': 'code'},
            legacy_key='errorMessage',
            status_value='error',
        )

        self.assertFalse(payload['ok'])
        self.assertEqual(payload['errorInfo']['code'], 'VALIDATION_ERROR')
        self.assertEqual(payload['errorInfo']['details'], {'field': 'code'})
        self.assertEqual(payload['errorMessage'], 'bad input')
        self.assertEqual(payload['status'], 'error')

    def test_cors_origin_allows_exact_configured_origins_only(self):
        with patch.dict(
            os.environ,
            {'ALLOWED_ORIGINS': 'https://example.com, http://localhost:5173'},
            clear=False,
        ):
            self.assertEqual(cors_origin('https://example.com'), 'https://example.com')
            self.assertEqual(cors_origin('https://example.com/'), 'https://example.com')
            self.assertIsNone(cors_origin('https://evil.example.com'))
            self.assertIsNone(cors_origin(None))

    def test_redact_url_scrubs_query_keys_and_telegram_bot_token_path(self):
        dart_url = (
            'https://opendart.fss.or.kr/api/list.json'
            '?crtfc_key=dart-secret&corp_code=00126380&page_no=1'
        )
        self.assertEqual(
            redact_url(dart_url),
            (
                'https://opendart.fss.or.kr/api/list.json'
                '?crtfc_key=REDACTED&corp_code=00126380&page_no=1'
            ),
        )

        gemini_url = (
            'https://generativelanguage.googleapis.com/v1beta/models?x-goog-api-key=gemini-secret'
        )
        redacted = redact_url(gemini_url, secret_query_keys=('x-goog-api-key',))
        self.assertNotIn('gemini-secret', redacted)
        self.assertIn('x-goog-api-key=REDACTED', redacted)

        telegram_url = telegram_bot_url('123456:telegram-secret', 'sendMessage')
        self.assertEqual(
            redact_url(telegram_url),
            'https://api.telegram.org/bot[REDACTED]/sendMessage',
        )

    def test_redact_text_and_known_secrets_scrub_env_values_inside_errors(self):
        with patch.dict(
            os.environ,
            {
                'DART_API_KEY': 'dart-env-secret',
                'TELEGRAM_BOT_TOKEN': '123456:telegram-env-secret',
            },
            clear=False,
        ):
            message = (
                'failed for https://opendart.fss.or.kr/api/list.json?crtfc_key=query-secret '
                'with dart-env-secret and https://api.telegram.org/bot123456:telegram-env-secret/getMe'
            )
            redacted = redact_text(message)

        self.assertNotIn('query-secret', redacted)
        self.assertNotIn('dart-env-secret', redacted)
        self.assertNotIn('telegram-env-secret', redacted)
        self.assertIn('crtfc_key=REDACTED', redacted)
        self.assertIn('/bot[REDACTED]/getMe', redacted)
        self.assertEqual(redact_known_secrets('plain text'), 'plain text')


if __name__ == '__main__':
    unittest.main()
