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
