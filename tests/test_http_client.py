import urllib.error

from lib.http_client import RetryableHTTPError, _error_from_http_error


def test_krx_http_403_is_retryable_because_kind_blocks_vercel_intermittently():
    error = urllib.error.HTTPError(
        'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do',
        403,
        'Forbidden',
        {},
        None,
    )

    mapped = _error_from_http_error('krx', error)

    assert isinstance(mapped, RetryableHTTPError)
    assert mapped.status == 403
