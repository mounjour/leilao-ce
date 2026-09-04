CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: leilaoce.streamlit.app (Streamlit Community Cloud, atualiza no push do main)
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-09-04):
- Scraping: Leilo, Mega, Pacto, MGL, Montenegro, Construbem, Daniel Garcia,
  MJ Leilões, Celso Cunha, HastaPública, Receita Federal (SLE) e Francisco
  Freitas Leilões implementados. Francisco Freitas adicionada em 2026-09-04
  (_raspar_francisco_freitas): leiloeiro forte no Nordeste, plataforma
  "Norte Nordeste Leilões" (nortenordesteleiloes.com.br == mesmo backend de
  franciscofreitasleiloes.com.br). MAIOR fonte já integrada: 91 lotes CE
  ativos na investigação (12 veículos, 60 imóveis, ~9 equipamentos), 77
  mantidos após filtro de categoria. API JSON com campos estruturados
  (nm_estado/nm_cidade prontos, sem regex de endereço) e lance real
  (vl_lance) quando já tem gente lançando — melhor qualidade de dado das
  fontes novas. O parâmetro estado= do endpoint get-leiloes NÃO filtra de
  verdade (testado, sempre retorna os mesmos 75 leilões) — o filtro CE é
  feito lote a lote via get-lotes. Site do leiloeiro está em migração
  ("MUDANÇA DE SITE"), front-end quebrado, mas a API funciona normal; URL
  do lote usa o padrão legado /leilao/index/leilao_id/X/lote/Y (pode não
  renderizar até a migração terminar). NÃO confundir com o "Freitas
  Leiloeiro" de Santo André/SP (mesmo sobrenome, leiloeiro diferente,
  investigado e descartado — só 1 imóvel no CE, ainda em loteamento). Nota:
  robots.txt do site desautoriza nominalmente crawlers de IA (ClaudeBot
  incluso, bloco padrão Cloudflare "AI Bots"); User-agent:* é Allow:/ e o
  scraper não se identifica como nenhum bot de IA (mesmo UA de navegador
  das outras fontes) — registrado por transparência. Ver
  FRANCISCO_FREITAS_ADICIONADO.md. Receita Federal adicionada em 2026-09-03
  (_raspar_receita_sle): leilão de
  mercadoria apreendida, API JSON pública em www25.receita.fazenda.gov.br
  (.gov, sem Cloudflare/sessão, confirmado com curl cru). A DRF Fortaleza
  (edital "317900") cobre CE+PI+MA, então o filtro CE é por LOTE (exige
  "Cidade/CE" na descrição de cada lote, nunca confia no campo "cidade" do
  edital) — testado com dados reais: de 10 lotes de veículo/máquina num
  edital de 411 lotes, só 5 eram de fato Fortaleza/CE (os outros eram
  São Luís/MA e Teresina/PI). Modelo de proposta fechada (sem lance ao
  vivo) — lance_atual = valor mínimo. Só entram lotes tipo veículo/máquina
  pesada; ~93% do edital é eletrônico (celular, TV) e fica de fora por
  categoria não se encaixar no produto. Ver RECEITA_SLE_ADICIONADO.md.
  HastaPública adicionada em 2026-09-03 (_raspar_hastapublica): plataforma nacional que
  detém o contrato dos leilões judiciais do TJ-CE via o leiloeiro Silvio
  Cesar Maraschi (JUCEC 020); os lotes do CE ficam no "grupo 11"
  (/grupos/11). Site renderizado no servidor, SEM Cloudflare — requests
  direto, mesma faixa do MJ/Celso Cunha. Testado com dados reais (4 leilões,
  imóveis + 1 máquina). Nasar Leilões (Fortaleza, muito imóvel no CE) foi
  visto na mesma investigação mas está atrás de Cloudflare — fica no radar
  se houver proxy. Ver HASTAPUBLICA_ADICIONADO.md. MGL reescrito em 2026-09-02 para
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
  2.116.0 instalado via scoop (bucket main). DEPLOY FEITO em 2026-09-03
  (supabase functions deploy stripe-webhook, projeto tybfusbovbihrkmcncux,
  via API sem Docker) — o fallback que grava phone/name ja esta no ar.
- Migration das colunas de cobrança: criada
  supabase/migrations/20260903000000_billing_columns.sql (idempotente) com
  subscription_status, stripe_customer_id, stripe_subscription_id,
  subscription_current_period_end, updated_at, billing_exempt, índices e a
  tabela billing_webhook_events. APLICADA em 2026-09-03 pelo dono via SQL
  Editor. (Nao esta no historico do CLI; se algum dia rodar "supabase db
  push" ele vai reaplicar essa + a 20260826000000 — as duas sao idempotentes.)

BACKLOG:
- Achar outro leiloeiro/fonte que de fato opere no CE: FEITO — HastaPública
  (grupo TJ-CE), Receita Federal (SLE, edital Fortaleza) e Francisco Freitas
  Leilões (91 lotes CE, maior fonte) implementadas. Ver STATUS,
  HASTAPUBLICA_ADICIONADO.md, RECEITA_SLE_ADICIONADO.md e
  FRANCISCO_FREITAS_ADICIONADO.md. Candidatos avaliados e descartados por
  ora: Nasar Leilões (Fortaleza, muito imóvel no CE, mas precisa de proxy —
  Cloudflare), Lopes Leilões (site sem Cloudflare mas dormente, zero lotes),
  Copart (login obrigatório + anti-bot agressivo), VIP Leilões (venda
  direta, não leilão), freitasleiloeiro.com.br de Santo André/SP (não
  confundir com o Francisco Freitas — quase zero CE).
- MGL: rotear /apiplugin/GetBusca e as páginas de lote pelo Zenrows/ScraperAPI
  (padrão de _raspar_soleon) — é a única saída, o IP do runner é bloqueado.
  Depende de recarregar crédito Zenrows/ScraperAPI.
- Recarregar crédito Zenrows/ScraperAPI (destrava MGL + Construbem +
  Daniel Garcia de uma vez) e crédito Anthropic (destrava a análise de IA).
- stripe-webhook: endurecimento do fallback (phone/name), migration das
  colunas de cobrança, deploy da Edge Function e aplicação da migration
  CONCLUÍDOS em 2026-09-03 (ver STATUS). Nada pendente aqui.
- dashboard.py: CSS de sidebar consolidado (painel em "SIDEBAR (bloco
  unico)"; moldura header/toolbar/colapso em "HEADER/TOOLBAR E BOTÃO DE
  COLAPSO DA SIDEBAR (bloco unico)"). Sem duplicatas pendentes.

CONVENÇÕES:
- Mensagens em português, código em inglês (variáveis, funções)
- Sem emojis dentro de código Python, apenas no UI do Streamlit
- Antes de mudanças grandes, sempre apresente um plano para eu aprovar
- Não rode "git push" sem me perguntar primeiro
