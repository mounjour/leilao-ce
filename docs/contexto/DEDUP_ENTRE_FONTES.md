# Dedup entre fontes (2026-09-16)

Implementa a pendência apontada em
`docs/contexto/INVESTIGACAO_NOVAS_FONTES_2026-09-14.md`: agregadores como
Spy Leilões e Grupo Lance podem trazer o **mesmo imóvel** que um leiloeiro
direto já raspado (Francisco Freitas, Maria Fixer...), só que com uma URL
diferente — o `vistos` (dedup por URL, já existente) não pega isso porque a
URL É diferente entre fontes.

## Estratégia escolhida

`_chave_dedup_entre_fontes` (scraper.py) só gera uma chave quando encontra,
no texto do lote (`descricao` + `modelo`), um **identificador de alta
confiança**:

1. Número de processo judicial, padrão CNJ:
   `NNNNNNN-DD.AAAA.J.TR.OOOO` (ex.: `8500061-18.2025.8.06.0076`, visto em
   descrições da Maria Fixer/Francisco Freitas).
2. Matrícula do imóvel (`Matrícula nº 6.264...`, visto em títulos do Spy
   Leilões e de outros agregadores de imóvel retomado de banco) — só aceita
   com 4+ dígitos, pra não colidir por coincidência com matrículas curtas
   demais.

**Na ausência de um desses dois, a função retorna `None` e o lote nunca é
removido** — decisão deliberada de não tentar dedup por heurística fraca de
título/endereço (formato varia demais entre fontes: "Rua X, 123" vs "Casa
em Bairro Y, Cidade/CE" vs descrição jurídica completa). Um falso positivo
esconderia uma oportunidade real do usuário, o que é pior do que deixar uma
duplicata visível — trade-off explícito a favor de precisão sobre
cobertura.

Isso significa que a cobertura do dedup é parcial: cobre bem leilões
**judiciais** (a maioria tem número de processo no edital/descrição) e
imóveis com matrícula divulgada, mas não pega duplicata entre, por
exemplo, dois agregadores mostrando o mesmo veículo sem nenhum desses
identificadores no texto.

## Onde entra no pipeline

`_remover_duplicatas_entre_fontes(lotes)` roda em `raspar_leiloes()`
**depois** de todas as fontes terem raspado (inclusive Soleon/Construbem/
Daniel Garcia) e **antes** de salvar `leiloes.json`. Mantém a 1ª
ocorrência — como a ordem de chamada em `raspar_leiloes()` já coloca os
leiloeiros diretos antes dos agregadores (Grupo Lance e Spy Leilões
raspados por último, antes só do Soleon), o lote do leiloeiro original é o
que sobrevive quando há colisão de chave.

## Health check não é afetado

`scraper_health.processar()` recebe os lotes **antes** do dedup
(`lotes_brutos` em `raspar_leiloes()`), não a lista final salva no JSON.
Isso evita um falso alarme: se todos os lotes de uma fonte num run
específico coincidissem de já estarem cobertos por outra fonte (dedup
zerando a contagem pós-merge), o health check continuaria vendo a
contagem real de produção daquela fonte, sem confundir "scraper quebrado"
com "lotes mesclados por já aparecerem em outro lugar".

## Testes

`tests/test_scraper.py` — `TestChaveDedupEntreFontes` (extração de
processo CNJ, matrícula, matrícula curta demais ignorada, ausência de
identificador, busca também no campo `modelo`) e
`TestRemoverDuplicatasEntreFontes` (remove duplicata entre fontes
diferentes, mantém a 1ª ocorrência, nunca remove sem identificador,
processos diferentes sobrevivem ambos). Sem rede, funções puras.
