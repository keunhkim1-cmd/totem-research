# Operations Runbook

## External API Integration

### Required Checks After Deploy

1. Open `/api/debug` with `DEBUG_ENABLED=true` only in a protected environment.
   Confirm:
   - `durable_cache_enabled` is `true` when Upstash is configured.
   - `provider_rate_limits_per_minute` matches the intended production limits.

2. Exercise one low-cost request per public endpoint:
   - `/api/stock-code?name=삼성전자`
   - `/api/stock-price?code=005930`
   - `/api/warn-search?name=삼성전자`
   - `/api/caution-search?name=삼성전자`

3. Check Vercel Logs for:
   - `external_api_call` with `result=success`
   - no burst of `external_api_retry`
   - no unexpected `provider_rate_limit_exceeded`

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

### Telegram Webhook

Telegram retries webhooks when the function times out or fails before returning
200. With Upstash configured, update processing claims expire after
`TELEGRAM_IDEMPOTENCY_PROCESSING_TTL`, while completed updates remain deduped for
`TELEGRAM_IDEMPOTENCY_DONE_TTL`.

Long term, `/info` should move to an acknowledge-first flow if real p95 exceeds
Telegram webhook tolerance.
