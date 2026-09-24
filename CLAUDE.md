CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: Achadin Leiloes em producao numa VPS Hostinger (plano KVM 1, 1 vCPU/4GB RAM, ~R$ 28/mes), endereco `2-25-223-119.sslip.io` (IP `2.25.223.119`, sem dominio proprio ainda, TLS via Let's Encrypt/Certbot), autodeploy via GitHub Actions SSH no push do main (`.github/workflows/deploy.yml`). Migracao concluida em 2026-09-15 (testada ponta a ponta: cadastro, login, paywall, Stripe Checkout, favoritar). Migracao do Render abandonada antes de ir ao ar (nunca chegou a subir o servico) — trocado pela VPS por decisao do dono em 2026-09-14. Streamlit Community Cloud (leilaoce.streamlit.app) ainda no ar como rollback rapido — desligar so apos alguns dias validando a VPS em uso real. Site na VPS roda com chaves Stripe de TESTE (sk_test_/pk_test_) — trocar para live antes de cobrar de verdade (acesso a conta Stripe travado em 2FA por app autenticador sem posse confirmada; resolver isso antes da troca). Ver docs/contexto/SETUP_HOSTINGER_VPS.md e o bullet "Migracao de deploy para a VPS Hostinger" no STATUS.
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em docs/contexto/SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-09-24):
- Regressao do Pacto corrigida (2026-09-24): desde o run de 21/09 os lotes
  vinham com lance 0, foto vazia, marca = nome do leilao e FIPE zerada. Causa
  raiz: o site foi refeito (nao so um segmento novo na URL) -- listagem agora em
  /leilao/ceara/{categoria}/, card `a.lote-card-link` com href /lote/<uuid>/,
  lance em `.valor-card` SEM centavos (o regex de _extrair_lance exige ',dd'),
  foto em <img> (nao mais background-image) e nome pronto "Marca/Modelo".
  `_raspar_pacto` reescrita com funcoes puras (`_pacto_parse_href/valor/ano/
  data/card`), 20 testes novos (120/120). Validado ao vivo: 37/37 lotes com
  lance, ano e data; 32 com foto real; 28 com FIPE. Atencao: a URL do lote
  mudou para /lote/<uuid>/ (favoritos de lotes Pacto antigos deixam de casar) e
  a cidade e fixa "Eusebio/CE" (card so mostra "CE"). Substitui o retry de foto
  do bullet de 2026-09-18 no seletor, mas o retry foi mantido. Pendencia (outra
  sessao): health check de campos-chave zerados em massa. Ver
  docs/contexto/PACTO_REGRESSAO_2026-09.md.
- Bug de foto faltando no Pacto corrigido (2026-09-18): investigacao pedida
  pelo dono (lotes sem imagem no projeto mas com imagem no site original)
  varreu leiloes.json inteiro (1011 lotes) e checou ao vivo contra o site de
  cada fonte com lote sem `foto`. receita_sle (282/287), spy_leiloes
  (87/594), francisco_freitas (17/37), mega (1/22) e maria_fixer (1/2)
  bateram com ausencia real de foto no site original (confirmado via API/
  DOM ao vivo) — nao sao bug. So o Pacto (6/19) tinha bug de verdade:
  confirmado ao vivo que `BAJAJ/DOMINAR NS160` e `CHEVROLET/VECTRA HATCH 4P
  GT` tem foto real no site mas foram salvos com `foto: ""`. Causa raiz: a
  foto do card e' um `background-image` no componente Quasar `q-img`
  (`_raspar_pacto` em scraper.py), setado de forma assincrona/preguicosa
  conforme o card entra na tela — o scraper lia o style uma unica vez logo
  apos o scroll, e alguns cards ainda nao tinham terminado de carregar a
  imagem nesse instante. Corrigido com `pg.wait_for_load_state("networkidle")`
  apos o scroll e um retry (ate 4x, 500ms) que só preenche as fotos que
  ainda faltavam, sem sobrescrever as ja capturadas. Suite de testes
  (100/100) sem regressao — sem teste dedicado pra `_raspar_pacto` por
  depender de Playwright/rede real; validar de fato so no proximo run do
  GitHub Actions. Limitacao a parte, nao corrigida: 2 lotes de
  pesados/agro (trator/plaina) nem aparecem na listagem `/leilao/{cidade}-
  ceara` mesmo com scroll bem mais agressivo — sugere que o Pacto tem
  multiplos "leiloes" concorrentes por cidade e a listagem agregada nem
  sempre traz todos os lotes/categorias; fica como pendencia de cobertura,
  nao de foto.
- Pereira Leilões adicionada como fonte (2026-09-18): reaproveita
  `_raspar_soleon` em scraper.py (mesmo backend "Soleon" do Construbem/Daniel
  Garcia, confirmado pelo `<meta name="author" content="SOLEON...">` e pelas
  URLs `/leilao/{id}/lotes` e `/item/{id}/detalhes` iguais) em vez de um
  parser dedicado — evita duplicar a logica de categorizacao/extracao ja em
  producao. `_raspar_soleon` ganhou o parametro `usar_proxy` (default True);
  Pereira roda com `usar_proxy=False` porque, diferente de Construbem/Daniel
  Garcia, o site nao esta atras de bloqueio de Cloudflare no IP do GitHub
  Actions (requests direto responde 200 normalmente). Leiloeiro cearense
  focado em bens de orgaos publicos (prefeituras municipais, UFC) — 17 lotes
  confirmados num leilao ativo no teste (12 veiculos + 5 diversos, incl.
  retroescavadeiras). Bug pego na validacao: titulo do site tem o typo
  "RETROECAVADEIRA" (sem o "s" de escavadeira), que nao batia com a
  palavra-chave `retroescavadeira` em PALAVRAS_MAQUINA — corrigido
  adicionando a variante com erro de digitacao, com teste novo em
  tests/test_scraper.py. `pereira` entrou em `FONTES_ESPERADAS_ZERO` (nao em
  FONTES_ATIVAS) no scraper_health.py — leiloeiro unico com leiloes
  esporadicos (semanas/meses de intervalo pelo historico de encerrados), 0
  lote por varios runs entre leiloes e esperado, nao fonte quebrada. Ver
  docs/contexto/PEREIRA_LEILOES_ADICIONADO.md.
- Dedup entre fontes implementado (2026-09-16): `_remover_duplicatas_entre_fontes`
  em scraper.py, rodando no fim de raspar_leiloes() antes de salvar
  leiloes.json. Resolve a pendencia da investigacao de 2026-09-14 (agregadores
  como Spy Leiloes/Grupo Lance podem repetir imovel ja raspado direto de
  Francisco Freitas/Maria Fixer com URL diferente). So remove quando acha um
  identificador de alta confianca no texto do lote (numero de processo CNJ ou
  matricula do imovel via `_chave_dedup_entre_fontes`) — sem isso, NAO tenta
  merge por heuristica de titulo/endereco (risco de falso positivo esconder
  oportunidade real e considerado pior que mostrar duplicata). Mantem a 1a
  ocorrencia (leiloeiro direto roda antes dos agregadores no pipeline). Health
  check (scraper_health.processar) usa a contagem ANTES do dedup, pra nao
  confundir "fonte quebrada" com "lotes mesclados". Testes:
  TestChaveDedupEntreFontes e TestRemoverDuplicatasEntreFontes em
  tests/test_scraper.py (9 casos novos, 99/99 no total). Ver
  docs/contexto/DEDUP_ENTRE_FONTES.md.
- Spy Leiloes adicionada como fonte (2026-09-16): `_raspar_spy_leiloes` em
  scraper.py. Agregador nacional de imoveis (SaaS pago pro usuario final,
  mas a busca em /imoveis-leilao e publica sem login), 604 imoveis
  confirmados no CE num run real (`?estado=CE&page=N`, SSR — requests direto
  sem Playwright nem API JSON separada). Bug pego e corrigido durante a
  validacao: o separador entre data e preco de cada praca no card e um
  bullet "•" (U+2022), nao espaco/nbsp — o regex copiado por analogia de
  outra fonte nao batia e zerava fipe_valor/data_leilao silenciosamente;
  corrigido apos smoke test contra a pagina ao vivo (495/604 lotes com
  referencia de preco depois do fix). Limitacao conhecida (por ser
  agregador, pode duplicar imoveis ja raspados de outras fontes com URL
  diferente) mitigada no mesmo dia — ver bullet "Dedup entre fontes"
  abaixo. `spy_leiloes` entrou em FONTES_ATIVAS do scraper_health.py. Ver
  docs/contexto/SPY_LEILOES_ADICIONADO.md.
- Maria Fixer Leiloes adicionada como fonte (2026-09-16): `_raspar_maria_fixer`
  em scraper.py, mesma plataforma "vlance" do Francisco Freitas (mesmos
  endpoints get-leiloes/get-lotes e mesmo schema de campos) — reaproveita os
  helpers genericos ja escritos pro Francisco Freitas (_ff_get, _ff_categoria,
  _ff_parse_veiculo, _ff_html_para_texto, _ff_num). 77 lotes CE confirmados
  num teste ao vivo (motos/carro em Farias Brito, 1 imovel em Caucaia) —
  mais que os "16" do contador do site porque sucata judicial reaparece em
  2a/3a rodada de leilao com lance decrescente (cada rodada e um leilao_id
  distinto). `maria_fixer` entrou em FONTES_ATIVAS do scraper_health.py. Sem
  teste novo dedicado (reaproveita helpers puros ja existentes e nao
  testados do Francisco Freitas). Ver docs/contexto/MARIA_FIXER_ADICIONADO.md.
- Bug critico no Leilo corrigido (2026-09-16): dono reportou categoria
  errada (filtro "motos" mostrando caminhao, "caminhoes" mostrando carro) e
  nome de lote com texto estranho ("Leilao-De-Seguradoras-15-09-26 Honda...").
  Causa raiz: o site do Leilo mudou de estrutura — `/leilao/{cidade}-ceara/
  {categoria}` parou de filtrar por categoria (cai num feed nacional sem
  filtro) e a URL do lote ganhou um segmento novo (nome do "leilao"
  nomeado) entre categoria e veiculo, quebrando o parser por indice fixo
  (marca virava o nome do leilao). Achado MAIS GRAVE na investigacao: como
  ninguem validava a UF real do lote, lotes de OUTROS ESTADOS (Taguatinga/
  DF, Cuiaba/MT, Manaus/AM, Aparecida de Goiania/GO...) estavam sendo
  rotulados "/CE" e aparecendo pro usuario como se fossem do Ceara.
  `_raspar_leilo` reescrita: uma unica URL (`/leilao/fortaleza-ceara`, unico
  grupo de busca CE que ainda filtra de verdade), virou "requests direto"
  (site e server-rendered, nao precisa mais de Playwright nem de abrir
  pagina de detalhe por lote — a listagem ja traz tudo), categoria vem do
  segmento da propria URL do lote (nao mais de um valor "pedido"), e todo
  lote so entra se o UF do proprio card for "CE" (rede de seguranca contra
  o vazamento de outro estado se o filtro cair de novo). Cobertura: 36
  lotes/run (sem paginacao disponivel na listagem — testado, nao encontrado
  mecanismo real apesar do badge do site dizer "124 Lotes"). Imoveis/
  equipamentos do Leilo (secao separada do site) ficam fora do escopo, como
  antes. Testes: `TestLeiloParseListagem` em tests/test_scraper.py (HTML
  real + casos sinteticos pro vazamento de outro estado). `leiloes.json`
  commitado so reflete a correcao apos o proximo run do GitHub Actions. Ver
  docs/contexto/LEILO_REESCRITO_2026-09.md.
- Grupo Lance adicionada como fonte (2026-09-15): `_raspar_grupo_lance` em
  scraper.py, "requests direto" (sem Playwright/proxy — site server-rendered
  Yii2/PHP, sem Cloudflare nem outro anti-bot). Filtro CE funciona de
  verdade na própria URL (`/imoveis/ce`, diferente do `?estado=` que é
  ignorado no Francisco Freitas/MGL). 9 lotes de imóvel confirmados no CE
  (Iguatu, Aquiraz, Juazeiro do Norte x2, Maranguape, Fortaleza, Pedra
  Branca, Crato), validados num run real. Veículos/bens industriais/bens de
  consumo do mesmo site ficaram de fora por ora (zerados no CE, formato de
  título de veículo nunca visto com dado real). `grupo_lance` entrou em
  `FONTES_ATIVAS` do scraper_health.py. Testes:
  `TestGrupoLanceCategoria`/`TestGrupoLanceParsePagina` em
  tests/test_scraper.py (HTML real, sem rede). Ver
  docs/contexto/GRUPO_LANCE_ADICIONADO.md.
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
  MJ Leilões, Receita Federal (SLE) e Francisco
  Freitas Leilões implementados. Celso Cunha DORMENTE (ver abaixo).
  HastaPública removida (2026-09-11): decisão do dono, fonte retirada do
  projeto (scraper, testes, `leiloes.json`/`scraper_health.json` e docs).
- Celso Cunha DORMENTE (2026-09-08): rendeu 119 lotes/run ate 26/08, 0 desde
  28/08. O site foi reconstruido — o esquema server-rendered
  /leilao/<id>/<slug> que `_raspar_celso_cunha` raspava sumiu (404), os lotes
  agora vem por AJAX (web/buscarLotes.php etc.) e nao ha leilao ativo
  (/agenda-de-leiloes so tem editais de 2019 "EM BREVE"). Chamada comentada em
  `raspar_leiloes()`; funcao e helpers mantidos como base. Reescrever estilo
  MGL (sessao propria) quando o site voltar a ter leilao. Ver
  docs/contexto/CELSO_CUNHA_DORMENTE.md.
- Health check do scraper (2026-09-08): novo `scraper_health.py`, chamado no
  fim de `raspar_leiloes()` (best-effort, nunca derruba o run). Mantem um
  placar por fonte em `scraper_health.json` (commitado junto do leiloes.json,
  runner e efemero). Quando uma fonte de `FONTES_ATIVAS` (leilo/mega/pacto/
  montenegro/mj/receita_sle/francisco_freitas) fica 3 runs
  seguidos com 0 lote, loga `::warning::` e manda 1 WhatsApp pro dono via
  `alertas.send_whatsapp(origem="scraper_health")`; re-alerta a cada ~14 runs
  enquanto seguir zerada; zera ao voltar. `FONTES_ESPERADAS_ZERO`
  (mgl/construbem/danielgarcia/celsocunha) sao rastreadas mas nunca alertam —
  tirar de la quando uma voltar. Secret novo `OWNER_WHATSAPP` no passo "Rodar
  scraper" do workflow (ausente = so `::warning::`, sem WhatsApp). NAO falha o
  job de proposito. Testes: `tests/test_scraper_health.py` (10 casos).
- Higiene (2026-09-08): `debug.py` removido (script solto de dev, nao importado).
  `docs/contexto/PLANO-DO-PROJETO.md` atualizado (snapshot, secoes 1/3/5/7/9/10/11/12/13/14).
  Decisoes do dono registradas como FORA DE ESCOPO: relatorios/exportacao,
  notificacao de lote novo por filtro salvo, migrar WhatsApp p/ Cloud API oficial
  da Meta. Mantido: `leiloes.json` versionado no git. Pendencias novas
  (nao-bloqueantes) no backlog do PLANO: retencao do `whatsapp_send_log`,
  confirmar tier de backup do Supabase, observar Construbem (rendeu 7 lotes em 1
  run 08/09 — se firmar, tirar de `FONTES_ESPERADAS_ZERO`).
- Migracao de deploy para a VPS Hostinger CONCLUIDA (2026-09-15): a migracao
  anterior para o Render foi abandonada sem nunca subir o servico (decisao do
  dono) e substituida por uma VPS Hostinger (plano **KVM 1**, IP
  `2.25.223.119`, endereco `2-25-223-119.sslip.io`). `render.yaml` e
  `docs/contexto/SETUP_RENDER.md` removidos; guia usado:
  `docs/contexto/SETUP_HOSTINGER_VPS.md` (provisionamento, usuario `leilao`,
  systemd `leilao-ce.service`, Nginx + Certbot — certificado valido ate
  2026-12-14). Deploy automatico via `.github/workflows/deploy.yml` (SSH a
  cada push no main) configurado e testado: chave dedicada
  `~/deploy_leilao_ce` autorizada, sudoers `leilao-ce-deploy` (restart sem
  senha), secrets `VPS_HOST`/`VPS_USER`/`VPS_SSH_KEY` no GitHub Actions.
  Supabase Auth (Site URL + Redirect URLs) apontado para a URL da VPS. Teste
  E2E completo passou: cadastro, confirmacao de e-mail, login, paywall,
  Stripe Checkout (cartao de teste), dashboard com lotes, favoritar.
  `requirements-web.txt` sem mudanca. **Pendente:** (1) site ainda roda com
  chaves Stripe de **TESTE** (`sk_test_`/`pk_test_`) — trocar para `live`
  antes de cobrar de verdade; acesso a conta Stripe esta travado num 2FA por
  app autenticador cuja posse nao foi confirmada, resolver isso antes de
  pegar as chaves live; (2) secrets `SUPABASE_DB_URL` (backup do Postgres) e
  `OWNER_WHATSAPP` (alerta de fonte zerada) ainda nao configurados no GitHub
  Actions; (3) Evolution API (WhatsApp) segue desligada, instancia perdida;
  (4) credito Anthropic zerado; (5) desligar o Streamlit Community Cloud
  (`leilaoce.streamlit.app`) so depois de alguns dias validando a VPS em uso
  real — por ora mantido no ar como rollback rapido. Checklist detalhado em
  `docs/contexto/DEPLOY_CHECKLIST.md`.
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
  ate recarregar. Ver docs/contexto/RECEITA_SLE_ADICIONADO.md, secao "Eletronicos".
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
  docs/contexto/FRANCISCO_FREITAS_ADICIONADO.md. Receita Federal adicionada em 2026-09-03
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
  do docs/contexto/RECEITA_SLE_ADICIONADO.md. Ficam de fora só têxtil/mineral/químico/
  bazar/utensílio. Ver docs/contexto/RECEITA_SLE_ADICIONADO.md.
  Nasar Leilões (Fortaleza, muito imóvel no CE) foi visto em investigação
  mas está atrás de Cloudflare — fica no radar se houver proxy. MGL
  reescrito em 2026-09-02 para
  usar a API JSON (POST /apiplugin/GetBusca com ID_Estado:23, veículos +
  imóveis do CE) — código validado com dados reais, MAS 2 runs manuais
  confirmaram que o Cloudflare bloqueia o site inteiro a partir do IP do
  GitHub Actions (SPA nao inicializa + 403). Parado até ter proxy residencial
  (ver docs/contexto/MGL_SCRAPER_PENDENTE.md). Construbem/Daniel Garcia = mesmo muro;
  Zenrows sem crédito (402) e ScraperAPI com timeout nos runs de 2026-09-02.
  Sodré Santoro investigado em 2026-08-31 e descartado: pátios só em SP/PR,
  sem estoque no CE (ver docs/contexto/SODRE_SANTORO_DESCARTADO.md). MGL destravado em
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
  docs/contexto/MGL_SCRAPER_PENDENTE.md.
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
  expira em 90 dias). Ver docs/contexto/SETUP_BACKUP_DB.md.
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
- Nova rodada de investigação de fontes (2026-09-14): Grupo Lance FEITO
  (2026-09-15, ver STATUS e docs/contexto/GRUPO_LANCE_ADICIONADO.md).
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
  docs/contexto/RECEITA_SLE_ADICIONADO.md e
  docs/contexto/FRANCISCO_FREITAS_ADICIONADO.md. Candidatos avaliados e descartados por
  ora: Nasar Leilões (Fortaleza, muito imóvel no CE, mas precisa de proxy —
  Cloudflare), Lopes Leilões (site sem Cloudflare mas dormente, zero lotes),
  Copart (login obrigatório + anti-bot agressivo), VIP Leilões (venda
  direta, não leilão), freitasleiloeiro.com.br de Santo André/SP (não
  confundir com o Francisco Freitas — quase zero CE).
- MGL: FEITO (2026-09-04) — `_raspar_mgl` roteado pela Zenrows Scraping
  Browser (`connect_over_cdp`), não pelo padrão de proxy de URL do
  _raspar_soleon (esse não bastava pro MGL, que precisa da navegação
  inteira passando pelo proxy, não só o fetch). Falta validar num run real
  do GitHub Actions. Ver STATUS e docs/contexto/MGL_SCRAPER_PENDENTE.md.
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
