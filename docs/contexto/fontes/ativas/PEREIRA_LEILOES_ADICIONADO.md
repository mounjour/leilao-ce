# Pereira Leilões — adicionada como fonte (2026-09-18)

Site https://www.pereiraleiloesce.com.br/, sugerido pelo dono. Implementado
reaproveitando `_raspar_soleon` em `scraper.py` (mesma função já usada por
Construbem e Daniel Garcia).

## Por que reaproveitar o scraper da Soleon

A investigação inicial ia seguir o padrão do Grupo Lance (scraper dedicado,
requests direto), mas o HTML do site trouxe
`<meta name="author" content="SOLEON Soluções para Leilões Online">` e as
mesmas URLs `/leilao/{id}/lotes` e `/item/{id}/detalhes` já usadas por
Construbem e Daniel Garcia — é o mesmo backend/plataforma "Soleon", só um
cliente diferente. Escrever um parser novo do zero duplicaria a lógica de
categorização, extração de lance/data e filtro de CE que já existe e está em
produção. `_raspar_soleon` virou `_raspar_soleon(base, fonte, vistos,
usar_proxy=True)`; Pereira entra com `usar_proxy=False` porque, diferente de
Construbem/Daniel Garcia, o site **não** está atrás de bloqueio de
Cloudflare no IP do GitHub Actions (testado com `requests.get()` cru, sem
proxy, 200 OK com HTML completo) — rotear por Zenrows/ScraperAPI aqui só
gastaria crédito à toa.

## O que o site tem

- Leiloeiro cearense com foco quase exclusivo em bens de **órgãos públicos**
  do Ceará (prefeituras municipais, UFC) — veículos, sucata, equipamentos e
  eventualmente imóveis/terrenos. Histórico de leilões encerrados mostra
  dezenas de prefeituras (Cruz, Santa Quitéria, Jucás, Tauá, Ipaporanga,
  Piquet Carneiro, Bela Cruz, Rerriutaba, Pires Ferreira, Fortaleza...).
- No momento da implementação (18/09/2026): 1 leilão ativo (Prefeitura
  Municipal de Barroquinha), 17 lotes — 12 veículos + 5 diversos (sucata de
  veículo sem documento, 2 retroescavadeiras, pirâmides de material
  hospitalar/informática). Sem imóvel ativo nesse momento.
- Cadência **intermitente**: pelos leilões encerrados, passam-se
  tipicamente semanas a poucos meses entre um leilão novo e outro (não é
  fluxo contínuo como Francisco Freitas/Spy Leilões). Ver seção "Health
  check" abaixo.

## Parsing (reaproveitado, sem código novo de extração)

- `_parse_soleon_lots_from_listing` já lida com o card padrão da Soleon
  (`Lote NNN` + link `/item/{id}/detalhes` + `Descrição:` + `Maior Lance`) —
  validado rodando contra o HTML real de `/lotes/veiculo` e `/lotes/diversos`
  (12 e 5 lotes extraídos corretamente, título/cidade/lance batendo com o
  que a página mostra).
- Cidade: o site não expõe um campo "Cidade:" nos cards nem no filtro
  (dropdown vem vazio, `address_cidade: null` — leilão de prefeitura, sem
  cadastro de cidade por lote) — cai no fallback genérico `"CE"` do parser
  compartilhado, exceto quando a cidade aparece por coincidência no texto
  (ex.: "Fortaleza/CE" reconhecido via `CIDADES_CE`).
- Categoria: reaproveita o `detectar_categoria`/branches já existentes em
  `_raspar_soleon` (imóvel, equipamento, caminhão, moto, "diversos" vira
  `equipamentos`, senão carro). Bug pego na validação: o título
  "RETROECAVADEIRA XC870BR-1" tem erro de digitação no próprio site (falta
  o "s" de "escavadeira") e não batia com a palavra-chave
  `retroescavadeira` em `PALAVRAS_MAQUINA` — adicionado `retroecavadeira`
  (o typo) na lista, com teste novo
  `TestDetectarCategoria.test_equipamento_typo_retroecavadeira` em
  `tests/test_scraper.py`.
- Lotes genéricos ("DIVERSOS", "SUCATAS DE VEÍCULOS SEM DOCUMENTOS", pirâmide
  de material hospitalar/informática) são filtrados como lixo por
  `_soleon_lote_util` — mesmo comportamento já usado pra Construbem, sem
  mudança.

## Health check

`pereira` foi colocado em `FONTES_ESPERADAS_ZERO` (scraper_health.py), **não**
em `FONTES_ATIVAS`: como é um leiloeiro único com leilões esporádicos (ver
cadência acima), ficar com 0 lote por vários runs seguidos entre um leilão e
outro é esperado, não indica fonte quebrada — colocar em `FONTES_ATIVAS`
geraria alerta de WhatsApp falso-positivo toda vez que o leilão de
Barroquinha encerrar e não houver outro ainda aberto. Promover pra
`FONTES_ATIVAS` se a cadência real (observada ao longo dos runs) se mostrar
mais constante do que o histórico de encerrados sugere.

## Testes

Sem teste de parsing dedicado (reaproveita `_parse_soleon_lots_from_listing`
e `_raspar_soleon`, já em produção e sem suíte própria — mesmo padrão da
Maria Fixer, que reaproveitou helpers do Francisco Freitas sem teste novo).
Único teste novo é o de categorização do typo (`retroecavadeira`), já citado
acima.
