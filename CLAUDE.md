CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: leilaoce.streamlit.app (Streamlit Community Cloud, atualiza no push do main)
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-08-27):
- Scraping: Leilo, Mega, Pacto, MGL, Montenegro, Construbem, Daniel Garcia,
  MJ Leilões e Celso Cunha implementados. MGL quebrado (ver
  MGL_SCRAPER_PENDENTE.md); Construbem/Daniel Garcia dependem de crédito
  Zenrows. Sodré Santoro investigado em 2026-08-31 e descartado: pátios só
  em SP/PR, sem estoque no CE (ver SODRE_SANTORO_DESCARTADO.md).
- Favoritos: pronto, sincronizando com Supabase (upsert por user_id,lote_url).
- Cadastro/login: pronto, Supabase Auth (fluxo PKCE) + trigger handle_new_user.
- Planos pagos (Stripe): enforcement ligado — dashboard.py bloqueia quem não
  tem assinatura ativa. Portal de cobrança e webhook funcionando.

BACKLOG:
- Consertar scraper MGL. Achar outro leiloeiro que de fato opere no CE
  (Sodré Santoro foi descartado — ver STATUS).
- stripe-webhook: o INSERT/UPSERT em profiles já foi feito (commit fe877d2,
  updateProfile faz upsert por id quando nenhuma linha bate). Resta endurecer
  o fallback: o upsert de emergência não grava phone/name, então alertas.py
  não manda WhatsApp se o trigger handle_new_user tiver falhado no signup.
- Colunas de cobrança em profiles (subscription_status, stripe_customer_id,
  stripe_subscription_id, subscription_current_period_end) não têm migration
  versionada — só existem no painel do Supabase.
- dashboard.py: CSS de sidebar consolidado (painel em "SIDEBAR (bloco
  unico)"; moldura header/toolbar/colapso em "HEADER/TOOLBAR E BOTÃO DE
  COLAPSO DA SIDEBAR (bloco unico)"). Sem duplicatas pendentes.

CONVENÇÕES:
- Mensagens em português, código em inglês (variáveis, funções)
- Sem emojis dentro de código Python, apenas no UI do Streamlit
- Antes de mudanças grandes, sempre apresente um plano para eu aprovar
- Não rode "git push" sem me perguntar primeiro
