# Log de falha de envio de WhatsApp (2026-09-08)

## Problema

O erro de envio de WhatsApp era engolido silenciosamente:
`favorites._whatsapp_favorito` tinha um `except: pass`, e
`alertas.send_whatsapp` só fazia `print` no stdout efêmero do runner. Não
havia como o dono saber que um alerta não chegou.

## Correção

As duas rotas agora gravam a **falha** (não o sucesso) na tabela
`public.whatsapp_send_log`, via o módulo novo `whatsapp_log.registrar_falha`
— que nunca levanta exceção (se o próprio insert falhar, cai num `print`).

- `favorites.py` insere com o JWT do usuário (RLS: policy de insert
  `user_id = auth.uid()`).
- `alertas.py` insere com service role (ignora RLS).

Colunas: `origem` (`favorito`|`alerta_lance`|`teste`), `telefone`,
`lote_url`, `erro`, `http_status`, `corpo`.

Migration `supabase/migrations/20260908000000_whatsapp_send_log.sql`
(idempotente) — aplicada no Supabase (confirmado pelo dono em 2026-09-09,
tabela `whatsapp_send_log` existe).

## Testes

`tests/test_whatsapp_log.py` (5 casos, `sb` falso).

## Como consultar

Só entram linhas de falha na tabela; o dono consulta pelo painel do
Supabase. Pendência (registrada no backlog do
[PLANO-DO-PROJETO.md](PLANO-DO-PROJETO.md)): definir política de retenção
da tabela.
