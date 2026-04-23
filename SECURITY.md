# Security Operations

## Vercel Environment Variables

Production and Preview should use separate values for all secrets:

- `DART_API_KEY`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `FINANCIAL_MODEL_API_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`
- `CACHE_ADMIN_TOKEN`

Do not use the ambiguous legacy `SUPABASE_KEY` name in Vercel. The code only accepts it when
`SUPABASE_ALLOW_LEGACY_SERVICE_ROLE_KEY=true`, which should be limited to temporary local
migration work.

## Supabase Cache

The `financial_data` table is a server-side cache used by the authenticated
`/api/financial-model` endpoint. Keep the Supabase service-role key in serverless
environment variables only. Never expose it to browser JavaScript.

Recommended cache behavior:

- `SUPABASE_SERVICE_ROLE_KEY`: set only in server environments that need cache reads.
- `SUPABASE_CACHE_WRITES=false`: default. The API reads existing cache but does not write.
- `SUPABASE_CACHE_WRITES=true`: enable only after confirming the endpoint auth token,
  rate limit, and logging redaction are active in the same environment.

Recommended table hardening:

```sql
alter table public.financial_data enable row level security;

-- Do not create anon/authenticated policies for this cache table.
-- Serverless functions use SUPABASE_SERVICE_ROLE_KEY and endpoint-level auth.
revoke all on table public.financial_data from anon, authenticated;
```

## Dependency Audit

Dependencies are pinned in `requirements.txt`. Re-run an OSV or pip-audit scan before
updating pins, and update the whole Supabase dependency set together.

## Durable Runtime Cache

When `UPSTASH_REDIS_REST_URL`/`UPSTASH_REDIS_REST_TOKEN` or Vercel Marketplace's
`KV_REST_API_URL`/`KV_REST_API_TOKEN` are set, selected server-side caches use
Upstash Redis as a cross-instance TTL cache. Keep those variables server-only.

The `/api/cache-bust` endpoint deletes a single durable cache key. Protect it
with `CACHE_ADMIN_TOKEN`; if that token is absent, the endpoint falls back to
`FINANCIAL_MODEL_API_TOKEN`. It does not purge already-warm in-memory entries
inside other Vercel function instances, so short local TTLs still apply.

## External Rate Limits

Provider-wide rate limiting is enabled by default through
`EXTERNAL_RATE_LIMITS_ENABLED=true`. With Upstash configured, limits are shared
across Vercel function instances; without Upstash they are per warm instance.

Tune these values after looking at `external_api_call`,
`provider_rate_limit_wait`, and `provider_rate_limit_exceeded` logs:

- `EXTERNAL_RATE_DART_PER_MINUTE`
- `EXTERNAL_RATE_KRX_PER_MINUTE`
- `EXTERNAL_RATE_NAVER_PER_MINUTE`
- `EXTERNAL_RATE_GEMINI_PER_MINUTE`
- `EXTERNAL_RATE_GEMINI_TOKENS_PER_MINUTE`
- `EXTERNAL_RATE_TELEGRAM_PER_MINUTE`
- `EXTERNAL_RATE_LIMIT_MAX_WAIT`

For `/api/financial-model`, `DART_FINANCIAL_MAX_WORKERS` defaults to 2 to avoid
bursting DART with 20 concurrent-ish calls on a cold cache. Raise it only after
the durable cache hit rate is healthy.

Set `CACHE_ACCESS_LOGS_ENABLED=true` temporarily when you need hit/miss/stale
ratios from Vercel Logs. Leave it off during normal operation if log volume
matters.
