# Leilo: regressao apos o redesign do site e dedup com o Pacto (2026-09-25)

## Sintoma
Vistoria de 2026-09-25 (run 36124909630): `⚠️ Leilo: nenhum lote no CE`. No run
de 24/09 eram 29 lotes. `scraper_health.json`: `leilo` com `zero_streak: 1` (o
alerta so dispararia no 3o run seguido).

## Causa raiz
O Leilo passou pelo mesmo redesign que o Pacto sofreu em 21/09 (Pacto e Leilo
sao dois front-ends da mesma plataforma). O card (`class="cl column"`) continua
la, mas o href virou `/lote/<uuid>/`. O `_LEILO_CARD_RE` exigia
`/leilao/.../ano.NNNN/<uuid>`, entao nao casava nenhum dos 36 cards. O redirect
de `/leilao/fortaleza-ceara` para `/leilao/ceara/` era inofensivo (o `requests`
segue o 301).

## Achados que mudaram a solucao
1. **O HTML embute o estoque em JSON.** `window.__INITIAL_STATE__` traz
   `elastic.lotes` com os campos estruturados: `id` (o mesmo uuid da URL),
   `localizacao.estado`, `veiculo.anoModelo/km/retomada`, `valor.lance.valor`,
   `valor.minimo`, `fotosUrls`, `leilao.data`, `tipo`. Ler isso e' mais robusto
   que regex de markup (que ja quebrou duas vezes em 10 dias).
2. **Ha paginacao real**: `?pagina=N` (36 por pagina; `totalRegistros`,
   `totalPaginasAtual` no proprio JSON). O CE tem 54 lotes em 2 paginas. A versao
   de 16/09 dizia "sem paginacao" e via so 36. Outros nomes de parametro
   (`page`, `p`, `pag`, `pg`, `offset`, `tamanho`...) sao ignorados pelo site.
3. **O filtro CE e' de verdade** (`filtrosBusca: localizacao.estado = CE`); mesmo
   assim a UF de cada lote continua sendo validada.

## Correcao (scraper.py, bloco "SCRAPER LEILO.COM.BR")
Funcoes puras: `_leilo_estado_elastic`, `_leilo_parse_lote`, `_leilo_parse_pagina`
(+ `_leilo_foto/_data/_km/_lance`). I/O: `_leilo_baixar_pagina`,
`_leilo_coletar` (pagina ate o total, trava em `_LEILO_MAX_PAGINAS`, para se o
site devolver a pagina errada).

- **Lance** = `valor.lance.valor`; sem lance ainda, `valor.minimo` ("Lance
  Inicial"). Conferido contra o card: 18/18 com lance e os sem lance mostram o
  minimo. (`valorProposta` NAO serve: so bate com o card em 9 de 18.)
- **Data**: `leilao.data` esta em UTC; convertida para Fortaleza (UTC-3, sem
  horario de verao). Bate com o card em 36/36.
- **Foto**: primeira de `fotosUrls`; `/fotos-modelo/` (imagem generica) vira `""`.
  Lotes com `quantidadeFotos = 0` mostram a imagem generica no card, entao
  `foto` vazia e' correta (18 dos 54 hoje).
- **Categoria** vem do `tipo` do proprio lote (Carros/Motos/Utilitarios; mesmo
  mapa do Pacto), depois refinada por `detectar_categoria`. Tipo desconhecido
  cai em `carros`.
- **UF**: so entra lote com `localizacao.estado == "CE"` (salvaguarda de
  16/09 mantida).
- **Falhas visiveis**: HTTP != 200, 200 sem o JSON ("layout mudou?"), lotes
  recebidos mas nenhum no CE e "coletou X de Y" sao logados.
- URL do lote: `https://leilo.com.br/lote/<uuid>/`. Favoritos de lotes Leilo com a
  URL antiga (`/leilao/.../ano.NNNN/<uuid>`) deixam de casar (como no Pacto).

## Sobreposicao Pacto x Leilo (medida ao vivo, 2026-09-25)
| Medida | Resultado |
|---|---|
| Lotes Leilo / Pacto | 54 / 54 |
| Mesmo uuid nos dois | 54 (100%); 0 exclusivos de cada lado |
| Campos-chave diferentes (nome, valor, leilao, veiculo, `dataFim`) | 0 |
| Leilo <= Pacto nos commits de 21-24/09 (formato atual) | 4/4 runs, 0 exclusivos |
| Leiloes listados pelos dois hotsites | 65 em comum; o unico so do Leilo e' um leilao de imoveis em Goiania/GO |

Historico antes de 21/09 nao serve de comparacao: ate 09/09 o Pacto antigo
raspava so 30 lotes (todos dentro do Leilo) e de 10 a 20/09 os dois raspavam
conjuntos diferentes (Pacto no layout antigo).

## Decisao de dedup
- **Chave exata**: uuid do lote (`_uuid_lote_plataforma`), so para URLs
  `/lote/<uuid>/` de `pactoleiloes.com.br` e `leilo.com.br`.
  `_chave_dedup_entre_fontes` devolve `lote:<uuid>` (prioridade sobre
  processo/matricula). Sem heuristica de titulo/lance/ano: zero risco de falso
  positivo.
- **Canonico = Pacto** (roda antes no pipeline; politica de "primeira
  ocorrencia" inalterada). Os dados dos dois sao identicos.
- **Leilo = reserva**: se o scraper do Pacto quebrar (Playwright, ja quebrou 3
  runs), os lotes do Leilo passam a aparecer, sem mudar nada. Ressalva: uma
  mudanca da plataforma quebra os dois de uma vez.
- **Health check**: continua contando o Leilo ANTES do dedup, entao ele segue
  monitorado (contagem, `lance>0`, `foto`) mesmo com todos os lotes mesclados.
  Por isso `_raspar_leilo` NAO pula os lotes que o Pacto ja trouxe.
- **Custo**: o Leilo faz FIPE (4 requests) por lote duplicado, ~200 requests por
  run (1-3 min). A IA nao e' cobrada duas vezes: `_analise_do_gemeo` reaproveita
  a analise que o Pacto deixou no cache (ignora o `dados_hash`, pois o Pacto nao
  le a descricao do lote).

## Validacao ao vivo (2026-09-25, script descartavel, FIPE/IA stubados)
`_leilo_coletar`: 54 lotes CE (site informa 54); por categoria carros 29, motos
24, caminhoes 1; 54 com lance, ano e data; 36 com foto; 45 com km; todos
`Eusebio/CE`. Dedup real Pacto+Leilo: 108 -> 54 (so Pacto). Sem o Pacto: os 54 do
Leilo sobrevivem.

## Testes
`tests/test_scraper.py`: `TestUuidLotePlataforma`, `TestLeiloParseLote`,
`TestLeiloParsePagina`, `TestLeiloColetar`, `TestRasparLeilo`,
`TestAnaliseDoGemeo`, mais casos Pacto<->Leilo em `TestChaveDedupEntreFontes` e
`TestRemoverDuplicatasEntreFontes`. Fixture real (6 lotes de 2026-09-25):
`tests/fixtures/leilo_listagem_2026-09-25.html`. 169/169.

## Pendencias (fora de escopo, registradas)
- **Migrar o Pacto para este mesmo parser via `requests`** (RESOLVIDO em 2026-09-25, ver PACTO_REGRESSAO_2026-09.md): o JSON esta no HTML
  SSR do Pacto tambem; eliminaria Playwright e a classe de bug de foto
  preguicosa. Mexe num scraper ja validado; fazer em sessao propria.
- **Favoritos por uuid** (RESOLVIDO em 2026-09-29): `favorites._normalizar_url` compara a URL inteira. Se o
  Pacto cair e o Leilo assumir, o favorito do lote nao casa. Normalizar por uuid
  para URLs `/lote/<uuid>/` resolveria (e tambem a troca de dominio).
- `leiloes.json` so reflete a correcao apos o proximo run do Actions.

## Historico: reescrita de 2026-09-16 (superada por este doc)

> Primeira reescrita do Leilo, antes do redesign. Superada em 2026-09-25: o parser
> por HTML foi trocado pelo JSON embutido e a afirmacao de que "nao ha paginacao"
> caiu (existe `?pagina=N`). As salvaguardas (categoria do proprio lote, UF "CE" por
> lote) foram mantidas. Antes ficava em `LEILO_REESCRITO_2026-09.md`.

Reportado pelo dono: no dashboard em produção, o filtro "Categoria: motos"
mostrava caminhões, "Categoria: caminhões" mostrava carros, e alguns nomes
de lote apareciam com texto estranho (ex.: "Leilao-De-Seguradoras-15-09-26
Honda Xre 300..." em vez de só "Honda Xre 300..."). Investigação encontrou
a causa raiz — e um problema mais sério além do relatado.

### Causa raiz: o site do Leilo mudou de estrutura

1. **A navegação por cidade+categoria parou de filtrar.** O scraper antigo
   pedia `https://leilo.com.br/leilao/{cidade}-ceara/{categoria}` (ex.:
   `.../eusebio-ceara/caminhoes`). Hoje esse formato **não filtra mais
   nada** — cai num feed genérico/nacional (testado ao vivo: `/motos` e
   `/caminhoes` devolviam exatamente os mesmos lotes, de cidades como
   Aparecida de Goiânia/GO, Taguatinga/DF, Alvorada/RS). Só
   `/leilao/{cidade}-ceara` **sem** sufixo de categoria continua
   funcionando como filtro de verdade — e hoje só existe **um** grupo de
   busca ativo pro Nordeste: `fortaleza-ceara` (cobre o pátio físico em
   Eusébio/CE; não há filtro fino por cidade do interior).
2. **A URL do lote ganhou um segmento novo.** Antes:
   `/leilao/{cidade}/{categoria}/{marca}/{modelo}/ano.NNNN`. Agora o site
   agrupa lotes por "leilão nomeado" (ex.:
   `leilao-de-seguradoras-15-09-26`), inserido **entre** a categoria e o
   veículo, que também passou a vir num slug só (marca+modelo juntos):
   `/leilao/{cidade}/{categoria}/{nome-do-leilao}/{marca-modelo}/ano.NNNN`.
   O parser antigo lia por índice fixo (`pts[3]` = marca, `pts[4]` =
   modelo) — com o segmento novo no meio, `pts[3]` virou o nome do leilão
   ("Leilao-De-Seguradoras-15-09-26") e `pts[4]` o slug marca+modelo
   inteiro. Daí o nome de lote esquisito (achado 2 do dono).

### O problema mais sério: lote de outro estado rotulado como CE

Como o problema 1 faz `/caminhoes`, `/motos` etc. caírem no feed nacional
sem filtro, e o scraper antigo **nunca validava a UF real do lote** (só
confiava que a URL pedida já tinha filtrado), lotes de **outros estados**
estavam sendo salvos no `leiloes.json` com `/CE` colado por engano.
Confirmado direto no arquivo em produção antes da correção:

```
{'Taguatinga Df/CE', 'Cuiaba Mt/CE', 'Candeias Ba/CE', 'Benevides Pa/CE',
 'Manaus Am/CE', 'Aparecida De Goiania Go/CE', 'Eusebio Ce/CE'}
```

Ou seja: usuário em Fortaleza via lote de Cuiabá/MT ou Taguatinga/DF como
se fosse do Ceará. Isso é mais grave que a categoria errada — é dado
geograficamente incorreto indo pro usuário final.

### Correção (`_raspar_leilo` reescrita)

- Uma única URL: `https://leilo.com.br/leilao/fortaleza-ceara` (sem
  sufixo de categoria).
- Site é **server-rendered** — confirmado com `requests.get()` cru, sem
  Playwright. Cada card da listagem já traz tudo que precisamos prontos:
  título como `"MARCA/MODELO"` (atributo `aria-label`/`title`, mais
  confiável que remontar da URL), UF (`cl__uf`), cidade (`cl__info--local`
  title), km, lance, data do leilão e foto. Não precisa mais abrir a
  página de detalhe por lote — scraper passou de Playwright pra "requests
  direto", junto com MJ/Receita SLE/Francisco Freitas/Grupo Lance.
- Categoria vem do **segmento da própria URL do lote**
  (`/leilao/{cidade}/{categoria}/...`), não de um valor "pedido" — a
  página é uma listagem só, não há mais o que pedir por categoria.
- **Rede de segurança contra o vazamento de outro estado**: cada card só
  é aceito se `cl__uf` = `"CE"` **e** a cidade (`cl__info--local`) termina
  em `/CE`. Se o filtro da URL cair de novo no futuro, os lotes de outro
  estado são descartados em vez de herdar `/CE` por engano — a mesma
  falha do parágrafo anterior não devia se repetir silenciosamente.
- Cobertura: 36 lotes/run no teste (antes o scraper tentava 60 URLs —
  12 cidades × 5 categorias — mas a maioria caía no mesmo feed genérico
  sem filtro, então o ganho real de cobertura daquele esquema já era
  ilusório). Não há paginação disponível nessa listagem (testado: query
  params `?pagina=`/`?page=`/scroll incremental não trazem lotes além dos
  ~36 iniciais, apesar do badge do site dizer "124 Lotes" — mismatch da
  própria UI do Leilo, não algo o scraper pode contornar sem descobrir o
  mecanismo real de paginação deles).
- Imóveis/equipamentos do Leilo vivem numa seção separada do site
  (`/leilao/imoveis`) e não passam por essa listagem — fora do escopo
  desta correção (o scraper antigo também nunca trouxe nenhum lote dessas
  categorias via Leilo, então não é uma regressão).

### Testes

`tests/test_scraper.py` — `TestLeiloParseListagem`, com HTML real
capturado em 16/09/2026 (um card de carro em CE) mais dois cards
sintéticos (moto em CE, carro em GO) pra cobrir o mapeamento de categoria
pela URL e a rede de segurança contra lote de outro estado.

### Pendência

O `leiloes.json` commitado ainda tem os dados antigos (com o vazamento de
outro estado) até o próximo run do GitHub Actions (`scraper.yml`, 1x/dia
às 06h UTC) ou um disparo manual (`workflow_dispatch`) regenerar o
arquivo com o scraper corrigido.
