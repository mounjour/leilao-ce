-- Colunas e tabela de cobrança (Stripe) versionadas.
--
-- Ate agora subscription_status / stripe_customer_id / stripe_subscription_id
-- / subscription_current_period_end, alem de updated_at e billing_exempt,
-- so existiam no painel do Supabase (criadas a mao). A Edge Function
-- supabase/functions/stripe-webhook/index.ts escreve nessas colunas e
-- consulta billing_webhook_events para deduplicar eventos; auth.py le
-- subscription_status/billing_exempt em is_subscribed() e stripe_customer_id
-- no portal de cobranca. Este arquivo passa a ser a fonte de verdade.
--
-- Tudo idempotente (if not exists): rodar contra o banco atual e no-op.
-- Rodar manualmente no Supabase SQL Editor (nao ha deploy automatico de
-- migrations neste projeto).

-- 1) Colunas de cobranca em public.profiles.
alter table public.profiles
  add column if not exists subscription_status text;
alter table public.profiles
  add column if not exists stripe_customer_id text;
alter table public.profiles
  add column if not exists stripe_subscription_id text;
alter table public.profiles
  add column if not exists subscription_current_period_end timestamptz;

-- updated_at: o webhook grava em toda sincronizacao de assinatura.
alter table public.profiles
  add column if not exists updated_at timestamptz not null default now();

-- billing_exempt: contas isentas de cobranca (is_subscribed() em auth.py
-- retorna true sem checar o Stripe).
alter table public.profiles
  add column if not exists billing_exempt boolean not null default false;

-- 2) Indices para os lookups do webhook (updateProfile busca por essas
--    colunas quando o evento nao traz o supabase_user_id).
create index if not exists profiles_stripe_customer_id_idx
  on public.profiles (stripe_customer_id);
create index if not exists profiles_stripe_subscription_id_idx
  on public.profiles (stripe_subscription_id);

-- 3) Log de eventos ja processados do Stripe (idempotencia do webhook).
create table if not exists public.billing_webhook_events (
  event_id    text primary key,
  event_type  text,
  received_at timestamptz not null default now()
);

-- RLS ligada e sem policies: so a service role (a Edge Function) enxerga.
alter table public.billing_webhook_events enable row level security;
