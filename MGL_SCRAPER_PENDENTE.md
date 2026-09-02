# MGL Leilões — scraper CONSERTADO (2026-09-02)

`_raspar_mgl` estava retornando 0 lotes e estourando `wait_for_selector`
(`.dg-leiloes-item`, Timeout 30000ms) no GitHub Actions. **Reescrito em
2026-09-02** para usar a API JSON da busca em vez de raspar o DOM.

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

## Se voltar a dar 0 no GitHub Actions

Provável bloqueio de Cloudflare no runner mesmo com Chromium headless. Nesse
caso, rotear a chamada de `/apiplugin/GetBusca` e das páginas de lote pelo
Zenrows quando `ZENROWS_API_KEY` estiver setada (padrão de `_raspar_soleon`).
Depende de crédito Zenrows recarregado.
