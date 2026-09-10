CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: leilao-ce.onrender.com (Render, Web Service plano Starter US$ 7/mes, autodeploy no push do main). Migracao do Streamlit Community Cloud (leilaoce.streamlit.app) em andamento — ver SETUP_RENDER.md e o bullet "Migracao de deploy para o Render" no STATUS.
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-09-08):
- Testes: adicionado tests/test_scraper.py em 2026-09-08 (46 casos, pytest,
  ~0,4s) cobrindo as funcoes puras de scraper.py: classificar,
  oportunidade_preco, _score_modelo, _parse_brl, _extrair_lance, _extrair_km,
  buscar_referencia_mercado, detectar_categoria. conftest.py na raiz faz stub
  de Playwright/anthropic/dotenv (setdefault em sys.modules) para o import de
  scraper nao exigir browser nem ANTHROPIC_API_KEY. Deps de teste em
  requirements-dev.txt (so pytest + requests; as libs pesadas ficam de fora
  por causa do stub). CI: .github/workflows/tests.yml roda em push/PR;
  scraper.yml roda "python -m pytest -q" como gate antes de raspar (falha
  rapido sem gastar os ~30min de scraping se um parser quebrou). Rodar local:
  python -m pytest -q. teste_alerta.py continua sendo script manual separado
  (dispara WhatsApp real, nao e parte da suite).
- Scraping: Leilo, Mega, Pacto, MGL, Montenegro, Construbem, Daniel Garcia,
  MJ Leilões, HastaPública, Receita Federal (SLE) e Francisco
  Freitas Leilões implementados. Celso Cunha DORMENTE (ver abaixo).
- Celso Cunha DORMENTE (2026-09-08): rendeu 119 lotes/run ate 26/08, 0 desde
  28/08. O site foi reconstruido — o esquema server-rendered
  /leilao/<id>/<slug> que `_raspar_celso_cunha` raspava sumiu (404), os lotes
  agora vem por AJAX (web/buscarLotes.php etc.) e nao ha leilao ativo
  (/agenda-de-leiloes so tem editais de 2019 "EM BREVE"). Chamada comentada em
  `raspar_leiloes()`; funcao e helpers mantidos como base. Reescrever estilo
  MGL (sessao propria) quando o site voltar a ter leilao. Ver
  CELSO_CUNHA_DORMENTE.md.
- Health check do scraper (2026-09-08): novo `scraper_health.py`, chamado no
  fim de `raspar_leiloes()` (best-effort, nunca derruba o run). Mantem um
  placar por fonte em `scraper_health.json` (commitado junto do leiloes.json,
  runner e efemero). Quando uma fonte de `FONTES_ATIVAS` (leilo/mega/pacto/
  montenegro/mj/hastapublica/receita_sle/francisco_freitas) fica 3 runs
  seguidos com 0 lote, loga `::warning::` e manda 1 WhatsApp pro dono via
  `alertas.send_whatsapp(origem="scraper_health")`; re-alerta a cada ~14 runs
  enquanto seguir zerada; zera ao voltar. `FONTES_ESPERADAS_ZERO`
  (mgl/construbem/danielgarcia/celsocunha) sao rastreadas mas nunca alertam —
  tirar de la quando uma voltar. Secret novo `OWNER_WHATSAPP` no passo "Rodar
  scraper" do workflow (ausente = so `::warning::`, sem WhatsApp). NAO falha o
  job de proposito. Testes: `tests/test_scraper_health.py` (10 casos).
- Higiene (2026-09-08): `debug.py` removido (script solto de dev, nao importado).
  `PLANO-DO-PROJETO.md` atualizado (snapshot, secoes 1/3/5/7/9/10/11/12/13/14).
  Decisoes do dono registradas como FORA DE ESCOPO: relatorios/exportacao,
  notificacao de lote novo por filtro salvo, migrar WhatsApp p/ Cloud API oficial
  da Meta. Mantido: `leiloes.json` versionado no git. Pendencias novas
  (nao-bloqueantes) no backlog do PLANO: retencao do `whatsapp_send_log`,
  confirmar tier de backup do Supabase, observar Construbem (rendeu 7 lotes em 1
  run 08/09 — se firmar, tirar de `FONTES_ESPERADAS_ZERO`).
- Migracao de deploy para o Render EM ANDAMENTO: blueprint `render.yaml`
  (Web Service, plano Starter US$ 7/mes), `requirements-web.txt`,
  `SETUP_RENDER.md`. Falta subir o servico e apontar a URL de producao.
  Passo a passo completo do que ainda falta (Render + Evolution API + backup +
  IA + desligar o Community Cloud) em `DEPLOY_CHECKLIST.md`. Quando concluir,
  revisar a linha "Deploy" no topo deste arquivo e as secoes 1/7/13 do
  PLANO-DO-PROJETO.md.
- Eletrônicos: em 2026-09-08 `_raspar_receita_sle` passou a trazer TAMBEM os
  lotes de eletronico da Receita (celular, audio/video, informatica,
  videogame) numa categoria nova `eletronicos` (icone 📱). Decisao do dono:
  trazer tudo, sem piso de valor, sem selo de "vedada a comercializacao".
  Filtro de tipo ganhou 2o balde (`_RF_TIPO_ELETRONICO_RE`); filtro CE do
  eletronico e pelo `recintoArmazenador` (`_rf_eletronico_ce` — descarta so se
  tiver marcador de Sao Luis/MA ou Teresina/PI; sem marcador = CE, pois o
  edital e da DRF Fortaleza), diferente do veiculo que exige `/CE` no texto.
  Referencia de preco = `valorAvaliacao` da RFB (lido do listaLotes/resumo;
  no detalhe vem null) no lugar da FIPE. Parser proprio `_rf_parse_eletronico`
  (marca/modelo do 1o item, sufixo "(+N itens)"). `analisar()` ramifica por
  categoria e usa prompt de eletronico (estados LACRADO/USADO/DEFEITO/
  NAO_INFORMADO; selos 📦/🔧/🔴/⚪). `DEFEITO` entrou na lista de estados que
  forcam INSPECIONAR em classificar/oportunidade_preco/orientacao_uso.
  Dashboard: pill_estado + filtro "Estado" reconhecem os selos novos; card
  omite `📅 ano` quando ano==0. Testado com 60 lotes reais do edital
  0317900/000003/2026 (60/60 montados, com valorAvaliacao). Um edital de
  exemplo pula de ~10 candidatos para ~396 (+2-3 min no run). IA em fallback
  (credito Anthropic zerado), entao todo eletronico sai como NAO_INFORMADO
  ate recarregar. Ver RECEITA_SLE_ADICIONADO.md, secao "Eletronicos".
- Francisco Freitas adicionada em 2026-09-04
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
  vivo) — lance_atual = valor mínimo. Desde 2026-09-08 entram lotes de
  veículo/máquina pesada E de eletrônico (~93% do edital) na categoria
  `eletronicos` — ver o bullet "Eletrônicos" acima e a seção "Eletrônicos"
  do RECEITA_SLE_ADICIONADO.md. Ficam de fora só têxtil/mineral/químico/
  bazar/utensílio. Ver RECEITA_SLE_ADICIONADO.md.
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
  sem estoque no CE (ver SODRE_SANTORO_DESCARTADO.md). MGL destravado em
  2026-09-04: `_raspar_mgl` agora abre sua própria sessão via Zenrows
  Scraping Browser (`p.chromium.connect_over_cdp("wss://browser.zenrows.com?apikey=...")`,
  reaproveita `ZENROWS_API_KEY`) em vez do Chromium local — o Cloudflare
  bloqueava a navegação inteira (SPA não inicializava) a partir do IP do
  GitHub Actions, não só o fetch, por isso o proxy simples de URL do
  Construbem não servia aqui. Sem fallback ScraperAPI (não tem produto de
  navegador remoto via CDP, só HTTP stateless com `render=true` — reescrever
  pra isso não compensa pro volume/prioridade do MGL). Se `ZENROWS_API_KEY`
  faltar ou a conexão falhar, faz bail limpo (mensagem clara, sem travar o
  resto do scraper). Ainda não testado num run real do GitHub Actions — ver
  MGL_SCRAPER_PENDENTE.md.
- IA (Anthropic): créditos esgotados nos runs de 2026-09-02 — circuit breaker
  desliga a análise e usa fallback "Não informado" em todos os lotes.
- Favoritos: pronto, sincronizando com Supabase (upsert por user_id,lote_url).
- Log de falha de WhatsApp (2026-09-08): antes o erro de envio era engolido
  (`favorites._whatsapp_favorito` com `except: pass`; `alertas.send_whatsapp`
  so `print` no stdout efemero). Agora as duas rotas gravam a FALHA na tabela
  `public.whatsapp_send_log` via o novo modulo `whatsapp_log.registrar_falha`
  (nunca levanta — se o insert falhar cai num print). `favorites.py` insere
  com o JWT do usuario (RLS: policy de insert `user_id = auth.uid()`);
  `alertas.py` insere com service role (ignora RLS). Colunas: origem
  (`favorito`|`alerta_lance`|`teste`), telefone, lote_url, erro, http_status,
  corpo. Migration `supabase/migrations/20260908000000_whatsapp_send_log.sql`
  (idempotente) — APLICADA no Supabase (dono confirmou 2026-09-09, tabela
  `whatsapp_send_log` existe). Testes:
  `tests/test_whatsapp_log.py` (5 casos, sb falso). So entram linhas de
  falha; o dono consulta pelo painel do Supabase.
- Backup do Postgres (2026-09-09): plano do Supabase e Free (sem backup
  nativo). Novo `.github/workflows/backup-db.yml` roda `pg_dump` (schemas
  `public` + `auth`, via container `postgres:17-alpine`) 1x/dia as 08:00 UTC
  e sob demanda; dump sai gzipado como artifact do Actions com retencao de
  90 dias. Secret novo `SUPABASE_DB_URL` = connection string do Session
  pooler (porta 5432; o Transaction pooler nao serve pra pg_dump). Job falha
  alto se o secret faltar ou o dump vier vazio. PENDENTE: configurar o
  secret, testar 1 restauracao, e decidir copia off-site mensal (o artifact
  expira em 90 dias). Ver SETUP_BACKUP_DB.md.
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
- MGL: FEITO (2026-09-04) — `_raspar_mgl` roteado pela Zenrows Scraping
  Browser (`connect_over_cdp`), não pelo padrão de proxy de URL do
  _raspar_soleon (esse não bastava pro MGL, que precisa da navegação
  inteira passando pelo proxy, não só o fetch). Falta validar num run real
  do GitHub Actions. Ver STATUS e MGL_SCRAPER_PENDENTE.md.
- Recarregar crédito Anthropic (destrava a análise de IA). Zenrows/ScraperAPI
  já em uso nos planos de entrada (dono do projeto confirmou em 2026-09-04
  que preço não é uma preocupação aqui).
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

## Agent skills

### Issue tracker

Issues rastreadas como GitHub Issues (mounjour/leilao-ce, via CLI `gh`). Ver `docs/agents/issue-tracker.md`.

### Triage labels

Labels padrão (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). Ver `docs/agents/triage-labels.md`.

### Domain docs

Layout single-context (CONTEXT.md + docs/adr/ na raiz). Ver `docs/agents/domain.md`.
