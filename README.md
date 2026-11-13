# Achadin Leilões (leilao-ce)

SaaS de monitoramento de leilões no **Ceará** (carros, motos, caminhões, imóveis,
equipamentos, eletrônicos). Junta os lotes de vários leiloeiros num painel só, compara com a
tabela FIPE, usa IA para avaliar o estado do item e avisa por WhatsApp quando o lance de um
lote favoritado muda. Acesso por assinatura (Stripe).

- Site: `achadinleiloes.tech` (landing estática em `/`, app Streamlit em `/app/`)
- Contexto operacional detalhado e status: [`CLAUDE.md`](CLAUDE.md)
- Pendências: [GitHub Issues](https://github.com/mounjour/leilao-ce/issues)

## Onde fica o quê

| Caminho | O que é |
|---|---|
| `scraper.py` | Coleta de todas as fontes, FIPE, IA, dedup entre fontes; gera `leiloes.json` |
| `scraper_health.py` | Placar de saúde por fonte (`scraper_health.json`) e alerta ao dono |
| `dashboard.py` | App Streamlit (painel, filtros, cards, paywall) |
| `auth.py` | Cadastro/login (Supabase Auth, PKCE) e cobrança (Stripe Checkout/Portal) |
| `favorites.py` | Favoritos no Supabase e WhatsApp ao favoritar |
| `alertas.py` | Alerta de mudança de lance dos favoritos (roda depois do scraper) |
| `whatsapp_log.py` | Grava falhas de envio em `whatsapp_send_log` |
| `legal.py` | Termos, privacidade e reembolso (`?pagina=...`) |
| `design_tokens.py`, `site/` | Tokens visuais compartilhados e landing estática |
| `deploy/` | Nginx, drop-in do systemd e script do cutover da landing |
| `supabase/` | Migrations e a Edge Function `stripe-webhook` (Deno) |
| `tests/`, `conftest.py` | Suíte pytest das funções puras (sem browser nem chave de API) |
| `scripts/`, `teste_alerta.py` | Utilitários manuais (`teste_alerta.py` dispara WhatsApp real) |
| `docs/contexto/` | Fontes (`fontes/`), incidentes, guias de setup (`setup/`) |

Os `.py` ficam soltos na raiz de propósito (layout single-context, ver
[`docs/agents/domain.md`](docs/agents/domain.md)).

## Arquitetura

```
GitHub Actions (cron diário)                 VPS (Nginx + systemd)
  scraper.py ──► leiloes.json (commit) ──►     dashboard.py (Streamlit, /app/)
  alertas.py ──► WhatsApp (Evolution API)         │
  scraper_health.py                               ├─► Supabase (Auth + Postgres)
                                                  └─► Stripe (Checkout/Portal)
                                       Stripe ──► stripe-webhook (Edge Function) ──► Supabase
```

- **`leiloes.json` é o banco dos lotes.** Não há tabela de lotes no Postgres: o scraper gera o
  arquivo, o bot commita na `main` e o dashboard lê direto (`st.cache_data`). Funciona porque o
  volume é de centenas/poucos milhares de lotes e a atualização é diária.
- **Postgres (Supabase)** só para o que precisa de consistência: `profiles` (usuário, telefone,
  status da assinatura), `favorites` (upsert por `user_id,lote_url`, com snapshot em
  `lote_data`), `billing_webhook_events` (dedup do webhook) e `whatsapp_send_log`.
- **IA** (Anthropic, Claude Haiku) só avalia o estado do item, com cache em
  `analises_ia_cache.json` e circuit breaker: sem crédito, cai no fallback "Não informado" e
  nunca bloqueia o scraper. A oportunidade de preço vs. FIPE é calculada localmente.
- **Coleta**: `requests` na maioria das fontes; Zenrows/ScraperAPI só onde há Cloudflare no IP
  do runner; Playwright ainda instalado para as fontes que precisam.
- **Alertas**: WhatsApp via Evolution API (não oficial). Gatilho único: mudança de
  `lance_atual` em lote favoritado. Falha de envio é best-effort e fica registrada em
  `whatsapp_send_log`. Risco de bloqueio do número aceito pelo dono (não migrar para a Cloud
  API oficial da Meta).
- **Sem staging**: push na `main` dispara `deploy.yml` direto para produção. O gate é o
  `pytest` (`tests.yml` e `scraper.yml`).

Fora de escopo por decisão do dono: relatórios/exportação, notificação de lote novo por filtro
salvo, papel de administrador dentro do app (administração pelo painel do Supabase/Stripe).

## Rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-web.txt      # só o site
streamlit run dashboard.py
```

O `.env` precisa de `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `STRIPE_SECRET_KEY`,
`STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRICE_ID` e `APP_URL`. Para o scraper:
`pip install -r requirements.txt && playwright install chromium`.

Testes (não precisam de browser nem de chave):

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Guias

- Deploy na VPS: [`docs/contexto/setup/SETUP_HOSTINGER_VPS.md`](docs/contexto/setup/SETUP_HOSTINGER_VPS.md)
  (alternativa: [`SETUP_ORACLE_FREE.md`](docs/contexto/setup/SETUP_ORACLE_FREE.md)) e operação em
  [`OPERACAO_VPS.md`](docs/contexto/setup/OPERACAO_VPS.md)
- Workflows e secrets do GitHub Actions: [`docs/contexto/setup/SETUP_GITHUB_ACTIONS.md`](docs/contexto/setup/SETUP_GITHUB_ACTIONS.md)
- Backup do Postgres: [`docs/contexto/setup/SETUP_BACKUP_DB.md`](docs/contexto/setup/SETUP_BACKUP_DB.md)
- WhatsApp (Evolution API): [`docs/contexto/setup/SETUP_EVOLUTION.md`](docs/contexto/setup/SETUP_EVOLUTION.md)
- Saúde do scraper: [`docs/contexto/SCRAPER_HEALTH.md`](docs/contexto/SCRAPER_HEALTH.md)
- Fontes ativas, pausadas e incidentes: [`docs/contexto/fontes/`](docs/contexto/fontes/)
