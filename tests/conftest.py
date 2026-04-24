import pytest


SECRET_QUERY_KEYS = (
    'access_token',
    'api_key',
    'apikey',
    'crtfc_key',
    'key',
    'token',
    'x-goog-api-key',
)

SECRET_HEADERS = (
    'authorization',
    'cookie',
    'x-api-key',
    'x-financial-model-token',
    'x-goog-api-key',
)


def _strip_response_cookies(response):
    headers = response.get('headers') or {}
    for key in list(headers):
        if key.lower() == 'set-cookie':
            headers[key] = ['REDACTED']
    return response


@pytest.fixture(scope='session')
def vcr_config():
    return {
        'before_record_response': _strip_response_cookies,
        'decode_compressed_response': True,
        'filter_headers': SECRET_HEADERS,
        'filter_query_parameters': SECRET_QUERY_KEYS,
    }
