# Grupo Lance — adicionada como fonte (2026-09-15)

Primeiro candidato priorizado na investigação de novas fontes de 2026-09-14
(ver docs/contexto/INVESTIGACAO_NOVAS_FONTES_2026-09-14.md). Implementado
como `_raspar_grupo_lance` em `scraper.py`.

## Por que essa fonte

- Empresa: Lance Alienações Virtuais LTDA, CNPJ 23.341.409/0001-77.
- Sites: grupolance.com.br (usado pelo scraper) e lancese.com.br (mesma
  empresa/plataforma).
- Sem indício de golpe/site falso (Reclame Aqui só tem queixas de
  atendimento/pós-arrematação, comum no setor). Não confundir com "Lance
  Maior Leilões" (empresa diferente, SP, JUCESP, alvo de clonagem por
  golpistas).
- 9 lotes ativos no CE confirmados na investigação e reproduzidos no
  primeiro run real do scraper (15/09/2026): Iguatu, Aquiraz, Juazeiro do
  Norte (2), Maranguape, Fortaleza, Pedra Branca, Crato — todos imóveis.

## Como o site funciona (sem anti-bot)

- Site server-rendered em Yii2/PHP (não é SPA) — confirmado com
  `requests.get()` cru, sem proxy nem Playwright: o HTML já vem com os
  cards da listagem prontos. Nenhum Cloudflare/WAF bloqueando o IP de
  datacenter (diferente de MGL/Construbem/Daniel Garcia).
- `robots.txt` (`User-agent: *`) só desautoriza `/entrar/`, `/temp/`,
  `/search/`, `/ajax/`, `/auditorio/` e PDFs — `/imoveis/ce` está liberado.
  Sem bloco específico de bots de IA (diferente do Francisco Freitas). O
  scraper usa o mesmo User-Agent de navegador das outras fontes.
- **O filtro por UF funciona de verdade na própria URL**: `/imoveis/ce`
  devolve só os 9 lotes do Ceará ("1-9 de 9 itens"), diferente do
  `?estado=CE` (query string), que é **ignorado** e sempre devolve o
  inventário nacional inteiro (375 imóveis no momento do teste) — mesma
  armadilha do Francisco Freitas (`estado=` no `get-leiloes`) e da MGL
  (filtro só funciona no corpo do POST, não na URL). `/veiculos/ce`,
  `/bens-industriais/ce` e `/bens-de-consumo/ce` seguem o mesmo padrão de
  URL mas estavam **zerados** no CE na investigação e no primeiro run —
  não incluídos em `_GRUPO_LANCE_URLS` por ora (ver seção "Fora do escopo"
  abaixo).
- A listagem já traz tudo que o scraper precisa por lote (cidade/UF, tipo
  de leilão, preço atual, valores de 1ª/2ª praça ou praça única) — não
  precisa abrir a página de detalhe. Um card = um bloco
  `<div class="card-item" data-key="ID">`; extração por regex sobre o
  chunk entre um `data-key` e o próximo (mesma técnica usada no parser da
  Soleon).

## Modelagem dos dados

- Categoria hoje é sempre `imoveis` (só isso está ativo no CE). Vem do
  primeiro segmento da URL do lote (`/imoveis/...`).
- `marca = "Imóvel"`, `modelo = <título completo do card>` (mesma
  convenção da MGL) — o título já é descritivo o bastante
  ("Terreno, 6.000m², José Geraldo da Cruz, Juazeiro do Norte/CE").
- Preço/referência: cada card lista 1 ou 2 "praças" (1ª/2ª, ou "praça
  única"), cada uma com um valor. `lance_atual` = `card-price` (o valor
  que o próprio site já mostra como ativo agora); `fipe_valor`
  (referência) = o **maior** valor entre as praças listadas (a avaliação
  original, antes de desconto de 2ª praça).
- `data_leilao` = primeira data/hora encontrada no card (início da praça
  mais próxima), via `_extrair_data_leilao` (já genérico o bastante pro
  formato "DD/MM/YYYY às HH:MM" do site).

## Fora do escopo (por ora)

- **Veículos, bens industriais e bens de consumo**: o site tem essas
  categorias (`/veiculos/{subcategoria}/ce`, `/bens-industriais/ce`,
  `/bens-de-consumo/ce`) mas nenhuma tinha lote no CE na investigação nem
  no primeiro run. Como o formato de título de veículo desse site nunca
  foi visto com dado real (não dá pra validar o parser de
  marca/modelo/ano contra nada), a categoria fica de fora até aparecer um
  lote de verdade pra testar. Quando aparecer: adicionar a URL em
  `_GRUPO_LANCE_URLS` e mapear a subcategoria (`carros`, `motos`,
  `caminhoes`/`onibus`, `maquinas-industriais`→`equipamentos`,
  `eletronicos`) em `_grupo_lance_categoria`.
- Health check: `grupo_lance` entrou em `FONTES_ATIVAS` (scraper_health.py)
  — se ficar 3 runs seguidos zerada, alerta o dono via WhatsApp, igual às
  outras fontes "requests direto".

## Testes

`tests/test_scraper.py` — `TestGrupoLanceCategoria` e
`TestGrupoLanceParsePagina`, com HTML real capturado em 15/09/2026 (um
card com 1ª/2ª praça, um com praça única). Cobrem categoria, cidade,
lance/referência e extração de data — sem rede.

## Possível bloqueio de Cloudflare no IP do GitHub Actions (observado 2026-09-16)

O run agendado de 16/09 (10h37 UTC) reportou `HTTP 403` na primeira página
(`/imoveis/ce?pagina=1`), zerando a fonte nesse run (health check ainda não
alertou — exige 3 runs seguidos zerados). Investigação no mesmo dia:

- Da minha rede local (fora do GitHub Actions), a mesma URL responde
  `200 OK` com conteúdo real (HTML completo, ~75KB, cards intactos) —
  testado com `curl` e com `requests.Session()` (o mesmo client do
  scraper), 3x seguidas, sem falha.
- O site está atrás de Cloudflare (`Server: cloudflare` no header de
  resposta), o que **não** batia com a investigação original de 15/09
  ("Nenhum Cloudflare/WAF bloqueando o IP de datacenter"). Ou o site ligou
  proteção nova entre 15/09 e 16/09, ou a Cloudflare passou a
  bloquear/desafiar a faixa de IP de datacenter do GitHub Actions
  especificamente (igual já acontece com MGL/Construbem/Daniel Garcia).
- Decisão do dono (16/09): **esperar mais 1-2 runs agendados** (03h/15h
  Fortaleza) antes de agir — pode ter sido bloqueio pontual/temporário.
  Se confirmar 3 runs seguidos zerados (e o WhatsApp de alerta disparar),
  as opções em aberto são: (a) rotear via Zenrows como a MGL faz
  (`ZENROWS_API_KEY` já existe no projeto), ou (b) mover `grupo_lance` pra
  `FONTES_ESPERADAS_ZERO` em `scraper_health.py` e aceitar a fonte como
  dormente por ora, documentando aqui.

## Causa real do 0 lotes (2026-09-24)

O fallback Zenrows/ScraperAPI (c88f89a) estava correto. O problema era outro:
o site foi reestruturado. A listagem passou de `/imoveis/ce` (agora 301) para
`/ce/imoveis`, e as URLs de lote de `/imoveis/<sub>/ce/<cidade>/<slug>` para
`/ce/<cidade>/imoveis/<sub>/<slug>`. `_grupo_lance_categoria` so aceitava
`imoveis` como 1o segmento e descartava todos os cards (0 lotes, sem log,
porque um fetch 200 que nao gera lote nao imprimia nada).

Correcao: `_GRUPO_LANCE_URLS` aponta para `/ce/imoveis`; `_grupo_lance_categoria`
aceita os dois formatos; `_grupo_lance_resposta_valida` trata 200 sem card
(pagina de bloqueio/desafio) como falha e passa ao proximo fornecedor, com log
explicito (`200 sem cards`, tamanho e titulo); o total de lotes da fonte e
sempre logado, mesmo 0.

Validacao local (requests direto, sem proxy): 9 lotes CE, os mesmos da adicao
(Aquiraz, Juazeiro x3, Maranguape, Pedra Branca, Fortaleza, Crato x2).
Nao validado: o caminho via proxy no Actions (o 403 no IP do runner e
inconfirmavel localmente). Se o proximo run mostrar os logs de fallback
falhando, opcoes: mover para `FONTES_ESPERADAS_ZERO` ou Zenrows Scraping
Browser via CDP (como no MGL).
