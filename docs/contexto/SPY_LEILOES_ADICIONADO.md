# Spy Leilões — adicionada como fonte (2026-09-16)

Agregador nacional priorizado na investigação de novas fontes de 2026-09-14
(ver `docs/contexto/INVESTIGACAO_NOVAS_FONTES_2026-09-14.md`, que já tinha
apontado ~195 lotes em Fortaleza). Implementado como `_raspar_spy_leiloes`
em `scraper.py`.

## Por que essa fonte

- `spyleiloes.com.br` é um **agregador**, não um leiloeiro próprio — cobre
  "+200 mil leilões" e "+900 leiloeiros" no Brasil segundo o próprio site.
  É um SaaS pago pro usuário final (planos de R$99-197/mês com busca
  avançada, mapa, alertas de WhatsApp etc.), mas a busca básica em
  `/imoveis-leilao` é **pública, sem login**.
- 604 imóveis confirmados no Ceará num run real (16/09/2026) — bem mais que
  os ~195 da investigação original, porque aquele número era só um recorte
  de Fortaleza; o total agora é estadual. Cobre cidade grande (Fortaleza:
  176, Caucaia: 41, Sobral: 23) e municípios pequenos (Choró, Roriz,
  Tupinambá...).

## Como o site funciona

- Next.js App Router, mas a listagem **é renderizada no servidor (SSR)** —
  um `requests.get()` cru já traz o HTML final com todos os cards e seus
  dados; não precisa de Playwright nem existe uma API JSON separada pra
  consumir diretamente (os dados vêm embutidos no HTML, não via fetch
  client-side).
- Filtro por UF funciona na query string: `?estado=CE`.
- **Paginação real é `page=N`** — a UI mostra controles com nomes diferentes
  ("Leilões por pagina", parâmetro aparente seria algo como `pagina`), mas
  testado e confirmado: `pagina=N` é **ignorado** (sempre devolve a página
  1), só `page=N` de fato pagina. Tamanho de página fixo em 20 itens
  (parâmetros de tamanho testados — `porPagina`, `itensPorPagina` — também
  não tiveram efeito).
- A ordenação default (rotulada "Aleatório" na UI) é, na prática,
  **estável entre requisições idênticas** — testado 2x seguidas, mesma
  ordem exata. Sem isso, paginar página a página correria risco de pular
  ou duplicar itens.
- Sem Cloudflare/anti-bot na frente — `requests` direto, mesmo User-Agent
  genérico das outras fontes.

## Modelagem dos dados

Card = `<li class="BroadSearch_auctionItem__iYXnc">`. Convenção igual à do
Grupo Lance (agregador só de imóveis): `marca = "Imóvel"`,
`modelo = <título completo do card>`, categoria sempre `imoveis`.

- `lance_atual` = preço em destaque no topo do card
  (`styles_h4LanceInicial`).
- `fipe_valor` (referência) = o **maior** valor entre as datas/praças
  listadas no card (`styles_date`/`styles_line`) — normalmente a 1ª praça
  (avaliação), antes do desconto da 2ª. **495 de 604 lotes (82%) trouxeram
  essa referência**; o resto tem só 1 valor (sem 1ª/2ª praça pra comparar),
  fica "Sem referência" — mesmo comportamento de outras fontes quando falta
  dado.
- `data_leilao` = data da última praça/linha do card (a mais próxima da
  data atual ou já a 2ª praça, quando existe).
- Cidade: extraída do endereço, que sempre termina em
  `"<Cidade> - Ceará"` (às vezes seguido de `, Cep ...`) — regex captura o
  trecho antes de `" - Ceará"`.

### Bug pego e corrigido durante a validação

O separador entre a `<span>` da data e a `<span>` do preço, dentro de cada
linha de praça, **não é um espaço/nbsp como no Grupo Lance — é um bullet
`•` (U+2022)**. O regex inicial (`</span>\xa0<span...`, copiado por
analogia de outra fonte) não batia com nada, e `fipe_valor`/`data_leilao`
saíam sempre vazios/zero mesmo com o dado presente no HTML. Corrigido para
`</span>.<span...` (ponto casa qualquer caractere) depois de inspecionar o
código do separador (`hex(ord(c))` → `0x2022`) num smoke test contra a
página ao vivo. Sem esse teste com dado real, o bug passaria despercebido
silenciosamente (nenhum erro, só campos vazios).

## Limitação conhecida: duplicata entre fontes

Como é agregador, os mesmos imóveis de leiloeiros já raspados diretamente
(Francisco Freitas, Maria Fixer, Grupo Lance...) podem aparecer aqui de
novo com uma URL diferente (`spyleiloes.com.br/leilao/...` em vez da URL
do leiloeiro original) — sem chave de dedup cruzada entre fontes (o
`vistos` do scraper dedupa só por URL, e cada fonte tem sua própria URL),
esses imóveis entram como itens duplicados no dashboard. Já era um risco
conhecido apontado no backlog da investigação de 2026-09-14; aceito por
ora, revisar se virar um incômodo real pro dono.

## Health check

`spy_leiloes` entrou em `FONTES_ATIVAS` (`scraper_health.py`) — se ficar 3
runs seguidos zerada, alerta o dono via WhatsApp, igual às outras fontes
"requests direto".

## Testes

Sem teste automatizado dedicado (mesma situação do Francisco Freitas e do
Maria Fixer: os helpers são específicos de parsing de HTML ao vivo).
Validado com dois smoke tests manuais contra a API ao vivo em 16/09/2026:
o primeiro pegou o bug do separador `•` (todo `fipe_valor`/`data_leilao`
zerado); o segundo, já corrigido, confirmou 604 lotes CE, 495 com
referência de preço, cidades/datas/valores condizentes com o que o site
mostra. `python -m pytest -q` segue passando (90/90).
