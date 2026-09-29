CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: Achadin Leiloes em producao numa VPS Hostinger (plano KVM 1, 1 vCPU/4GB RAM, ~R$ 28/mes), endereco `achadinleiloes.tech` (IP `2.25.223.119`, dominio proprio; DNS e HTTPS verificados em 2026-09-29, TLS via Let's Encrypt/Certbot; antes usava `2-25-223-119.sslip.io`), autodeploy via GitHub Actions SSH no push do main (`.github/workflows/deploy.yml`). Migracao concluida em 2026-09-15 (testada ponta a ponta: cadastro, login, paywall, Stripe Checkout, favoritar). Migracao do Render abandonada antes de ir ao ar (nunca chegou a subir o servico) — trocado pela VPS por decisao do dono em 2026-09-14. Streamlit Community Cloud (leilaoce.streamlit.app) ainda no ar como rollback rapido — desligar so apos alguns dias validando a VPS em uso real. Site na VPS roda com chaves Stripe de TESTE (sk_test_/pk_test_) — trocar para live antes de cobrar de verdade (acesso a conta Stripe travado em 2FA por app autenticador sem posse confirmada; resolver isso antes da troca). Ver docs/contexto/setup/SETUP_HOSTINGER_VPS.md e o bullet "Migracao de deploy para a VPS Hostinger" no STATUS.
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em docs/contexto/setup/SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-09-25; podado em 2026-09-28 — detalhe completo de
cada item foi movido pros docs de contexto linkados, ver
[ORGANIZACAO_PROJETO_2026-09-28.md](docs/contexto/ORGANIZACAO_PROJETO_2026-09-28.md)):
- MJ Leiloes corrigido (2026-09-25): lote saia 2x (URL com/sem `#lances`) e
  titulo/categoria quebravam pra veiculos pesados. 16 lotes unicos, 0 sem
  marca/modelo. Testes: 189/189. Ver
  docs/contexto/fontes/incidentes/MJ_LEILOES_DUPLICADO_2026-09.md.
- Leilo corrigido + dedup com o Pacto (2026-09-25): site refeito (mesmo
  redesign do Pacto); parser reescrito pra ler o JSON embutido da pagina.
  Pacto e Leilo sao a MESMA plataforma — dedup por uuid entre os dois, Pacto
  como canonico. Testes: 169/169. Pendencia: favoritos por uuid
  (`favorites._normalizar_url` compara URL inteira). Ver
  docs/contexto/fontes/incidentes/LEILO_REDESIGN_2026-09.md.
- Receita SLE corrigida (2026-09-24): 0 lotes desde 21/09 era o filtro de
  situacao do edital desatualizado (so aceitava `situacao 2`, precisava
  tambem `3`). 287 lotes CE restaurados. Testes: 136/136. Ver
  docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md.
- Grupo Lance corrigido (2026-09-24): site reestruturou URLs de
  listagem/lote e o filtro de categoria descartava tudo em silencio;
  corrigido + observabilidade nova (200 sem cards vira falha logada). 9
  lotes CE, 127/127 testes. Pendente: confirmar no proximo run do Actions.
  Ver docs/contexto/fontes/ativas/GRUPO_LANCE_ADICIONADO.md.
- Pacto migrado para requests (2026-09-25): `_raspar_pacto` reescrita sem
  Playwright, reaproveitando o parser da plataforma Leilo (JSON
  `elastic.lotes`). 176/176 testes; validado 69 lotes ao vivo. Pendencia:
  favoritos por uuid. Ver
  docs/contexto/fontes/incidentes/PACTO_REGRESSAO_2026-09.md.
- Regressao do Pacto corrigida (2026-09-24): site refeito quebrou lance,
  foto, marca e FIPE desde 21/09; `_raspar_pacto` reescrita com funcoes
  puras, 120/120 testes. Atencao: URL do lote mudou pra `/lote/<uuid>/`
  (favoritos antigos de lote Pacto nao casam mais). Ver
  docs/contexto/fontes/incidentes/PACTO_REGRESSAO_2026-09.md.
- Health check de campos zerados em massa (2026-09-24): `scraper_health.py`
  passou a vigiar tambem `lance_atual>0` e `foto` por fonte, nao so a
  contagem de lotes — a regressao do Pacto acima passou batida por dias
  porque so a contagem era checada. Ver docs/contexto/SCRAPER_HEALTH.md.
- Bug de foto faltando no Pacto corrigido (2026-09-18): investigacao
  confirmou que so o Pacto tinha bug real (foto carregada de forma
  assincrona no site, lida cedo demais pelo scraper); corrigido com
  wait_for_load_state + retry. Demais fontes sem foto batiam com ausencia
  real no site original. Ver
  docs/contexto/fontes/incidentes/PACTO_FOTO_ASSINCRONA_2026-09-18.md.
- Pereira Leiloes adicionada como fonte (2026-09-18): reaproveita
  `_raspar_soleon` (mesmo backend do Construbem/Daniel Garcia), sem bloqueio
  de Cloudflare no IP do Actions. Leiloeiro cearense de bens publicos,
  leiloes esporadicos (`FONTES_ESPERADAS_ZERO`). Ver
  docs/contexto/fontes/ativas/PEREIRA_LEILOES_ADICIONADO.md.
- Dedup entre fontes implementado (2026-09-16):
  `_remover_duplicatas_entre_fontes` remove lote repetido entre agregador e
  leiloeiro direto quando ha identificador de alta confianca (CNJ/matricula)
  no texto — sem heuristica de titulo/endereco. 99/99 testes. Ver
  docs/contexto/fontes/incidentes/DEDUP_ENTRE_FONTES.md.
- Spy Leiloes adicionada como fonte (2026-09-16): agregador nacional de
  imoveis, 604 imoveis CE confirmados. Ver
  docs/contexto/fontes/ativas/SPY_LEILOES_ADICIONADO.md.
- Maria Fixer Leiloes adicionada como fonte (2026-09-16): mesma plataforma
  "vlance" do Francisco Freitas, 77 lotes CE. Ver
  docs/contexto/fontes/ativas/MARIA_FIXER_ADICIONADO.md.
- Bug critico no Leilo corrigido (2026-09-16): categoria errada e vazamento
  de lotes de OUTROS ESTADOS rotulados como CE; parser reescrito com
  validacao de UF por lote. Ver
  docs/contexto/fontes/incidentes/LEILO_REESCRITO_2026-09.md.
- Grupo Lance adicionada como fonte (2026-09-15): 9 lotes de imovel
  confirmados no CE, requests direto (sem Cloudflare). Ver
  docs/contexto/fontes/ativas/GRUPO_LANCE_ADICIONADO.md.
- Testes: tests/test_scraper.py cobre as funcoes puras de scraper.py
  (pytest, ~0,4s). conftest.py stuba Playwright/anthropic/dotenv pra import
  nao exigir browser nem ANTHROPIC_API_KEY. CI (.github/workflows/tests.yml)
  roda em push/PR; scraper.yml roda pytest como gate antes de raspar. Rodar
  local: `python -m pytest -q`. teste_alerta.py e script manual separado
  (dispara WhatsApp real, nao e parte da suite).
- Scraping: Leilo, Mega, Pacto, MGL, Montenegro, Construbem, Daniel Garcia,
  MJ Leiloes, Receita Federal (SLE) e Francisco Freitas Leiloes
  implementados. Celso Cunha DORMENTE (ver abaixo). HastaPublica removida
  (2026-09-11, decisao do dono).
- Celso Cunha DORMENTE (2026-09-08): site reconstruido, sem leilao ativo
  desde 28/08. Ver docs/contexto/fontes/pausadas/CELSO_CUNHA_DORMENTE.md.
- Health check do scraper (2026-09-08): scraper_health.py mantem placar por
  fonte; 3 runs seguidos com 0 lote numa fonte de FONTES_ATIVAS aciona
  WhatsApp pro dono. Ver docs/contexto/SCRAPER_HEALTH.md.
- Higiene (2026-09-08): debug.py removido; PLANO-DO-PROJETO.md atualizado.
  Decisoes FORA DE ESCOPO: relatorios/exportacao, notificacao de lote novo
  por filtro salvo, migrar WhatsApp p/ Cloud API oficial da Meta.
- Migracao de deploy para a VPS Hostinger CONCLUIDA (2026-09-15): detalhe e
  pendencias atuais no bullet "Deploy" da secao CONTEXTO DO PROJETO acima.
  Checklist completo em docs/contexto/setup/DEPLOY_CHECKLIST.md e guia em
  docs/contexto/setup/SETUP_HOSTINGER_VPS.md.
- Eletronicos (2026-09-08): Receita SLE tambem traz eletronicos (categoria
  `eletronicos`, icone 📱) — decisao do dono de trazer tudo, sem piso de
  valor. Ver docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md, secao
  "Eletronicos".
- Francisco Freitas adicionada (2026-09-04): maior fonte ja integrada (77
  lotes CE mantidos apos filtro), API JSON com dado estruturado. Receita
  Federal adicionada (2026-09-03): leilao de mercadoria apreendida, filtro
  CE por lote. MGL reescrito (2026-09-02, API JSON) mas bloqueado por
  Cloudflare no IP do Actions ate ser destravado via Zenrows Scraping
  Browser em 2026-09-04 — ainda nao validado em run real do Actions. Sodre
  Santoro descartado (2026-08-31, sem estoque no CE). Ver
  docs/contexto/fontes/ativas/FRANCISCO_FREITAS_ADICIONADO.md,
  docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md,
  docs/contexto/fontes/pausadas/MGL_SCRAPER_PENDENTE.md e
  docs/contexto/fontes/pausadas/SODRE_SANTORO_DESCARTADO.md.
- IA (Anthropic): creditos esgotados nos runs de 2026-09-02 — circuit
  breaker desliga a analise e usa fallback "Nao informado" em todos os
  lotes.
- Favoritos: pronto, sincronizando com Supabase (upsert por
  user_id,lote_url).
- Log de falha de WhatsApp (2026-09-08): falha de envio agora e gravada na
  tabela `whatsapp_send_log` (antes era engolida silenciosamente). Ver
  docs/contexto/WHATSAPP_SEND_LOG.md.
- Backup do Postgres (2026-09-09): pg_dump diario via GitHub Actions
  (Supabase Free nao tem backup nativo). Pendente: configurar secret
  `SUPABASE_DB_URL`, testar 1 restauracao. Ver
  docs/contexto/setup/SETUP_BACKUP_DB.md.
- Cadastro/login: pronto, Supabase Auth (fluxo PKCE) + trigger
  handle_new_user.
- Planos pagos (Stripe): enforcement ligado — dashboard.py bloqueia quem
  nao tem assinatura ativa. Portal de cobranca e webhook funcionando.
- stripe-webhook + migration de colunas de cobranca (2026-09-03): fallback
  de emergencia do updateProfile (puxa phone/name de auth.users) e colunas
  de cobranca (subscription_status etc.) deployados e aplicados. Ver
  docs/contexto/STRIPE_WEBHOOK_FALLBACK.md.

BACKLOG:
- PENDENTE (registrado 2026-09-29): conferir a migracao para `achadinleiloes.tech`
  fora do repo — `APP_URL` no `.env` da VPS, Site URL/Redirect URLs no Supabase
  Auth e URL do webhook no Stripe. DNS e HTTPS ja verificados. Checklist na
  secao G de docs/contexto/setup/DEPLOY_CHECKLIST.md.
- Nova rodada de investigação de fontes (2026-09-14): Grupo Lance FEITO
  (2026-09-15, ver STATUS e docs/contexto/fontes/ativas/GRUPO_LANCE_ADICIONADO.md).
  Restam para implementar, por prioridade: Spy Leilões (agregador, 195
  lotes em Fortaleza, exige dedup entre fontes), Nasar Leilões (leiloeiro
  próprio de Fortaleza, reaproveitar Zenrows do MGL para driblar
  Cloudflare). Leilão Imóvel (agregador) fica de reserva, menor prioridade.
  Descartados: cearaleiloes.com.br (= Francisco Freitas), Silvio Cesar
  Maraschi (= HastaPública, já removida), Alfa/Italo/Átrio Leilões (sem
  volume CE confirmado ou risco reputacional). Ver
  docs/contexto/INVESTIGACAO_NOVAS_FONTES_2026-09-14.md.
- Achar outro leiloeiro/fonte que de fato opere no CE: FEITO — Receita
  Federal (SLE, edital Fortaleza) e Francisco Freitas
  Leilões (91 lotes CE, maior fonte) implementadas. Ver STATUS,
  docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md e
  docs/contexto/fontes/ativas/FRANCISCO_FREITAS_ADICIONADO.md. Candidatos avaliados e descartados por
  ora: Nasar Leilões (Fortaleza, muito imóvel no CE, mas precisa de proxy —
  Cloudflare), Lopes Leilões (site sem Cloudflare mas dormente, zero lotes),
  Copart (login obrigatório + anti-bot agressivo), VIP Leilões (venda
  direta, não leilão), freitasleiloeiro.com.br de Santo André/SP (não
  confundir com o Francisco Freitas — quase zero CE).
- MGL: FEITO (2026-09-04) — `_raspar_mgl` roteado pela Zenrows Scraping
  Browser (`connect_over_cdp`), não pelo padrão de proxy de URL do
  _raspar_soleon (esse não bastava pro MGL, que precisa da navegação
  inteira passando pelo proxy, não só o fetch). Falta validar num run real
  do GitHub Actions. Ver STATUS e docs/contexto/fontes/pausadas/MGL_SCRAPER_PENDENTE.md.
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
