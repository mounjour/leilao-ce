# Maria Fixer Leilões — adicionada como fonte (2026-09-16)

Leiloeiro `mariafixerleiloes.com.br`, adicionado a pedido do dono. Implementado
como `_raspar_maria_fixer` em `scraper.py`.

## Por que essa fonte

- 16 lotes ativos no CE vistos no contador de filtro do site na investigação
  (Veículos, Bens Diversos, Imóveis, ao lado de DF/MA/MS/SC/SP). Confirmado
  com dado real: 77 itens efetivamente coletados (mais que o contador porque
  itens de sucata judicial reaparecem em 2ª/3ª rodada de leilão com lance
  decrescente — cada rodada é um `leilao_id` distinto, então não é
  duplicata).

## Como o site funciona (mesma plataforma do Francisco Freitas)

- **Mesmo backend "vlance"** usado por
  `docs/contexto/FRANCISCO_FREITAS_ADICIONADO.md` — confirmado testando a
  API ao vivo em 2026-09-16: mesmos endpoints (`core/api/get-leiloes`,
  `core/api/get-lotes?leilao_id=X` via POST) e o mesmo schema de campos
  (`nm_estado`, `nm_cidade`, `nm_titulo_lote`, `nm_categoria`,
  `nm_subcategoria`, `vl_lance`, `vl_lanceinicial`, `dt_fechamento`,
  `fotos`...). Por isso `_raspar_maria_fixer` **reaproveita os helpers
  genéricos** já escritos para o Francisco Freitas — `_ff_get`,
  `_ff_categoria`, `_ff_parse_veiculo`, `_ff_html_para_texto`, `_ff_num` —
  nenhum deles hardcoda o domínio da Francisco Freitas, só o nome tem
  prefixo `_ff_`. Só o base URL (`_MF_BASE`) e a chamada de `get-lotes`
  (`_mf_get_lotes`) são específicos do Maria Fixer.
- Sem Cloudflare nem sessão — API JSON pública, `requests` direto.
- `get-leiloes` traz TODOS os leilões ativos do Brasil (33 no teste, não só
  CE) — mesma limitação do Francisco Freitas, o filtro é feito lote a lote
  via `get-lotes` (`nm_estado == "CE"`).
- URL do lote: `/leilao/index/leilao_id/<leilao_id>/lote/<lote_id>` (mesmo
  padrão do Francisco Freitas).
- Concentração observada: quase tudo em Farias Brito/CE (sucata de
  motocicleta, processo judicial), com 1 imóvel em Caucaia/CE e 1 carro.

## Modelagem dos dados

Idêntica ao Francisco Freitas (mesmos campos, mesmo schema): categoria via
`_ff_categoria` (`nm_categoria`/`nm_subcategoria`/título), marca/modelo/ano
de veículo via `_ff_parse_veiculo` (título no formato
`MARCA MODELO - AA/AA - Cidade/UF`), `lance_atual` = `vl_lance` (fallback
`vl_lanceinicial`/`vl_lanceminimo`), descrição via `_ff_html_para_texto`.
Não filtra por `statuslote_id` (mesmo comportamento já existente para o
Francisco Freitas) — um lote "Vendido" de um leilão que ainda aparece em
`get-leiloes` pode entrar; não é um problema novo introduzido aqui.

## Health check

`maria_fixer` entrou em `FONTES_ATIVAS` (scraper_health.py) — se ficar 3
runs seguidos zerada, alerta o dono via WhatsApp, igual às outras fontes
"requests direto".

## Testes

Sem teste novo dedicado: `_raspar_maria_fixer` reaproveita 100% dos helpers
puros já usados (e não testados) pelo Francisco Freitas — mesma situação
pré-existente, não uma lacuna nova. Validado com smoke test manual contra a
API ao vivo em 2026-09-16 (77 lotes CE, categorias `motos`/`carros`/
`imoveis` corretas). `python -m pytest -q` segue passando (90/90).
