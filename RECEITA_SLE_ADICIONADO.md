# Receita Federal (SLE) — adicionada como fonte (2026-09-03)

> **Atualização 2026-09-08 — eletrônicos entraram no escopo.** Antes só
> veículo/máquina era raspado; agora `_raspar_receita_sle` também traz os
> lotes de eletrônico (celular, áudio/vídeo, informática, videogame) na
> categoria nova `eletronicos` (ícone 📱). Decisão do dono: trazer **tudo**,
> sem piso de valor, sem selo de "vedada a comercialização". Detalhes na
> seção "Eletrônicos (2026-09-08)" no fim do arquivo.

Item da tabela de candidatos avaliada em 2026-09-03 (Receita Federal, Copart,
Freitas Leiloeiro, VIP Leilões, JUCEC). Só a Receita Federal entrou; ver
BACKLOG do `CLAUDE.md` para o motivo dos outros terem ficado de fora.

## O que é

- **SLE — Sistema de Leilão Eletrônico** (`www25.receita.fazenda.gov.br/sle-sociedade`),
  onde a Receita Federal leiloa mercadoria apreendida (importação irregular,
  contrabando, veículo sem documentação etc.).
- A **DRF Fortaleza** (órgão `317900`) é a unidade que cobre o Ceará — mas
  cobre também **Piauí e Maranhão** (3ª Região Fiscal). O campo `cidade` do
  edital é só a sede administrativa, **não** a localização do lote: um
  edital "FORTALEZA" pode ter caminhão depositado em São Luís/MA. Ver seção
  "Filtro CE" abaixo — é o ponto mais importante deste scraper.
- Modelo de **proposta fechada**, não lance ao vivo: os interessados mandam
  proposta num prazo, depois tem uma sessão de classificação/lances. Não dá
  pra saber o "lance atual" em tempo real — `lance_atual` aqui é o **valor
  mínimo de venda** (mesma convenção já usada quando MJ/CelsoCunha/
  HastaPública não têm lance registrado).
- Um edital típico tem centenas de lotes, mas **~93% é eletrônico**
  (celular, TV, componente) — fora do escopo de um monitor de veículo/
  imóvel/máquina. Amostra real (edital `0317900/000003/2026`, 411 lotes):
  219 CELULAR/ACESSÓRIO + 165 ELETRÔNICO/ÁUDIO/VÍDEO = 384 eletrônicos;
  só 10 eram veículo/máquina (8 CAMINHÃO/ÔNIBUS, 1 VEÍCULO, 1 MOTOCICLETA).

## Por que dá pra raspar

- API JSON pública, `.gov`, **sem Cloudflare, sem cookie/sessão** —
  confirmado com `curl` "cru" (sem apoio de navegador nem headers especiais
  além de User-Agent/Accept). Mesma faixa do MJ Leilões/Celso Cunha/
  HastaPública: `requests` puro, sem Playwright, sem proxy.
- Três endpoints, todos JSON limpo:
  - `GET /api/editais-disponiveis` → todos os editais abertos no Brasil,
    agrupados por `situacao` (2 = aberto p/ proposta — o único que interessa;
    8 e 15 são estados pós-encerramento).
  - `GET /api/edital/{orgao}/{num}/{ano}` → `listaLotes[]` com `tipo`,
    `valorMinimo`, `valorAvaliacao` por lote (sem descrição textual).
  - `GET /api/lote/{orgao}/{num}/{ano}/{nrAtribuido}` → detalhe do lote:
    `itensDetalhesLote[].descricao` (texto livre com marca/modelo/ano/placa/
    **endereço do depósito**) e `imagens[].src`.

## Filtro CE (o ponto crítico)

**Nunca confia no campo `cidade` do edital.** Cada lote só entra se o texto
da própria `descricao` citar um endereço com `/CE` (`_rf_cidade_ce`,
mesma lógica anti-falso-positivo já usada no Celso Cunha). Testado com os
10 lotes de veículo/máquina do edital de Fortaleza:

| Lote | Tipo | Endereço na descrição | Resultado |
|---|---|---|---|
| 38–42 (5 lotes) | CAMINHÃO/ÔNIBUS | Rua Trairi, 1500, Pedras, **Fortaleza/CE** | ✅ entra |
| 296 | VEÍCULO | Av. Daniel de La Touche, Coama, **São Luís/MA** | ❌ descartado |
| 297 | MOTOCICLETA | mesmo depósito, **São Luís/MA** | ❌ descartado |
| 366 | CAMINHÃO/ÔNIBUS | sem endereço na descrição (sem evidência) | ❌ descartado |
| 404–405 | CAMINHÃO/ÔNIBUS | Rua João Cabral, Vermelha, **Teresina/PI** | ❌ descartado |

Ou seja: de 10 lotes "de Fortaleza", só **metade** era fisicamente do Ceará.
Sem esse filtro por lote, a fonte contaminaria o produto com veículo do
Maranhão e do Piauí carimbado como CE.

## Como o scraper funciona (`_raspar_receita_sle`)

1. `GET /api/editais-disponiveis` → filtra `situacao == 2` (aberto) e
   `cidade == "FORTALEZA"` (única unidade da RFB no CE).
2. Para cada edital: `GET /api/edital/{orgao}/{num}/{ano}` → filtra
   `listaLotes` por `tipo` (regex `_RF_TIPO_RE`: caminhão/ônibus/veículo/
   automóvel/moto/trator/máquina/reboque/embarcação/equipamento) — os
   lotes de eletrônico/têxtil/bazar nem chegam a baixar o detalhe.
3. Para cada lote candidato: `GET /api/lote/...` → junta
   `itensDetalhesLote[].descricao`, exige `/CE` no texto (senão descarta),
   extrai marca/modelo/ano com um parser dedicado (`_rf_parse_veiculo` —
   formato de dump RENAVAM/DETRAN, bem diferente do "MARCA/MODELO - ANO:"
   da Soleon/MJ) e pega a primeira foto de `imagens[]`.
4. `lance_atual` = `valorMinimo`; `data_leilao` = `dataAberturaLances` do
   edital. FIPE/ref de mercado + análise de IA (cacheada) + `_lote_dict`,
   igual às outras fontes. `fonte = "receita_sle"`; label no dashboard =
   "Receita Federal".

## Teste com dados reais (2026-09-03)

Edital `0317900/000003/2026` (Fortaleza, aberto, sessão de lances prevista
28/09/2026): **5 lotes extraídos**, todos confirmados Fortaleza/CE —

- Caminhão Volvo VM 260 6X2R (2008) — mín. R$ 40.000
- Caminhão VW 7.90 S (1991) — mín. R$ 10.000
- Caminhão M.Benz Actros 2546 LS (2011) — mín. R$ 40.000
- Carreta semirreboque Randon (2007) — mín. R$ 10.000
- Caminhão Ford Cargo 815 E (2009) — mín. R$ 40.000

## Limitações conhecidas

- `_rf_parse_veiculo` é um parser heurístico sobre texto livre de
  cadastro veicular (formato inconsistente entre lotes — às vezes tem
  "ANO/MODELO dddd/dddd", às vezes só "ANO FAB dd" com 2 dígitos, às vezes
  a ordem marca/modelo vem invertida como "SR/RANDON"). Extrai bem o ano;
  marca/modelo às vezes carrega ruído (placa, código de chassi) — mesmo
  nível de tolerância que os parsers da Soleon/MJ para casos difíceis.
- Só cobre a DRF Fortaleza. Não cobre outras unidades da Receita que possam
  eventualmente ter lote avulso no CE fora dessa jurisdição.
- Volume é baixo e depende de apreensão — varia muito de edital pra edital
  (o próximo pode ter 0 ou 20 veículos em Fortaleza).

---

## Eletrônicos (2026-09-08)

### O que mudou

`_raspar_receita_sle` deixou de ser só veículo/máquina. Agora o filtro de
`tipo` tem **dois baldes**:

- `_RF_TIPO_RE` — veículo/máquina (inalterado).
- `_RF_TIPO_ELETRONICO_RE` — `CELULAR | ELETR.NIC | .UDIO | V.DEO |
  INFORM.TICA | VIDEOGAME | COMPUTADOR | NOTEBOOK | TABLET | COMPONENTE
  ELETR` (o `.` cobre a vogal acentuada venha como `Ô`/`O` ou como mojibake).

Ficam **de fora**: têxtil, produto mineral/químico, bazar, utensílio
doméstico — sem valor de revenda relevante pro produto.

Amostra real (edital `0317900/000003/2026`, 411 lotes): **386 eletrônicos**
(219 CELULAR/ACESSÓRIO + 165 ELETRÔNICO/ÁUDIO/VÍDEO + 2 outros) entram agora;
antes entravam só os ~10 de veículo/máquina.

### Filtro CE do eletrônico (diferente do veículo)

A descrição do item de eletrônico **não tem endereço** ("SMARTPHONE APPLE
IPHONE 14 PRO 128GB NS:..."), então o `_rf_cidade_ce` (que exige `/CE` no
texto) não serve. O campo `cidade` do lote é **sempre** `FORTALEZA` (sede da
DRF), mesmo pra item fisicamente em São Luís/MA ou Teresina/PI — confirmado.

O sinal confiável é o **`recintoArmazenador`** dos itens. `_rf_eletronico_ce`:

- retorna `""` (descarta) se achar marcador de outra UF no recinto/descrição:
  `São Luís`, `Teresina`, `Maranhão`, `Piauí`, `/MA`, `/PI`,
  `IRF PORTO DE SÃO...`;
- senão, trata como CE (o edital é da DRF Fortaleza) e rotula a cidade pelo
  recinto (`DMA DO PORTO DE FORTALEZA` → `Fortaleza/CE`; recinto sem cidade
  no nome, tipo `J. Log Logística` → `Fortaleza/CE` por padrão).

Isso é **mais permissivo** que o filtro de veículo (que exige evidência
positiva de `/CE`), de propósito: recinto sem marcador de fora, em edital da
DRF Fortaleza, é CE.

Teste real (60 primeiros eletrônicos do edital): 60/60 montados, 0 fora do
CE, todos com `valorAvaliacao`. Lotes 300 e 400 (recinto São Luís / Teresina)
corretamente descartados.

### Referência de preço: `valorAvaliacao` no lugar da FIPE

Eletrônico não tem FIPE. A referência é o **`valorAvaliacao` da própria RFB**,
lido do `listaLotes` (o resumo) — no detalhe do lote ele vem `null`, no resumo
vem preenchido. Vira `fipe_valor` / `fipe_str` (`"R$ X (avaliação RFB)"`).
`classificar` e `oportunidade_preco` funcionam normalmente contra ele. Quando
não há avaliação → `"Sem referência"`, igual a veículo sem FIPE.

### Parser `_rf_parse_eletronico(itens)`

Marca/modelo do **primeiro** item. Corta a descrição no primeiro de: `////`,
`"`, `NS:`, `IMEI`, `PAÍS:`, `ORIGEM:`, `ORIG.ESTRANG`, `S/ACESS`,
`SEM CAIXA`, `(RM`, run de 6+ dígitos. Remove o prefixo de tipo
(`SMARTPHONE`, `TELEFONE CELULAR`, `SMARTWATCH (RELOG.INTLG.)`, ...) só se
ainda sobrar marca + modelo. Lote com N itens ganha sufixo `(+N-1 item/itens)`
no modelo; a lista completa continua inteira em `descricao`.

Exemplos: `SMARTPHONE APPLE IPHONE 14 PRO 128GB NS:...` → `("Apple", "Iphone
14 Pro 128Gb")`; `TELEFONE CELULAR XIAOMI REDMI 12 8/256GB PAIS:CHINA...` →
`("Xiaomi", "Redmi 12 8/256Gb")`.

`ano = 0` (não se aplica); o dashboard omite o `📅` quando `ano` é 0.

### IA: prompt dedicado

`analisar()` agora ramifica por `categoria == "eletronicos"` e usa um prompt
próprio — avalia lacrado/novo x usado, "sem caixa/acessórios", risco de
bloqueio de conta (iCloud/Google/MDM), origem estrangeira sem nota. Schema de
resposta:

- `estado`: `LACRADO | USADO | DEFEITO | NAO_INFORMADO`
- `selo`: `📦 Lacrado | 🔧 Usado | 🔴 Com defeito | ⚪ Não informado`

`DEFEITO` entrou na lista de estados que forçam `⚠️ INSPECIONAR` em
`classificar` / `oportunidade_preco` / `orientacao_uso` (junto de
SINISTRADO/BATIDO/SUCATA). Como o crédito Anthropic está esgotado, na prática
todo eletrônico sai hoje com `NAO_INFORMADO` até recarregar.

### Dashboard

Quase nada mudou — as abas e o filtro de categoria já eram data-driven e
`cats_completas` já listava `eletronicos`. Ajustes:

- `pill_estado` reconhece `Lacrado` / `Usado` / `Com defeito`.
- filtro "Estado" ganhou as 3 opções novas.
- card omite `📅 {ano}` quando `ano == 0`.
- bloco de preço já tratava `fipe == 0` → "Indisponível"; o rótulo
  "FIPE / Referência" já era genérico o bastante.

### Custo no run

`candidatos` do edital de exemplo pula de ~10 para ~396 → ~386 GETs de
detalhe a mais (0,2s de sleep entre eles) ≈ +2–3 min por run. Dentro do
timeout de 90 min do workflow.
