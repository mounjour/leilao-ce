# MJ Leilões: lote duplicado e título quebrado (corrigido 2026-09-25)

## Sintomas

Cada lote do MJ Leilões saía 2x no `leiloes.json`, e marca/modelo de
ônibus/ambulância vinham zerados.

## Causas raiz

**(A) Duplicação (bug desde ~06/2026).** O site do MJ Leilões expõe o mesmo
lote em duas URLs: com e sem o fragmento `#lances`. O scraper tratava as duas
como lotes diferentes.

**(B) Título quebrado.** `_mj_parse_titulo` cortava a string em 120
caracteres, o que zerava marca/modelo de veículos com título longo (ônibus,
ambulância). Também não removia sufixos como `, Cor:`/`Combustível:`/
`Chassi:`/`Capacidade:` nem "Caminhão"/"Ônibus" do campo modelo.

**(C) Categoria errada.** `' cargo'` estava em `PALAVRAS_MOTO`, então
"Caminhão Ford Cargo" virava moto.

## Correção

- `_mj_normalizar_lote_path`/`_mj_lote_paths` removem fragmento e query da
  URL antes de deduplicar (32 → 16 lotes reais). A URL canônica é a sem
  fragmento; favoritos já casavam porque `favorites._normalizar_url`
  descarta o fragmento.
- `_mj_parse_titulo` sem o limite de 120 chars; corta os sufixos acima.
- `PALAVRAS_CAMINHAO` ganhou `caminhao`/`onibus`/`ford cargo`.
- Sucata eletrônica, hospitalar/escolar e aparelhos vão para `eletronicos`
  (decisão do dono, sem FIPE).

## Validação

Ao vivo: 16 lotes únicos, 0 sem marca/modelo, lance e foto 16/16. Testes:
189/189.

## Limitações conhecidas

Marca "Benz" fica incompleta porque o título do site omite "Mercedes".
`leiloes.json` commitado só reflete a correção após o próximo run do GitHub
Actions.
