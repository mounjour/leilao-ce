# Health check do scraper

Como `scraper_health.py` vigia as fontes de dados e quando ele avisa o dono
por WhatsApp.

## Contagem zerada (2026-09-08)

`scraper_health.py` é chamado no fim de `raspar_leiloes()` (best-effort,
nunca derruba o run). Mantém um placar por fonte em `scraper_health.json`
(commitado junto do `leiloes.json`; o runner do GitHub Actions é efêmero).

Quando uma fonte de `FONTES_ATIVAS` (leilo/mega/pacto/montenegro/mj/
receita_sle/francisco_freitas/spy_leiloes/maria_fixer/grupo_lance) fica 3
runs seguidos com 0 lote, loga `::warning::` e manda 1 WhatsApp pro dono via
`alertas.send_whatsapp(origem="scraper_health")`; re-alerta a cada ~14 runs
enquanto seguir zerada; zera ao voltar.

`FONTES_ESPERADAS_ZERO` (mgl/construbem/danielgarcia/celsocunha/pereira) são
rastreadas mas nunca alertam por contagem zero — são fontes com leilões
esporádicos ou bloqueadas por infra conhecida, não fontes quebradas. Tirar
da lista quando uma delas voltar a produzir de forma consistente.

Secret `OWNER_WHATSAPP` no passo "Rodar scraper" do workflow (ausente = só
`::warning::`, sem WhatsApp). O health check nunca falha o job de propósito.

Testes: `tests/test_scraper_health.py`.

## Campos zerados em massa (2026-09-24)

Contagem de lotes sozinha não pega regressão de qualidade dos dados: em
21/09 o Pacto continuou entregando 29 lotes/run, mas todos com `lance_atual`
0 e `foto` vazia (ver
[fontes/incidentes/PACTO_REGRESSAO_2026-09.md](fontes/incidentes/PACTO_REGRESSAO_2026-09.md))
— só a contagem era checada, então isso passou batido por dias.

`scraper_health.py` agora também vigia `lance_atual > 0` e `foto` por fonte
de `FONTES_ATIVAS` (mínimo de 5 lotes pra fonte entrar na checagem). Guarda
em `scraper_health.json` a taxa de referência (última leitura saudável) por
campo; se a taxa cai ≥ 50 pontos abaixo da referência (referência ≥ 50%) por
2 runs seguidos, loga `::warning::` e manda 1 WhatsApp (mesmo esquema de
re-alerta do zerado). Campo que a fonte nunca preenche (ex.: foto do
Construbem) não alerta.

Backtest nos commits reais do período mostrou que essa checagem teria
alertado o Pacto em 22/09, sem falso positivo em nenhuma outra fonte.

Testes novos em `tests/test_scraper_health.py` (131/131 no total na época).
