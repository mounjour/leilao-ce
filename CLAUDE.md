CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: leilaoce.streamlit.app (Streamlit Community Cloud, atualiza no push do main)
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-09-03):
- Scraping: Leilo, Mega, Pacto, MGL, Montenegro, Construbem, Daniel Garcia,
  MJ Leilões e Celso Cunha implementados. MGL reescrito em 2026-09-02 para
  usar a API JSON (POST /apiplugin/GetBusca com ID_Estado:23, veículos +
  imóveis do CE) — código validado com dados reais, MAS 2 runs manuais
  confirmaram que o Cloudflare bloqueia o site inteiro a partir do IP do
  GitHub Actions (SPA nao inicializa + 403). Parado até ter proxy residencial
  (ver MGL_SCRAPER_PENDENTE.md). Construbem/Daniel Garcia = mesmo muro;
  Zenrows sem crédito (402) e ScraperAPI com timeout nos runs de 2026-09-02.
  Sodré Santoro investigado em 2026-08-31 e descartado: pátios só em SP/PR,
  sem estoque no CE (ver SODRE_SANTORO_DESCARTADO.md).
- IA (Anthropic): créditos esgotados nos runs de 2026-09-02 — circuit breaker
  desliga a análise e usa fallback "Não informado" em todos os lotes.
- Favoritos: pronto, sincronizando com Supabase (upsert por user_id,lote_url).
- Cadastro/login: pronto, Supabase Auth (fluxo PKCE) + trigger handle_new_user.
- Planos pagos (Stripe): enforcement ligado — dashboard.py bloqueia quem não
  tem assinatura ativa. Portal de cobrança e webhook funcionando.
- stripe-webhook (commit 3e1694a, 2026-09-03): fallback de emergência do
  updateProfile agora puxa phone/name/full_name de auth.users
  (raw_user_meta_data via admin API) quando cria a linha de profiles — antes
  nascia sem telefone e alertas.py não mandava WhatsApp se o trigger
  handle_new_user tivesse falhado no signup. Type-check com deno check =
  OK (exit 0, 2026-09-03). deno 2.9.6 instalado via winget; supabase CLI
  2.116.0 instalado via scoop (bucket main). PENDENTE (precisa das
  credenciais do dono): supabase login / supabase link --project-ref <ref> /
  supabase functions deploy stripe-webhook.
- Migration das colunas de cobrança: criada
  supabase/migrations/20260903000000_billing_columns.sql (idempotente) com
  subscription_status, stripe_customer_id, stripe_subscription_id,
  subscription_current_period_end, updated_at, billing_exempt, índices e a
  tabela billing_webhook_events. PENDENTE: rodar no SQL Editor do Supabase
  (não há deploy automático de migrations).

BACKLOG:
- Achar outro leiloeiro que de fato opere no CE (Sodré Santoro foi
  descartado — ver STATUS).
- MGL: rotear /apiplugin/GetBusca e as páginas de lote pelo Zenrows/ScraperAPI
  (padrão de _raspar_soleon) — é a única saída, o IP do runner é bloqueado.
  Depende de recarregar crédito Zenrows/ScraperAPI.
- Recarregar crédito Zenrows/ScraperAPI (destrava MGL + Construbem +
  Daniel Garcia de uma vez) e crédito Anthropic (destrava a análise de IA).
- stripe-webhook: endurecimento do fallback (phone/name) e migration das
  colunas de cobrança FEITOS em 2026-09-03 (commit 3e1694a). Resta o deploy
  da Edge Function e rodar a migration no painel do Supabase (ver STATUS).
- dashboard.py: CSS de sidebar consolidado (painel em "SIDEBAR (bloco
  unico)"; moldura header/toolbar/colapso em "HEADER/TOOLBAR E BOTÃO DE
  COLAPSO DA SIDEBAR (bloco unico)"). Sem duplicatas pendentes.

CONVENÇÕES:
- Mensagens em português, código em inglês (variáveis, funções)
- Sem emojis dentro de código Python, apenas no UI do Streamlit
- Antes de mudanças grandes, sempre apresente um plano para eu aprovar
- Não rode "git push" sem me perguntar primeiro
