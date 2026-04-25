from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_error_message_legacy_key_is_limited_to_caution_search_contract():
    """`errorMessage` 레거시 호환 필드는 /api/caution-search 한 곳만."""
    from lib.api_routes import ROUTES

    routes_with_legacy_errormessage = [r.path for r in ROUTES if r.legacy_key == 'errorMessage']
    assert routes_with_legacy_errormessage == ['/api/caution-search']


def test_legacy_key_errormessage_string_only_lives_in_route_registry():
    """텍스트 레벨 가드 — 레지스트리 외 파일에 'legacy_key=errorMessage'가 새지 않는다."""
    sources = [
        *sorted((ROOT / 'api').glob('*.py')),
        ROOT / 'serve.py',
        ROOT / 'lib/api_routes.py',
    ]
    matches = []
    for path in sources:
        text = path.read_text(encoding='utf-8')
        if 'legacy_key' in text and 'errorMessage' in text:
            matches.append(path.relative_to(ROOT).as_posix())

    assert matches == ['lib/api_routes.py']


def test_api_handler_files_are_thin_shims():
    """단순 GET 라우트의 api/*.py는 레지스트리 위임 외 로직이 없다."""
    from lib.api_routes import ROUTES

    for route in ROUTES:
        path = ROOT / 'api' / f'{route.path.removeprefix("/api/")}.py'
        text = path.read_text(encoding='utf-8')
        assert 'make_handler' in text, f'{path} should use make_handler'
        assert f"ROUTES_BY_PATH['{route.path}']" in text, (
            f'{path} should bind via ROUTES_BY_PATH[{route.path!r}]'
        )
