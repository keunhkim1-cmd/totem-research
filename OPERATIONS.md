# Operations Runbook

## External API Integration

### Environment Sync

Local development reads `.env` when running `python3 serve.py`, but deployed
functions only read Vercel environment variables.

Recommended flow:

1. Pull scoped Vercel values when you need an exact local mirror:
   `vercel env pull .env.local`
2. Run local smoke checks with Vercel-provided env:
   `vercel env run -- python3 serve.py`
3. Keep Production and Preview values separate for:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_WEBHOOK_SECRET`
   - `FINANCIAL_MODEL_API_TOKEN`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `CACHE_ADMIN_TOKEN`
   - `CRON_SECRET`

Required production checks:

- `/api/telegram` should report `configured`.
- `/api/financial-model` should return 401 without a token, not 503.
- `/api/warm-cache` should return 401 without Vercel's cron bearer token, not 503.

### Required Checks After Deploy

1. Open `/api/debug` with `DEBUG_ENABLED=true` only in a protected environment.
   Confirm:
   - `durable_cache_enabled` is `true` when Upstash is configured.
   - `provider_rate_limits_per_minute` matches the intended production limits.
   - `environment.missing` is empty for enabled features.

2. Exercise one low-cost request per public endpoint:
   - `/api/stock-code?name=삼성전자`
   - `/api/stock-price?code=005930`
   - `/api/warn-search?name=삼성전자`
   - `/api/caution-search?name=삼성전자`

3. Check Vercel Logs for:
   - `external_api_call` with `result=success`
   - no burst of `external_api_retry`
   - no unexpected `provider_rate_limit_exceeded`

### Frontend Asset Budget

After frontend edits, run:

```bash
python3 scripts/check_frontend_budget.py
python3 scripts/check_frontend_smoke.py
```

This guards the static SPA against drifting back into a large single HTML file.
See `FRONTEND_BUILD_ROI.md` for the current bundler decision record.

### Cache Hit/Miss Audit

Set `CACHE_ACCESS_LOGS_ENABLED=true` briefly, then repeat the same endpoint calls.
Turn it off after collecting enough logs.

Useful events:

- `cache_access`: cache name, key, state (`hit`, `miss`, `stale`, `durable_hit`)
- `cache_stale_returned`: stale fallback was used after an upstream failure
- `dart_financial_stale_returned`: DART financial stale data was returned
- `gemini_summary_stale_returned`: Gemini summary stale data was returned

### Rate Limit Audit

Useful events:

- `external_api_call`: provider, result, elapsed, attempts, rate wait
- `external_api_retry`: retry attempt and delay
- `provider_rate_limit_wait`: request waited locally before calling provider
- `provider_rate_limit_exceeded`: provider budget exhausted beyond max wait
- `financial_dart_fetch_plan`: planned DART financial calls for one model build
- `financial_dart_fetch_burst`: one financial request is likely too expensive

Suggested first production limits:

- `EXTERNAL_RATE_DART_PER_MINUTE=900`
- `EXTERNAL_RATE_KRX_PER_MINUTE=120`
- `EXTERNAL_RATE_NAVER_PER_MINUTE=180`
- `EXTERNAL_RATE_GEMINI_PER_MINUTE=10`
- `EXTERNAL_RATE_GEMINI_TOKENS_PER_MINUTE=0`
- `EXTERNAL_RATE_TELEGRAM_PER_MINUTE=900`
- `DART_FINANCIAL_MAX_WORKERS=2`

Set `EXTERNAL_RATE_GEMINI_TOKENS_PER_MINUTE` only after you know your Gemini
project TPM limit. The value is measured in estimated 1K-token units per minute.

### Manual Cache Bust

Use `/api/cache-bust` only with `CACHE_ADMIN_TOKEN` or `FINANCIAL_MODEL_API_TOKEN`.
It deletes one durable cache key from Upstash. Warm in-memory entries inside
already-running function instances may remain until their local TTL expires.

Example durable keys:

- `krx-kind:kind:1:1:21:1000:YYYY-MM-DD`
- `naver-code:code:삼성전자`
- `dart-full:all:00126380:2024:11011:CFS`
- `dart-report-summary:summary:005930:RCEPT_NO:v1`

### Scheduled Cache Warm

`vercel.json` runs `/api/warm-cache` at 07:10 UTC, Monday-Friday. That is
16:10 KST, shortly after the Korean cash-market close.

The job warms:

- KRX warning/risky pages
- KRX caution page
- Samsung Electronics Naver code and price lookups
- KOSPI/KOSDAQ index price lookups
- DART corp-code map

Set `CRON_SECRET` in Production before deployment. With Upstash configured, the
job uses a Redis lock to avoid overlapping runs.

### DART Corp Registry Refresh

`data/dart-corps.json` is the bundled fallback for DART company lookup and the
financial-model corp-code allowlist. Refresh it after meaningful listing changes,
or schedule it in a trusted maintenance environment:

```bash
DART_API_KEY=... python3 scripts/update_dart_corps.py
python3 -m unittest discover -s tests
```

### Telegram Webhook

Telegram retries webhooks when the function times out or fails before returning
200. With Upstash configured, update processing claims expire after
`TELEGRAM_IDEMPOTENCY_PROCESSING_TTL`, while completed updates remain deduped for
`TELEGRAM_IDEMPOTENCY_DONE_TTL`.

Long term, `/info` should move to an acknowledge-first flow if real p95 exceeds
Telegram webhook tolerance.

### Rollback

If a Production deployment is bad but a previous deployment is healthy:

1. List recent Production deployments with `vercel list`.
2. Inspect the known-good deployment with `vercel inspect <deployment-url>`.
3. Promote or roll back from the Vercel dashboard, or use
   `vercel rollback <deployment-url>` when the CLI is available.
4. Re-run the Required Checks After Deploy section.
