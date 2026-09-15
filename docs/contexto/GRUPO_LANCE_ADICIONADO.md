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
