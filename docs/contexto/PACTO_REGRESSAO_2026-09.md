# Pacto: regressao do scraper apos redesenho do site (2026-09-24)

## Sintoma
Nos runs de 2026-09-21 em diante (commits 351944a, 25188a3, 911a7d4, 105a4aa) os
lotes da fonte `pacto` vieram com `lance_atual = 0` e `foto = ""` em 100% dos
casos, `marca` = nome do leilao (`Leilao-De-Pesados-E-Agro-25-09-2026`),
`modelo` = "marca + modelo" e FIPE zerada. O health check nao alertou porque so
olha a contagem de lotes (29 > 0).

## Causa raiz
O site pactoleiloes.com.br foi refeito. Nao era so o segmento novo na URL:

| Campo | Antes | Depois |
|---|---|---|
| Listagem | `/leilao/{cidade}-ceara` | redireciona para `/leilao/ceara/`; uma pagina por categoria (`/leilao/ceara/motos/`) |
| Card / href | `a[href*="/ano."]` -> `/leilao/eusebio-ce/<cat>/[<leilao>/]<slug>/ano.AAAA/<uuid>` | `a.lote-card-link` -> `/lote/<uuid>/` (sem categoria, marca, modelo nem ano) |
| Marca/modelo | slug da URL por indice fixo | `.lote-card-nome` = "Honda/Nxr 160 Bros ABS" |
| Lance | texto do card com centavos | `.valor-card` = "R$ 16.100" **sem centavos** (`_extrair_lance` exige `,dd` e devolvia 0) |
| Foto | `background-image` de `.q-img__image` | `<img class="lote-card-img" src=...>` |
| Ano | `ano.AAAA` na URL | texto `25 /26` (fab/modelo, 2 digitos) |
| Data do leilao | countdown | `Sab, 26/09/20 • 09:30h` -- o site corta o ano para 2 digitos ("20" em vez de "26") |

O seletor antigo (`/ano.`) nao acha mais nenhum card no site atual.

## Correcao (scraper.py, bloco "SCRAPER PACTO LEILOES")
- Raspa `/leilao/ceara/{carros,motos,pesados,utilitarios,sucatas,equipamentos,imoveis}/`.
  A pagina geral omite 1 lote (36 vs 37 somando as categorias).
- Funcoes puras testaveis: `_pacto_parse_href` (novo e legado, ancorado em `ano.`,
  nunca por indice absoluto), `_pacto_parse_valor`, `_pacto_parse_ano`,
  `_pacto_parse_data` (infere o ano), `_pacto_parse_card`.
- Nome sem "/" (equipamentos/implementos) vira modelo, com marca "Outros".
- Foto `/fotos-modelo/` (imagem generica) continua virando `""`; retry de
  lazy-loading (commit e5ca64a) mantido em `_pacto_coletar`.
- Testes: `TestPactoParseHref`, `TestPactoParseCampos`, `TestPactoParseCard` em
  `tests/test_scraper.py` (textos reais de cards de 2026-09-24).

## Validacao ao vivo (2026-09-24, `_raspar_pacto` isolado, IA stubada)
37 lotes (= total do site: 16 motos + 11 carros + 10 pesados), 37 com lance > 0,
37 com ano e data do leilao, 32 com foto real (os 5 sem foto usam a imagem
generica do site), 28 com FIPE, 16 com km (so os que informam km).

## Efeitos colaterais a saber
- **URL do lote mudou** para `https://www.pactoleiloes.com.br/lote/<uuid>/`.
  Favoritos (`lote_url`) e cache de analise de lotes Pacto salvos com a URL
  antiga deixam de casar. Os lotes do Pacto giram a cada semana, entao o
  impacto e pequeno, mas favoritos de lotes ainda ativos somem da lista.
- **Cidade fixa "Eusebio/CE"**: o card so mostra "CE" e o unico patio listado
  no CE e o de Eusebio. Se aparecer outra cidade no filtro "Cidades em CEARA"
  do site, ler a cidade no detalhe do lote.
- `leiloes.json` commitado so reflete a correcao apos o proximo run do Actions.

## Fora de escopo (registrado)
- Pacto e Leilo listam lotes dos mesmos leiloes (o Iveco Stralis aparece nos
  dois). RESOLVIDO em 2026-09-25: mesmo uuid de lote nos dois sites, dedup exato
  por uuid, Pacto canonico. Ver `LEILO_REDESIGN_2026-09.md`.
- Health check de "campos-chave zerados em massa" por fonte (lance/foto/marca)
  teria pego esta regressao no primeiro run: proposta para outra sessao.
