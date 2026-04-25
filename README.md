# TOTEM

Korean market-data utility for investment-warning lookup, price thresholds,
DART disclosure search, financial-model JSON, and a Telegram bot webhook.

## Local Development

```bash
python3 serve.py
```

The local server reads `.env.local` first and then `.env`. Vercel functions read
only Vercel environment variables.

## Verification

Install development tools once:

```bash
. .venv/bin/activate  # create first with: python3 -m venv .venv
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
pre-commit install --install-hooks
```

Run these before deploy or broad refactors:

```bash
python -m ruff check .
python -m mypy
python -m compileall -q lib api scripts tests serve.py
python -m pytest -m "not external" --disable-socket --allow-hosts=127.0.0.1,localhost --record-mode=none --cov --cov-report=term-missing
python -m json.tool vercel.json
python scripts/sync_frontend_metadata.py --check
python scripts/check_frontend_smoke.py
python scripts/check_frontend_budget.py
```

CI runs the same fast test suite with live external network disabled. The
browser-level Playwright checks run against `python serve.py` and mocked API
responses. Cassette-backed DART/KRX/Naver tests replay committed VCR.py fixtures;
tests that require live external APIs must be marked `external` and kept out of
the default PR path. Dependabot opens monthly PRs for Python QA tooling and
GitHub Actions updates so upgrades pass through the same gates.

When adding a new cassette, record it intentionally:

```bash
python -m pytest tests/test_external_cassettes.py --record-mode=once
```

Never commit real API keys in cassettes. The test fixture filters secret query
params and headers before writing files.

Use `python -m ruff format <changed-python-files>` or pre-commit to format
Python changes incrementally. The first CI lint gate is intentionally bug-focused
to avoid a large one-time formatting churn.

## Main Runtime Paths

- Static app: `index.html`, `assets/`
- Serverless handlers: `api/`
- Shared use cases and adapters: `lib/`
- Static server-side data: `data/`
- Maintenance scripts: `scripts/`

See `ARCHITECTURE.md`, `OPERATIONS.md`, and `SECURITY.md` for structure,
operations, and secret-handling rules.
