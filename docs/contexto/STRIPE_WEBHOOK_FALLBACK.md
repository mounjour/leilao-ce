# stripe-webhook: fallback de telefone/nome e colunas de cobrança (2026-09-03)

## Problema

Se o trigger `handle_new_user` falhasse no signup, o `profiles` do usuário
nascia sem telefone — e `alertas.py` não conseguia mandar WhatsApp pra ele,
mesmo com assinatura Stripe ativa.

## Correção (commit `3e1694a`)

O fallback de emergência do `updateProfile`, dentro da Edge Function
`stripe-webhook`, agora puxa `phone`/`name`/`full_name` de `auth.users`
(`raw_user_meta_data`, via admin API) quando precisa criar a linha de
`profiles` do zero.

Type-check com `deno check` = OK (exit 0, 2026-09-03). `deno` 2.9.6
instalado via winget; `supabase` CLI 2.116.0 via scoop (bucket main).

**Deploy feito em 2026-09-03** (`supabase functions deploy stripe-webhook`,
projeto `tybfusbovbihrkmcncux`, via API sem Docker) — o fallback que grava
phone/name já está no ar.

## Migration das colunas de cobrança

`supabase/migrations/20260903000000_billing_columns.sql` (idempotente),
adicionando: `subscription_status`, `stripe_customer_id`,
`stripe_subscription_id`, `subscription_current_period_end`, `updated_at`,
`billing_exempt`, índices e a tabela `billing_webhook_events`.

Aplicada em 2026-09-03 pelo dono via SQL Editor do Supabase — **não** está
no histórico do CLI. Se algum dia rodar `supabase db push`, ele vai
reaplicar essa migration mais a `20260826000000_handle_new_user_trigger.sql`
— as duas são idempotentes, então é seguro.
