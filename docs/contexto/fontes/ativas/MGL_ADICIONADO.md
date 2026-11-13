# MGL Leilões (ativa via API HTTP do Zenrows, 2026-09-29)

> Resumo: a MGL bloqueia o IP do GitHub Actions com Cloudflare. Desde 2026-09-29,
> `_raspar_mgl` chama a API de busca do site pela **API HTTP do Zenrows** (proxy premium
> no Brasil), sem Playwright. Validado num run real: 13 lotes de imóvel no CE. `mgl` está
> em `FONTES_ATIVAS` no health check.

## Contexto

A MGL só tinha imóvel no CE (retomados da Caixa) quando foi integrada; o código também
traz veículo se aparecer. A fonte passou por três fases:

1. **2026-09-02:** reescrita para a API JSON da busca (o DOM antigo e as regexes de
   detalhe tinham quebrado). Funcionava no navegador, mas o Cloudflare bloqueava o runner:
   a SPA não inicializava e a API devolvia 403.
2. **2026-09-04:** tentativa com o Zenrows Scraping Browser (`connect_over_cdp`). Nunca
   passou: o Cloudflare servia a interstitial e a SPA não subia (0 lotes de 26 a 29/09).
3. **2026-09-29:** troca para a API HTTP do Zenrows, que funciona. O Playwright/CDP foi
   removido.

## Implementação

`_raspar_mgl` em `scraper.py`:

1. `_mgl_zenrows_busca` faz `POST /apiplugin/GetBusca/{Pagina}/{PaginaIndex}/0?` via
   Zenrows com `premium_proxy=true&proxy_country=br` (sem `proxy_country=br` dá 422). Corpo
   = `_MGL_BUSCA_PARAMS`, com `ID_Estado: 23` (Ceará) e `ID_Categoria: 0` (veículos e
   imóveis). O filtro de estado só funciona no corpo do POST, não no `#hash` da URL.
2. `_mgl_categoria_lote` decide `imoveis` / `carros` / `motos` / `caminhoes` /
   `equipamentos`, ou `None` para bens diversos (fora do escopo). Salvaguarda extra:
   descarta `UF != "CE"`.
3. `_mgl_zenrows_detalhe` busca a página do lote. Ela é instável (às vezes volta o desafio,
   4-7 KB): repete até 3x (`_MGL_DETALHE_TENTATIVAS`) e, se falhar, segue só com os dados
   da listagem (sem avaliação nem descrição).
4. Parsers do detalhe (sobre `_html_para_texto`):
   - veículo: `_mgl_parse_detalhe_veiculo` (`MODELO:`, `ANO: aaaa/aaaa`, `KM:`) e
     `_mgl_descricao` (specs + bloco "Ônus");
   - imóvel: `_mgl_avaliacao_imovel` (`Avaliação: R$ ...`) vira o `ref_val`.
5. `data_leilao` sai de `GetLoteRealTime[0]` (abertura da 1ª praça; em venda direta, o
   encerramento). Foto: `imagens-complete/605x487/<Foto>` (`_mgl_url_foto`).

Custo: requisições premium do Zenrows (~1 busca + 1 a 3 por lote). Sem `ZENROWS_API_KEY`
ou sem crédito, a função sai limpa e não trava o resto do run.

### Contrato da API

```
POST https://www.mgl.com.br/apiplugin/GetBusca/{Pagina}/{PaginaIndex}/0?
Content-Type: application/json
Corpo: window.JsonParametrosBusca  (ver _MGL_BUSCA_PARAMS)
```

Campos por lote usados: `Lote` (título), `URLlote`, `UF`, `Cidade`, `IconeCategoria`,
`ValorInicialPrimeiraPraca` / `ValorVendaDireta`, `Fotos[].Foto`,
`GetLoteRealTime[0].DataHoraAberturaPrimeiraPraca` / `...EncerramentoPrimeiraPraca`.
Sentinela de data ausente: `1900-01-01T00:00:00`.

## Referências

- `scraper.py`: `_raspar_mgl`, `_mgl_*`, `_MGL_*`
- Health check: [`../../SCRAPER_HEALTH.md`](../../SCRAPER_HEALTH.md)
- Histórico detalhado das fases 1 e 2: versões anteriores deste arquivo no git
  (`docs/contexto/fontes/pausadas/MGL_SCRAPER_PENDENTE.md`)
