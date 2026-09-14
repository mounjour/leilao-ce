# Backup do banco (Supabase Postgres)

O plano do Supabase deste projeto é **Free**, que **não faz backup automático**. Se o
Postgres for apagado, corrompido por uma migration ruim ou perdido num incidente do
Supabase, não há cópia em lugar nenhum de:

- `public.profiles` — usuários, telefone, status de assinatura, IDs do Stripe
- `public.favorites` — os lotes favoritados de cada usuário (`lote_data`)
- `public.billing_webhook_events` — dedupe do webhook do Stripe
- `public.whatsapp_send_log` — log de falha de envio de WhatsApp
- `auth.users` e o resto do schema `auth` — as contas em si

(Os `leiloes.json`, `analises_ia_cache.json` etc. **já estão versionados no git** — esses
não entram no backup do banco.)

## Como funciona

`.github/workflows/backup-db.yml` roda `pg_dump` **1×/dia às 08:00 UTC** (05:00 Fortaleza,
fora dos horários do scraper) e também sob demanda pela aba **Actions > Backup do banco
(Supabase) > Run workflow**.

- Dumpa os schemas **`public` + `auth`** (`--no-owner --no-privileges --clean --if-exists`).
- `pg_dump` roda dentro do container `postgres:17-alpine` para garantir versão de cliente
  compatível com o servidor.
- O dump sai gzipado (`supabase-<timestamp>.sql.gz`) e é publicado como **artifact do
  GitHub Actions**, com **retenção de 90 dias** (teto do GitHub).
- O job **falha** se o secret não estiver configurado ou se o dump vier vazio.

### Limitação: 90 dias

O artifact expira em 90 dias. Para ter um ponto de restauração mais antigo, **baixe 1
artifact por mês** (aba Actions > run do backup > seção Artifacts) e guarde off-site
(Drive, S3, disco local). Se isso virar incômodo, o próximo passo é o workflow enviar o
dump direto para um bucket (S3/B2/GCS) — precisa de credenciais de storage.

## Configuração (uma vez)

1. **Pegar a connection string** no painel do Supabase:
   - Botão verde **"Connect"** na barra superior do projeto → seção **Connection string**.
   - Use a aba **Session pooler** **ou** **Direct connection** — o que vale é a **porta
     5432**. **Não** use o **Transaction pooler (porta 6543)**: não funciona com `pg_dump`.
   - Session pooler: `postgresql://postgres.<ref>:[SENHA]@aws-0-<region>.pooler.supabase.com:5432/postgres`
   - Direct connection: `postgresql://postgres:[SENHA]@db.<ref>.supabase.co:5432/postgres`
   - Troque `[SENHA]` pela senha do banco (Settings → Database → Database password; se não
     souber, dá pra resetar ali — isso invalida outras strings que usem essa senha).

2. **Adicionar o secret** no GitHub:
   - Repo → Settings → Secrets and variables → **Actions** → New repository secret
   - Nome: `SUPABASE_DB_URL`
   - Valor: a connection string completa do passo 1

3. **Testar**: aba Actions → **Backup do banco (Supabase)** → Run workflow → conferir que
   o artifact `supabase-<timestamp>.sql.gz` aparece no fim do run.

## Como restaurar

Baixe e descomprima o artifact:

```bash
gunzip supabase-<timestamp>.sql.gz
```

### Para um banco existente (rollback no mesmo projeto)

O dump usa `--clean --if-exists`, então ele derruba e recria os objetos de `public` e
`auth` antes de recarregar os dados:

```bash
psql "$SUPABASE_DB_URL" -f supabase-<timestamp>.sql
```

### Para um projeto Supabase novo (perda total)

1. Crie um projeto novo no Supabase.
2. Rode as migrations do repo (`supabase/migrations/`) **ou** deixe o próprio dump recriar
   o schema `public` (ele tem os `CREATE TABLE`).
3. Rode o `psql ... -f` acima apontando para o banco novo.
4. Revise: o schema `auth` já existe num projeto novo — o `--clean` vai recriar as tabelas
   dele com os dados do dump; confira se o login volta a funcionar antes de apontar a
   produção para o projeto novo.

> **Faça um teste de restauração pelo menos uma vez** num projeto descartável, para saber
> que o dump presta e que o passo a passo funciona — um backup nunca testado não é um
> backup.
