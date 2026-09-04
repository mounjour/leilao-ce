# Francisco Freitas Leilões — adicionada como fonte (2026-09-04)

Investigação pedida sobre "Freitas Leiloeiro" (item da tabela de candidatos
de 2026-09-03). Achei DOIS leiloeiros diferentes com nome parecido — só um
entrou.

## ⚠️ Nota sobre robots.txt

O `robots.txt` do site tem o bloco padrão do Cloudflare "AI Bots", que
desautoriza nominalmente uma lista de crawlers de IA/treinamento —
`ClaudeBot`, `GPTBot`, `Google-Extended`, `CCBot`, `Amazonbot`, `Bytespider`,
`meta-externalagent`, `Applebot-Extended`, `CloudflareBrowserRenderingCrawler`.
Para bots em geral (`User-agent: *`) o site é `Allow: /`. O scraper não se
identifica como nenhum desses — usa o mesmo User-Agent de navegador que as
outras fontes do projeto — e a finalidade é monitoramento de leilão pro
produto, não indexação/treinamento de IA. Registrado aqui por transparência
(quem escreveu o scraper foi o Claude).

## `freitasleiloeiro.com.br` (Santo André/SP) — investigado e descartado

Leiloeiro Sérgio Villa Nova de Freitas. **Não é o mesmo leiloeiro** do que
entrou. Claramente paulista:
- Veículos: 0% CE — só 3 pátios, todos em SP (Utinga, Santo André, Santa
  Bárbara). Confirmado no detalhe de um lote ("Local do leilão: Santo
  André/SP").
- Imóveis: 1 de ~92 é no CE (Sobral, terreno em loteamento — status "EM
  LOTEAMENTO", nem está aberto pra lance ainda).

Mesmo padrão do Sodré Santoro: inventário nacional cheio, quase nada no
Ceará. Descartado.

## `franciscofreitasleiloes.com.br` — a fonte que entrou

- Leiloeiro **Francisco Freitas**, plataforma de marca **"Norte Nordeste
  Leilões"** (`nortenordesteleiloes.com.br` — mesmo backend, redireciona
  pro mesmo site).
- **91 lotes ativos no Ceará** no momento da investigação (04/09/2026), de
  177 lotes ativos no total — mais da metade de todo o inventário do
  leiloeiro é CE. Maior fonte já adicionada ao projeto:
  - 12 veículos (5 carros, 2 motos, 3 ônibus, 1 reboque/semirreboque, 1
    caminhão)
  - 60 imóveis (sítios, fazendas, casas, apartamentos, terrenos, prédios
    comerciais, galpões)
  - ~9 "bens diversos" aproveitáveis (empilhadeira, máquinas industriais de
    costura, equipamento de irrigação, máquina de corte) — o resto (TV,
    combustível, óculos, cadeira odontológica, cotas sociais...) fica de
    fora por não se encaixar em nenhuma categoria do produto.

## Por que dá pra raspar

- API JSON pública, sem Cloudflare-challenge nem sessão/cookie — confirmado
  com `curl` cru (GET e POST).
- Campos **estruturados e diretos** — melhor fonte já integrada nesse
  quesito:
  - `nm_estado`/`nm_cidade`: cidade/UF do lote prontos, sem precisar caçar
    endereço em texto livre (diferente da Receita Federal, que exige regex
    sobre a descrição).
  - `nm_categoria`/`nm_subcategoria`: categoria pronta, sem inferência por
    palavra-chave (Veículos/Imóveis/Bens diversos/Semoventes, com
    subcategoria tipo Carros/Motos/Ônibus/Sítios/Casas...).
  - `vl_lance`: lance **atual real** quando já tem gente lançando (não só
    valor mínimo — diferente de HastaPública/Receita Federal, que são
    proposta fechada).
  - `fotos[]`, `anexos[]` (edital/laudo em PDF), `dt_fechamento`.
- Título do veículo já vem quase no formato Soleon: `"MARCA/MODELO - ANO -
  Cidade/UF"` (ex.: `"Ford/Fiesta HÁ 1.5L SB - 2016 - Juazeiro do
  Norte/CE"`) — reaproveita `_extrair_veiculo_de_titulo` já existente.

### Detalhe técnico: `get-leiloes` não filtra de verdade

Os parâmetros `estado=` e `tipo=` do endpoint `/core/api/get-leiloes` são
**ignorados pelo backend** — testado enviando `estado=CE`, `estado=SP`,
`estado=` (vazio) e sem o parâmetro: sempre o mesmo total (75 leilões).
Por isso o scraper busca a lista **completa** de leilões ativos e filtra
**lote a lote** via `POST /core/api/get-lotes?leilao_id=X`, que traz
`nm_estado` confiável por item.

### O site está em migração

Banner "MUDANÇA DE SITE FRANCISCO FREITAS LEILÕES" na home; a grade de
leilões do front-end está quebrada (erro JS "Can not detect viewport
width", vários 404/400, "Carregando leilões..." nunca resolve — confirmado
via console do navegador). A API por trás funciona normal. A URL do lote
usada (`/leilao/index/leilao_id/{id}/lote/{lote_id}`) é o padrão legado do
site, achado via indexação do Google e confirmado com HTTP 200 — pode não
renderizar direito pro usuário final até a migração terminar, mas é o link
correto assim que o front-end for corrigido.

## Como o scraper funciona (`_raspar_francisco_freitas`)

1. `GET /core/api/get-leiloes?pg=N&itens_pagina=100` paginado até esgotar
   `totalPages` (hoje sempre retorna os mesmos 75 leilões ativos).
2. Para cada leilão: `POST /core/api/get-lotes?leilao_id={id}` → filtra os
   itens com `nm_estado == "CE"`.
3. Categoria via `nm_categoria`/`nm_subcategoria` (`_ff_categoria`); veículo
   sem categoria reconhecida ou "bens diversos" sem palavra-chave de
   máquina/equipamento é descartado.
4. Marca/modelo/ano: veículo usa `_ff_parse_veiculo` (extrai o ano do
   trecho entre os dois primeiros " - ", inclusive formato "AA/AA" com
   conversão de século; reaproveita `_extrair_veiculo_de_titulo` pra
   marca/modelo); imóvel/equipamento segue a convenção Soleon
   (marca=título, modelo=cidade).
5. `lance_atual` = `vl_lance` (lance real) → `vl_lanceinicial` →
   `vl_lanceminimo`. `data_leilao` = `dt_fechamento`. FIPE/ref de mercado +
   análise de IA (cacheada) + `_lote_dict`, igual às outras fontes.
   `fonte = "francisco_freitas"`.

## Teste com dados reais (2026-09-04)

`py_compile` OK. Rodada completa nos 75 leilões ativos: **77 lotes CE**
extraídos sem erro (60 imóveis, 5 caminhões/ônibus/reboques, 5
equipamentos, 5 carros, 2 motos) — as 14 diferenças pro total de 91 são os
"bens diversos" genéricos (TV, combustível etc.) corretamente descartados
por categoria.

## Limitações conhecidas

- Depende do front-end do leiloeiro terminar a migração pra os links de
  lote funcionarem de verdade pro usuário final (a API já funciona).
- `_ff_parse_veiculo` é heurístico como os outros parsers do projeto —
  marca/modelo podem carregar ruído em casos difíceis.
- Volume real depende do inventário do leiloeiro no momento — pode variar
  bastante entre execuções do scraper.
