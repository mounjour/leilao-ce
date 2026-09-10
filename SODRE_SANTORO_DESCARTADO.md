# Sodré Santoro — descartado como fonte (investigação 2026-08-31)

Investigado a pedido do backlog ("adicionar Sodré Santoro"). **Não foi
implementado**: o Sodré Santoro não tem lotes no Ceará, então um scraper
filtrando por CE (como todos os outros do projeto) retornaria zero.

## Por que descartado

- O site **não tem filtro por estado** para veículos — só por `lot_location`,
  que é uma lista de **pátios**, todos em SP ou PR:
  guarulhos i/sp (272), outros locais (128), curitiba i/pr (54),
  monte mor/sp (52), caçapava/sp, bauru/sp, sertãozinho/sp, limeira/sp,
  ribeirão preto/sp, cesário lange/sp, guarulhos iii/sp, curitiba ii/pr.
- "outros locais" é o balde coringa; na amostra coletada eram todos lotes
  da COFCO (agronegócio paulista), com visitação em Meridiano/SP e Ibirá/SP.
- O campo `lot_location_address` vem `null`; o endereço real só aparece no
  texto livre de `lot_description`.
- Nenhum pátio ou cliente no Nordeste.

## Contrato da API (caso um dia se revisite)

SPA em **Nuxt 3**. Os lotes vêm de uma rota do próprio site que repassa uma
query **Elasticsearch**:

```
POST https://www.sodresantoro.com.br/api/search-lots
Content-Type: application/json
```

- Corpo = Elasticsearch Query DSL. Paginação: `"from": <n>, "size": 48`
  (`from = (pagina - 1) * 48`). O `post_filter` carrega os filtros de UI
  (ex.: `{"terms": {"lot_location": ["outros locais"]}}`).
- Resposta: `{ "results": [ ... ], "aggs": { ... }, "total": N, "page": N, "perPage": 48 }`.
- Sem anti-bot aparente (é o proxy deles, JSON limpo). `apiURL` interno
  `https://prd-api.sodresantoro.com.br` + `apiSanctumToken` público ficam no
  HTML, mas `search-lots` não precisa deles.

Campos por lote (todos já mapeáveis pro `_lote_dict` de scraper.py):

| Campo API | Uso |
|---|---|
| `lot_brand`, `lot_model`, `lot_title` | marca / modelo |
| `lot_year_manufacture`, `lot_year_model` | ano |
| `bid_initial`, `bid_actual` (string "116000.00") | lance |
| `lot_km` (int) | km |
| `lot_description` (texto livre) | descrição + único lugar com a cidade |
| `lot_category` | caminhões / carros / motos / utilitarios leves / tratores / implementos rod. |
| `lot_pictures` (array de URLs completas) | foto |
| `auction_date_init` ("2026-09-10 11:00:00") | data_leilao |
| `auction_id`, `lot_id`, `id`, `lot_number` | montar URL do lote |
| `lot_status_id` (1 = em andamento) | filtrar abertos |
| `client_name`, `auction_name` | contexto |

Inventário nacional na época: ~219 carros, 96 caminhões, 74 motos,
58 utilitários leves.

## Re-análise 2026-09-09 — segue descartado

Re-checado a pedido do dono ("ele já teve lotes no CE? poderá ter?"). Resposta:
**nenhum lote no CE agora, nenhum sinal de que já teve, e só um canal
teórico para o futuro.** Não é filtro escondendo lote bom — é ausência de
footprint no estado.

### Estado atual (consulta ao vivo na API `POST /api/search-lots`)

2.284 lotes abertos no total: materiais 1.296, veículos 654, sucatas 159,
luxos 125, judiciais 32, imóveis 18.

- Agregação por `lot_location`: **todos os locais são SP ou PR** (`outros
  locais` 1007, `guarulhos i/sp` 805, `são paulo/sp` 135, `monte mor/sp`,
  `curitiba i/pr`, `ribeirão preto/sp`, `bauru/sp`, `caçapava/sp`,
  `sertãozinho/sp`, `cascavel/pr`, `consultar edital` 17…).
- Busca por `"ceará"` e por 12 municípios cearenses (Fortaleza, Caucaia,
  Maracanaú, Sobral, Juazeiro do Norte, Eusébio, Aquiraz, Maranguape,
  Iguatu, Quixadá, Crateús…) em `lot_description` / `lot_city` /
  `lot_state` / `lot_location` / `lot_title` / `search_terms`: **0 em
  todos os segmentos**.
- Imóveis abertos (18): 13 SP, 5 PR. O agregador terceiro
  leilaoimovel.com.br/leiloeiro/sodre-santoro lista 25 imóveis do Sodré
  Santoro, **todos em SP**.
- As ~12 ocorrências de `/ce` em `lot_description` são falso-positivo
  ("cabine estendida", "Accelo 1017 CE" etc.), nunca o estado.
- Notas de API: o antigo `search-lots` com Query DSL do post_filter ainda
  funciona a partir do browser (mesma origem), mas responde página de erro
  Azion para `curl`/WebFetch cru. Campos de imóvel: `lot_state`,
  `lot_city`, `lot_neighborhood`, `lot_street` (o mapa antigo só tinha
  `lot_description`). `segment_slug` ∈ {materiais, veiculos, sucatas,
  luxos, judiciais, imoveis}.

### Histórico — nada no CE

- Empresa estruturalmente paulista: leiloeiros na JUCESP (Luiz Fernando
  #192, José Eduardo #195, Flávio Cunha #581); ~143 processos como "Sodré
  Santoro Leiloeiro Oficial", quase todos no TJSP.
- Pátios de veículos só em SP + PR (Guarulhos, Bauru, Monte Mor, Ribeirão
  Preto, Cesário Lange, Caçapava, Sertãozinho, Limeira, Curitiba,
  Cascavel) — nada no Nordeste.
- Os leilões de frota do Detran-CE em Fortaleza vão para a **Montenegro
  Leilões**, não para o Sodré Santoro.
- Nenhuma notícia, edital ou registro de leilão do Sodré Santoro no CE em
  nenhum ano.

### Poderá ter lote no CE?

- Veículos/sucata: praticamente não — preso aos pátios SP/PR; precisariam
  abrir base no Nordeste, nunca sinalizado.
- Imóvel extrajudicial (Caixa/Bradesco, Lei 9.514): teoricamente sim —
  leiloeiro oficial atua no país todo, então um imóvel Caixa retomado no
  CE poderia cair na mão deles. Mas a carteira bancária deles é
  concentradíssima em SP; hoje, zero mandato no CE.
- Judicial: improvável — exigiria uma vara cearense nomear o Sodré Santoro
  especificamente, disputando com leiloeiros locais da JUCEC (o TJ-CE já
  está com HastaPública / Silvio Maraschi).

### Recomendação

Manter descartado. Único canal que algum dia poderia surgir lote CE sem o
Sodré Santoro mudar de modelo: segmento **imóveis** com `client_name` =
caixa/bradesco. Vale, no máximo, um re-check leve trimestral só nesse
recorte. Todo o resto é "não" estrutural.
