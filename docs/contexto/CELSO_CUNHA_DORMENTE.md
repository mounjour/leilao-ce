# Celso Cunha Leilões — dormente (investigação 2026-09-08)

`_raspar_celso_cunha` foi **desativado** (chamada comentada em
`raspar_leiloes()`). A função e os helpers (`_cc_get`, `_demojibake`,
`_cc_data_leilao`, `_CC_BUNDLE_RE`, `_CC_UF_FORA_CE`) continuam no
`scraper.py` como base para a reescrita futura.

## O que aconteceu

Histórico do campo `celsocunha` no `leiloes.json` (contagem por commit):

| Período | Lotes por run |
|---|---|
| 20–26/08/2026 | **119** (estável) |
| 27/08/2026 | 75 |
| **28/08/2026 → hoje** | **0** (todos os runs) |

Queda de 119 → 0 de um dia para o outro = mudança no site, não inventário
minguando. O run passou a logar `⚠️ CelsoCunha: nenhum leilão encontrado na
homepage` e ninguém notou por ~12 dias (perda silenciosa — os `except:`
genéricos do scraper e a ausência de um health check de contagem por fonte).

## Causa raiz (confirmada acessando o site em 2026-09-08)

1. **Site reconstruído** (~27–28/08). jQuery 1.11, `Montserrat`,
   `swiper.min.css`, `web/css/style.css?v=1788888680`.
2. **Esquema de URL antigo removido.** `_raspar_celso_cunha` acha os leilões
   por regex `/leilao/\d+/<slug>` na homepage. Hoje **não existe nenhum**
   link desse tipo — `/leilao/...`, `/lote/...`, `/leiloes` todos retornam
   **404**.
3. **Lotes agora carregam por AJAX.** O `web/js/functions.js` novo chama
   `POST web/buscarLotes.php` (`{idLeilao, page, idTipo, idSucata}`),
   `POST web/detalheLote.php` (`{idLote}`) e `filtroBusca.php?acao=1`.
   `requests` no HTML da página não vê lote nenhum.
4. **Nenhum leilão ativo.** `/agenda-de-leiloes` (server-rendered) só lista
   editais **datados de 2019**, todos marcados "EM BREVE" / "Em loteamento"
   (LEILÃO PARÁ, AMC, DETRAN, SEPLAG, P M de Aracati, Prefeitura de Salvador,
   3ª Vara Empresarial do Ceará, CRM/PA, CRF/CE). Nenhum `codLeilao`
   renderizado → nenhum leilão em estado aberto.

Ou seja: mesmo reescrevendo o scraper contra os endpoints AJAX novos, hoje
não haveria nada para coletar.

## Plano de retorno

Quando o site voltar a ter leilão ativo (checar `/agenda-de-leiloes`
manualmente de vez em quando, ou deixar o health check do scraper avisar se
algum dia voltar a render):

1. Reescrever `_raspar_celso_cunha` estilo **MGL** — abrir sessão própria e
   fazer `fetch` de dentro da página para reaproveitar cookies/headers, em
   vez de `requests` puro no HTML.
2. Fluxo novo: `agenda` → lista de `idLeilao` → `POST web/buscarLotes.php`
   paginado por leilão → `POST web/detalheLote.php` por `idLote`.
3. Manter o filtro "só CE" ancorado (o rodapé traz o endereço do escritório
   em Fortaleza/CE, que dá falso positivo se procurar no texto inteiro — ver
   o comentário de `_raspar_celso_cunha`).
4. Reativar a chamada em `raspar_leiloes()` e voltar `CelsoCunha` ao banner.
