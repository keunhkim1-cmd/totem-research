-- Runtime cache tables used only by server-side functions.

create table if not exists public.financial_data (
    corp_code text not null check (corp_code ~ '^[0-9]{8}$'),
    fs_div text not null check (fs_div in ('CFS', 'OFS')),
    period_type text not null check (period_type in ('annual', 'quarterly')),
    period_key text not null check (period_key ~ '^([0-9]{4}|[1-4]Q[0-9]{2})$'),
    data jsonb not null,
    source text not null default 'dart',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (corp_code, fs_div, period_type, period_key)
);

create index if not exists financial_data_corp_fs_idx
    on public.financial_data (corp_code, fs_div);

create or replace function public.set_financial_data_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists financial_data_set_updated_at on public.financial_data;

create trigger financial_data_set_updated_at
before update on public.financial_data
for each row
execute function public.set_financial_data_updated_at();

create table if not exists public.telegram_updates (
    update_id text primary key,
    created_at timestamptz not null default now()
);

create index if not exists telegram_updates_created_at_idx
    on public.telegram_updates (created_at);

alter table public.financial_data enable row level security;
alter table public.telegram_updates enable row level security;

revoke all on table public.financial_data from anon, authenticated;
revoke all on table public.telegram_updates from anon, authenticated;

comment on table public.financial_data is
    'Server-side DART financial model cache. Accessed with the Supabase service-role key only.';

comment on table public.telegram_updates is
    'Optional server-side Telegram update idempotency store. Delete old rows after the webhook retry window.';
