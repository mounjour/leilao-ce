# Investigação de novas fontes/leiloeiros (2026-09-14)

Segunda rodada de busca por leiloeiros/plataformas com atuação no CE
(Fortaleza e interior), cruzando cada candidato com Reclame Aqui, listas de
sites falsos (ALEIBRAS/Leilão Seguro) e checagem direta do site para
confirmar lotes ativos de fato no Ceará. Só investigação — **nada
implementado ainda**.

## Descartados de saída (duplicados ou já cobertos)

- **cearaleiloes.com.br** → redireciona (301) para
  franciscofreitasleiloes.com.br. Mesma empresa já implementada
  (`_raspar_francisco_freitas`), não é fonte nova.
- **Silvio Cesar Maraschi** (JUCEC 020) → site é hastapublica.com.br. Mesma
  plataforma HastaPública já removida do projeto em 2026-09-11 (ver
  STATUS).
- **Mega Leilões** (megaleiloes.com.br) → já coberto por `_raspar_mega`.
  Existe uma "Mega Leilões MS" (megaleiloesms.com.br) que parece marca
  regional separada — não investigada a fundo, baixa prioridade.

## Candidatos novos, por prioridade

### 1. Grupo Lance / Lance Leilões (grupolance.com.br, lancese.com.br) — prioridade alta

- Empresa: Lance Alienações Virtuais LTDA, CNPJ 23.341.409/0001-77 (visível
  no rodapé).
- 9 lotes ativos no CE no momento da checagem: Aquiraz, Juazeiro do Norte
  (3), Iguatu, Maranguape, Pedra Branca, Fortaleza, Crato. Datas de leilão
  de agosto/2026 a fevereiro/2027.
- Reclame Aqui tem queixas, mas de atendimento/pós-arrematação (comum no
  setor), não de golpe/site falso.
- ⚠️ Não confundir com **"Lance Maior Leilões"** (empresa diferente, SP,
  JUCESP) — essa inclusive tem site clonado por golpistas.

### 2. Spy Leilões (spyleiloes.com.br)

- Empresa: Spy Leilões Serviços Digitais, CNPJ 36.133.974/0001-90.
- 195 lotes ativos em Fortaleza/CE — volume grande; é portal agregador
  (reúne leilões de vários leiloeiros/bancos).
- Nenhum indício de golpe, só 1 reclamação de propaganda enganosa.
- ⚠️ Risco técnico (não de fraude): por ser agregador de imóveis retomados
  de banco, o mesmo imóvel tende a aparecer também em outros portais
  (Leilão Imóvel, Mega, etc.) — precisaria dedup por matrícula do
  imóvel/edital, não só por URL, para não duplicar no `leiloes.json`.

### 3. Nasar Leilões (nasarleiloes.com.br) — reavaliar

- Leiloeiro próprio sediado em Fortaleza (Av. Carapinima, 1751). Nenhuma
  reclamação de golpe encontrada.
- Já investigado antes e descartado por Cloudflare bloquear o IP do GitHub
  Actions — mas isso foi antes da solução Zenrows Scraping Browser
  (`connect_over_cdp`) que hoje resolve exatamente esse problema pro MGL
  (ver docs/contexto/MGL_SCRAPER_PENDENTE.md). Vale reaproveitar a mesma
  abordagem aqui.

### 4. Leilão Imóvel (leilaoimovel.com.br)

- Portal agregador nacional, com seção dedicada a Fortaleza/CE; lista o
  próprio Nasar como leiloeiro parceiro.
- Só reclamações de precisão de anúncio e dado pessoal, nada de fraude
  confirmada.
- Mesmo risco de duplicação que o Spy Leilões, e menor prioridade por não
  ser fonte primária (já expõe lotes de leiloeiros que talvez valha raspar
  direto).

## Não recomendados

- **Alfa Leilões** — reclamações mais sérias e recorrentes (leiloeiro
  "abandona" cliente após receber comissão, descumprimento de decisão
  judicial de reembolso). Registrado em SP (JUCESP), sem evidência de
  volume relevante no CE. Risco reputacional pra vincular ao produto.
- **Italo Leilões** — nenhuma evidência de lotes no CE. Sem dado suficiente
  pra justificar o esforço de scraper.
- **Átrio Leilões** — só 1 lote em Fortaleza via busca (baixo volume
  aparente), sede em Barueri/SP, sem confirmação de CNPJ nem leiloeiro na
  página do lote. Fica no radar, não prioritário.

## Ordem de implementação sugerida

1. **Grupo Lance** — melhor sinal: CNPJ claro, lotes CE confirmados agora,
   sem sinal de golpe.
2. **Spy Leilões** — mais volume, mas exige lógica de dedup entre fontes.
3. **Nasar Leilões** — reaproveitando a solução Zenrows do MGL.

Nenhum plano técnico (estrutura de API/HTML, filtro CE, dedup) foi
detalhado ainda — a fazer quando o dono priorizar qual fonte implementar
primeiro.
