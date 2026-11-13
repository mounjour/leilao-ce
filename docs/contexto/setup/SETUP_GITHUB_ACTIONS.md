# GitHub Actions — workflows e secrets

> Resumo: seis workflows em `.github/workflows/`. O scraper roda 1x/dia e commita os dados na
> `main`; o deploy vai para a VPS a cada push na `main` e depois de cada run do scraper. Esta
> página lista o que cada um faz e de quais secrets depende.

## Workflows

| Workflow | Quando roda | O que faz |
|---|---|---|
| `scraper.yml` (Scraper LeilãoCE) | 06:00 UTC (03:00 Fortaleza) e manual | `pytest` como gate, roda `scraper.py`, commita `leiloes.json`, `scraper_health.json` e caches (`chore: atualiza leiloes.json [auto ...]`), depois `alertas.py` |
| `deploy.yml` (Deploy do site) | push na `main` e `workflow_run` do scraper com sucesso | SSH na VPS: atualiza o código, reinstala deps, publica `site/`, reinicia o serviço. O `workflow_run` existe porque o push feito com `GITHUB_TOKEN` não dispara outros workflows |
| `tests.yml` (Testes) | push e PR | `python -m pytest -q` |
| `backup-db.yml` | 08:00 UTC e manual | `pg_dump` do Supabase como artifact (90 dias). Ver [`SETUP_BACKUP_DB.md`](SETUP_BACKUP_DB.md) |
| `uptime.yml` | a cada 15 min | Health do Streamlit, `GET /` e validade do certificado. Ver [`OPERACAO_VPS.md`](OPERACAO_VPS.md) |
| `teste_alerta.yml` | manual | Dispara um WhatsApp real para o número informado (teste da Evolution API) |

Para mudar a frequência do scraper, editar o `cron` do `scraper.yml` (em UTC; Fortaleza é
UTC-3, sem horário de verão). Ex.: `0 6,18 * * *` = 03h e 15h.

## Secrets (Settings > Secrets and variables > Actions)

| Secret | Usado por | Observação |
|---|---|---|
| `ANTHROPIC_API_KEY` | scraper | IA do estado do item; sem crédito, cai no fallback |
| `ZENROWS_API_KEY` | scraper | MGL e Construbem |
| `SCRAPERAPI_KEY` | scraper | Daniel Garcia |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | scraper (alertas), teste_alerta | Service role ignora RLS |
| `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE` | scraper (alertas), teste_alerta | Ver [`SETUP_EVOLUTION.md`](SETUP_EVOLUTION.md) |
| `OWNER_WHATSAPP` | scraper (health check) | Ausente = só `::warning::` no log |
| `SUPABASE_DB_URL` | backup-db | Session pooler, porta 5432 |
| `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` | deploy | Ver [`SETUP_HOSTINGER_VPS.md`](SETUP_HOSTINGER_VPS.md), seção 6 |

O commit do scraper exige **Settings > Actions > General > Workflow permissions > Read and
write permissions** (o workflow já declara `contents: write`).

## Troubleshooting

- **Scraper falhou no passo de testes**: o `pytest` é gate; corrigir o teste/código antes.
- **Fonte zerou**: ver o log do passo "Rodar scraper" e o
  [`SCRAPER_HEALTH.md`](../SCRAPER_HEALTH.md); incidentes anteriores em
  [`../fontes/incidentes/`](../fontes/incidentes/).
- **Sem push do bot**: conferir a permissão de escrita acima e se o branch padrão é `main`.
- **Site não pegou os dados novos**: o dashboard usa `st.cache_data(ttl=1800)`; conferir se o
  `deploy.yml` rodou depois do scraper.
- Limite do plano gratuito: repo público é ilimitado; privado tem 2.000 min/mês.
