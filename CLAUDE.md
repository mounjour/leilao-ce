CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: leilaoce.streamlit.app (Streamlit Community Cloud, atualiza no push do main)
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-08-27):
- Scraping: Leilo, Mega, Pacto, MGL, Montenegro, Construbem, Daniel Garcia,
  MJ Leilões e Celso Cunha implementados. MGL quebrado (ver
  MGL_SCRAPER_PENDENTE.md); Construbem/Daniel Garcia dependem de crédito
  Zenrows. Sodré Santoro ainda não feito.
- Favoritos: pronto, sincronizando com Supabase (upsert por user_id,lote_url).
- Cadastro/login: pronto, Supabase Auth (fluxo PKCE) + trigger handle_new_user.
- Planos pagos (Stripe): enforcement ligado — dashboard.py bloqueia quem não
  tem assinatura ativa. Portal de cobrança e webhook funcionando.

BACKLOG:
- Consertar scraper MGL e adicionar Sodré Santoro.
- stripe-webhook faz só UPDATE em profiles (nunca INSERT) — frágil se o
  trigger handle_new_user falhar no signup.
- dashboard.py: CSS de sidebar duplicado entre bloco legado e bloco "V3".

CONVENÇÕES:
- Mensagens em português, código em inglês (variáveis, funções)
- Sem emojis dentro de código Python, apenas no UI do Streamlit
- Antes de mudanças grandes, sempre apresente um plano para eu aprovar
- Não rode "git push" sem me perguntar primeiro
