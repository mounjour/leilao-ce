# Pacto: foto faltando por carregamento assíncrono (corrigido 2026-09-18)

## Pedido

O dono reportou lotes sem imagem no projeto que tinham imagem no site
original. Investigação varreu o `leiloes.json` inteiro (1011 lotes) e checou
ao vivo, contra o site de cada fonte, todo lote sem `foto`.

## O que era esperado (não é bug)

`receita_sle` (282/287), `spy_leiloes` (87/594), `francisco_freitas`
(17/37), `mega` (1/22) e `maria_fixer` (1/2) bateram com ausência real de
foto no site original (confirmado via API/DOM ao vivo).

## O que era bug de verdade

Só o Pacto (6/19). Confirmado ao vivo que `BAJAJ/DOMINAR NS160` e
`CHEVROLET/VECTRA HATCH 4P GT` têm foto real no site mas foram salvos com
`foto: ""`.

## Causa raiz

A foto do card é um `background-image` no componente Quasar `q-img`, setado
de forma assíncrona/preguiçosa conforme o card entra na tela. O scraper
(`_raspar_pacto` em `scraper.py`) lia o `style` uma única vez logo após o
scroll, e alguns cards ainda não tinham terminado de carregar a imagem nesse
instante.

## Correção

`pg.wait_for_load_state("networkidle")` após o scroll, mais um retry (até
4x, 500ms) que só preenche as fotos que ainda faltavam, sem sobrescrever as
já capturadas.

## Validação

Suite de testes (100/100) sem regressão — sem teste dedicado para
`_raspar_pacto` por depender de Playwright/rede real; validado de fato só no
run seguinte do GitHub Actions.

## Limitação à parte, não corrigida

2 lotes de pesados/agro (trator/plaina) nem aparecem na listagem
`/leilao/{cidade}-ceara` mesmo com scroll bem mais agressivo — sugere que o
Pacto tem múltiplos "leilões" concorrentes por cidade e a listagem agregada
nem sempre traz todos os lotes/categorias. Fica como pendência de cobertura,
não de foto.

Nota: este bug e sua correção (seletor de foto) ficaram obsoletos pela
reescrita completa do parser em 2026-09-24, quando o site do Pacto foi
refeito — ver [PACTO_REGRESSAO_2026-09.md](PACTO_REGRESSAO_2026-09.md). O
retry de 4x foi mantido na reescrita.
