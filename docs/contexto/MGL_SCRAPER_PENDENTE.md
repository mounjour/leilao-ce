# MGL Leilões — bloqueio do runner contornado via Zenrows (2026-09-04)

> **Atualização 2026-09-04:** `_raspar_mgl` foi mudado pra abrir sua própria
> sessão de browser remota na **Zenrows Scraping Browser**
> (`p.chromium.connect_over_cdp("wss://browser.zenrows.com?apikey=...")`,
> reaproveitando a `ZENROWS_API_KEY` que já existia pro Construbem/Daniel
> Garcia) em vez do Chromium local (`p.chromium.launch(headless=True)`)
> compartilhado com os outros scrapers Playwright. Motivo de precisar de uma
> abordagem diferente da usada no Construbem: lá o bloqueio era só no fetch
> HTTP (resolvido com proxy de URL simples via `_raspar_soleon`); aqui o
> Cloudflare bloqueia a **navegação inteira** — a SPA não inicializa nem no
> `goto` inicial — então só um proxy residencial na camada do próprio
> navegador resolve. Avaliado e descartado dar fallback via ScraperAPI:
> não tem produto de navegador remoto via CDP, só uma API HTTP stateless
> (`render=true` + DSL de instruções), o que exigiria reescrever o scraper
> inteiro num paradigma sem sessão persistente — não compensa pro MGL, que
> hoje só tem imóvel no CE (decisão do dono do projeto: mesmo assim vale
> investir, porque o problema era de código, e pode aparecer veículo no
> futuro). Sem crédito/chave, o scraper faz bail limpo e não trava o resto
> do run. **Ainda não validado num run real do GitHub Actions** — só
> revisado por leitura de código.

---

# Histórico: código reescrito, mas BLOQUEADO no runner (2026-09-02)

`_raspar_mgl` estava retornando 0 lotes e estourando `wait_for_selector`
(`.dg-leiloes-item`, Timeout 30000ms) no GitHub Actions. **Reescrito em
2026-09-02** para usar a API JSON da busca em vez de raspar o DOM.

> **Status: o código novo funciona (validado contra dados reais via
> navegador), MAS o Cloudflare bloqueia o site inteiro a partir do IP do
> GitHub Actions.** 2 runs manuais (17:23Z e 18:22Z) confirmaram: a SPA nem
> inicializa no runner (`window.JsonParametrosBusca` nunca aparece) e a API
> devolve 403. Stealth + espera + retry não passam — é bloqueio na borda.
> **Parado até ter proxy residencial** (Zenrows/ScraperAPI, hoje 402/timeout —
> mesmo muro do Construbem/Daniel Garcia). MGL só tem imóvel no CE agora
> (zero veículo), então a prioridade é baixa.

## Causa raiz

1. **URL de busca obsoleta.** O `#hash` mudou de esquema
   (`Engine=StartMGL&modelo=Veículos&estado=23` → `Engine=Start&ID_Categoria=N`),
   então a listagem antiga carregava vazia e o `wait_for_selector` nunca
   resolvia.
2. **O filtro de estado só funciona no corpo do POST, não no hash.** Passar
   `estado=23`/`ID_Estado=23` na URL não filtra nada (a SPA ignora). No corpo
   JSON de `POST /apiplugin/GetBusca`, `ID_Estado: 23` filtra o Ceará
   corretamente.
3. **A página de detalhe mudou de layout.** Não existe mais `MARCA/MODELO:`
   nem `ANO/MODELO:`; agora é `MODELO: <marca modelo>`, `ANO: <aaaa>/<aaaa>`,
   `KM: <n>`. As duas regexes antigas não casavam mais nada.
4. **Cloudflare bloqueia IP de datacenter.** `requests.get` numa página de
   lote retorna **403**. Só funciona via navegador real (Playwright), que
   passa o desafio JS ao abrir `/busca/` e mantém o cookie `cf_clearance`.

## Como funciona agora

`_raspar_mgl` (em `scraper.py`):

1. `pg_lista.goto(_MGL_BUSCA_URL)` uma vez (passa o Cloudflare).
2. Pagina a listagem com `pg_lista.evaluate(fetch POST /apiplugin/GetBusca/…)`
   — mesma origem, reaproveita o clearance. Corpo = `_MGL_BUSCA_PARAMS` com
   `ID_Estado: 23`, `ID_Categoria: 0` (traz veículos **e** imóveis).
3. Para cada lote: `_mgl_categoria_lote` decide `imoveis` / `carros` / `motos`
   / `caminhoes` / `equipamentos`, ou `None` para bens diversos (fora do
   escopo). Filtro de segurança extra: descarta `UF != "CE"`.
4. Página de detalhe via `pg_lista.evaluate(fetch <url_lote>)` (HTML cru, sem
   navegar) → `_html_para_texto` → parsers:
   - **veículo:** `_mgl_parse_detalhe_veiculo` (MODELO/ANO/KM) +
     `_mgl_descricao` (specs + bloco "Ônus" com IPVA/restrições).
   - **imóvel:** `_mgl_avaliacao_imovel` (`Avaliação: R$ …` do bloco de
     valores) vira o `ref_val`; descrição fica vazia (o resto é só o edital).
5. `data_leilao` sai de `GetLoteRealTime[0]` (abertura da 1ª praça; para venda
   direta, o encerramento). Foto: `imagens-complete/605x487/<Foto>`.

## Contrato da API (para manutenção futura)

```
POST https://www.mgl.com.br/apiplugin/GetBusca/{Pagina}/{PaginaIndex}/0?
Content-Type: application/json
Corpo: window.JsonParametrosBusca  (ver _MGL_BUSCA_PARAMS)
```

Campos por lote usados: `Lote` (título), `URLlote`, `UF`, `Cidade`,
`IconeCategoria`, `ValorInicialPrimeiraPraca` / `ValorVendaDireta`, `Fotos[].Foto`,
`GetLoteRealTime[0].DataHoraAberturaPrimeiraPraca` /
`…EncerramentoPrimeiraPraca`. Sentinela de data ausente: `1900-01-01T00:00:00`.

## Situação do inventário (2026-09-02)

A MGL tinha **0 veículos no CE** — os 23 lotes do estado eram 21 imóveis
(retomados Caixa) + 2 bens diversos. Por isso o scraper agora inclui imóveis
(decisão do dono do projeto). Quando a MGL tiver veículo no CE, o mesmo código
já traz — sem mudança.

## Cloudflare no runner do GitHub Actions (pendente)

**1º run (17:23Z):** `goto` passou, mas `fetch /apiplugin/GetBusca` → **403**.

**Endurecimento aplicado** (`stealth_sync`, espera por `JsonParametrosBusca`,
headers de XHR + `credentials:'include'` + retry 3x no fetch).

**2º run (18:22Z), com o endurecimento:**

```
📡 MGL | veículos e imóveis no Ceará
  ⚠️ MGL: SPA nao inicializou (possivel bloqueio Cloudflare no runner)
  ⚠️ MGL busca p1: 403
  ✅ MGL: 0 lote(s)
```

`window.JsonParametrosBusca` nunca apareceu → a página real da SPA **não
carrega** no runner (Cloudflare serve a interstitial/bloqueio antes de
qualquer desafio resolvível pelo headless). Confirmado: **bloqueio duro por
IP de datacenter**.

**Único caminho:** proxy residencial — rotear `/apiplugin/GetBusca` e as
páginas de lote pelo Zenrows/ScraperAPI quando a key estiver setada e com
crédito (padrão de `_raspar_soleon`). Hoje ambos estão fora (402/timeout no
mesmo run). O código atual faz bail rápido com mensagem clara quando a SPA
não inicializa.
