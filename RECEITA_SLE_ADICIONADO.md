# Receita Federal (SLE) — adicionada como fonte (2026-09-03)

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
