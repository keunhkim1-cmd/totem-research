# Architecture

## Layer Rules

`api/` is the HTTP transport layer. Handlers should parse requests, enforce
endpoint auth when needed, call one shared use case, and shape the HTTP response.
Business logic should not live directly in `api/*.py`.

`lib/usecases.py` is the thin application layer shared by Vercel handlers and
`serve.py`. Put endpoint-level orchestration here when both local and deployed
paths need the same behavior.

`lib/` contains provider adapters, shared policy, parsing, validation, cache,
retry, and message-building code. Provider adapters should call
`lib/http_client.py` instead of opening URLs directly.

`data/` contains packaged fallback/reference data. Treat `data/dart-corps.json`
and `data/account-mapping.json` as server-side inputs, not public UI payloads.

`scripts/` contains trusted maintenance utilities. Scripts may write generated
data when explicitly run by an operator.

## Telegram Split

`api/telegram.py` handles webhook validation, update freshness, idempotency, and
command routing.

`lib/telegram_commands.py` handles command use cases.

`lib/telegram_messages.py` builds Telegram text.

`lib/telegram_transport.py` sends Telegram Bot API requests.

## Provider Adapter Checklist

When adding a new external API:

1. Add a provider adapter under `lib/`.
2. Use `lib/http_client.py` for retries, redaction, logging, and rate limiting.
3. Add timeout constants to `lib/timeouts.py` and rate defaults to
   `lib/provider_rate_limit.py`.
4. Add provider-specific typed errors in `lib/errors.py` when callers need
   different user-facing behavior.
5. Put endpoint orchestration in `lib/usecases.py`.
6. Keep `api/*.py` as request/response glue.
7. Add `.env.example`, `SECURITY.md`, and `OPERATIONS.md` entries for new envs.
8. Add unit tests with provider calls mocked behind the adapter boundary.

## API Response Contract

All JSON endpoints should return `ok: true` on success and `ok: false` with
`errorInfo.code` and `errorInfo.message` on failure.

Do not add new top-level legacy error fields. The only intentional
`errorMessage` compatibility surface is `/api/caution-search`, including the
matching local-server route in `serve.py`, while older caution clients finish
migrating to `errorInfo.message`.

## DART Adapter Rules

Use `lib/dart_base.py` for DART API key injection, URL construction, bytes/JSON
fetches, retryable DART statuses, and `raise_for_status()`.

Existing modules keep domain-specific responsibilities:

- `lib/dart.py`: disclosure list search
- `lib/dart_full.py`: full financial statement endpoint
- `lib/dart_registry.py`: corp-code registry
- `lib/dart_report.py`: business-report document extraction

Do not duplicate `crtfc_key`, request URLs, or DART status handling outside
`lib/dart_base.py`.
