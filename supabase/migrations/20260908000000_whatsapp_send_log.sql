-- Log persistente de FALHA no envio de WhatsApp (Evolution API).
--
-- Ate agora as duas rotas de envio engoliam o erro:
--   - favorites.py -> _whatsapp_favorito: "except Exception: pass" (silencio
--     total; um favorito salvava mas a confirmacao nunca saia e ninguem sabia)
--   - alertas.py  -> send_whatsapp: so um print() no stdout do job/app, que
--     e efemero (some no redeploy do Streamlit Cloud / fim do run do Actions)
--
-- Esta tabela e o unico sink de fato persistente nesse contexto. So entram
-- linhas de FALHA. O dono consulta pelo painel do Supabase / SQL Editor.
--
-- Idempotente (if not exists / drop policy antes de create): rodar contra o
-- banco atual e no-op. Rodar manualmente no Supabase SQL Editor (nao ha
-- deploy automatico de migrations neste projeto).

create table if not exists public.whatsapp_send_log (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  -- dono do favorito/alerta; set null se a conta for apagada (mantem o log).
  user_id     uuid references auth.users (id) on delete set null,
  origem      text not null,   -- 'favorito' | 'alerta_lance' | 'teste'
  telefone    text,            -- numero formatado que falhou (55DDD...)
  lote_url    text,
  erro        text,            -- str(exc)
  http_status int,             -- status da Evolution quando houve resposta
  corpo       text             -- primeiros ~500 chars do corpo de erro
);

create index if not exists whatsapp_send_log_created_at_idx
  on public.whatsapp_send_log (created_at desc);
create index if not exists whatsapp_send_log_origem_idx
  on public.whatsapp_send_log (origem);

-- RLS ligada. Uma unica policy: o app (favorites.py, com JWT do usuario)
-- insere a linha do PROPRIO envio. Sem policy de select/update/delete -> so a
-- service role (alertas.py no GitHub Actions, painel do Supabase, SQL Editor)
-- le/edita. Mesmo padrao de billing_webhook_events.
alter table public.whatsapp_send_log enable row level security;

drop policy if exists "usuario insere log do proprio envio"
  on public.whatsapp_send_log;
create policy "usuario insere log do proprio envio"
  on public.whatsapp_send_log
  for insert
  to authenticated
  with check (user_id = auth.uid());
