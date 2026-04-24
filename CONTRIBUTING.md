# Contributing

## Before Editing

Check the current worktree:

```bash
git status --short
```

Do not revert unrelated local changes.

## Code Conventions

- Python files use `snake_case`; public Vercel endpoint files keep URL-matching
  kebab names under `api/`.
- Keep `api/*.py` thin. Move shared endpoint behavior into `lib/usecases.py`.
- Keep provider calls behind `lib/http_client.py`.
- Prefer typed provider errors from `lib/errors.py` over broad `RuntimeError`
  when callers need a stable response code or message.
- Add type hints to new `lib/` and `scripts/` functions.

## Tests

Use `pytest`. Existing `unittest.TestCase` tests are intentionally kept
compatible with pytest discovery. Mock network calls at the provider adapter
boundary unless the test is explicitly marked `external`.

Minimum check:

```bash
python -m ruff check .
python -m mypy
python -m compileall -q lib api scripts tests serve.py
python -m pytest -m "not external" --disable-socket --allow-hosts=127.0.0.1,localhost --record-mode=none --cov --cov-report=term-missing
```

For frontend changes, also run:

```bash
python -m playwright install chromium  # first local setup only
python3 scripts/check_frontend_smoke.py
python3 scripts/check_frontend_budget.py
python -m pytest tests/test_playwright_flows.py --disable-socket --allow-hosts=127.0.0.1,localhost
```

For cassette-backed external API tests, use VCR.py/pytest recording fixtures and
filter secret-bearing query params and headers. CI runs with recording disabled,
so new external calls fail instead of silently hitting live providers.

Mypy starts on shared, low-churn `lib/` modules listed in `tool.mypy.files`.
Expand the allowlist one dependency boundary at a time, after the current target
passes without suppressing useful errors.

Coverage starts as a regression floor, not a vanity metric. Raise
`tool.coverage.report.fail_under` only after adding tests that protect real user
or provider behavior.

Ruff formatting is introduced incrementally through pre-commit. Format changed
Python files, but do not mix broad repo-wide formatting with behavioral changes.

## Deploy Notes

Use `OPERATIONS.md` for deployment checks and `SECURITY.md` for env/secret
rules. Production and Preview should not share webhook, cache admin, Supabase
service-role, or financial-model tokens unless the Preview is protected.
