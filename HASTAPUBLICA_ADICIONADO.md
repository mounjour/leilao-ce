# HastaPública — adicionada como fonte (2026-09-03)

Item do backlog "achar outro leiloeiro que de fato opere no CE" (Sodré Santoro
tinha sido descartado — ver `SODRE_SANTORO_DESCARTADO.md`). Desta vez deu certo:
scraper implementado em `scraper.py` (`_raspar_hastapublica`).

## Quem é

- Plataforma **HastaPública** (`hastapublica.com.br`), leiloeira nacional com
  sede em Ribeirão Preto/SP. Sozinha ela é SP/PR, MAS detém o contrato dos
  **leilões judiciais do TJ-CE** através do leiloeiro **Silvio Cesar Maraschi
  (JUCEC 020)**.
- Esses leilões — e só eles — ficam no **grupo 11** do site
  (`/grupos/11`, rótulo "TJ-CE"). Confirmado: `/agenda` (nacional) tem 0 lotes
  no CE; o grupo 11 tem 100% CE.
- Na investigação (03/09/2026) havia **4 leilões em andamento**: 2 apartamentos
  em Fortaleza (Res. Los Angeles / Aldeota), 1 máquina rebobinadora (2ª Vara
  Cível de Fortaleza) e 1 terreno em Catarina/CE (Comarca de Acopiara).
- Hoje é quase tudo **imóvel** (varas cíveis), mas a plataforma comporta
  veículo/máquina e o scraper trata as três categorias.

## Por que dá pra raspar (ao contrário de MGL/Construbem/Nasar)

- Site **100% renderizado no servidor** (jQuery, plataforma "Prism"), **sem
  Cloudflare** e **sem SPA**. `requests.get()` simples devolve 200 com o HTML
  completo dos lotes.
- Mesma faixa de dificuldade do **MJ Leilões / Celso Cunha**: sem Playwright,
  sem proxy residencial, sem ScraperAPI/Zenrows.
- O portal regional `hastaceara.com.br` existe mas está **vazio** — ignorado.

### Candidatos rejeitados na mesma investigação

- **Nasar Leilões** (`nasarleiloes.com.br`) — sediada em Fortaleza, com bastante
  imóvel no CE (Praia do Futuro, Cocó, Sobral, licitação Caixa). Mas está
  **atrás de Cloudflare** (`cdn-cgi/challenge-platform`); cairia no mesmo
  bloqueio por IP do runner que travou MGL/Construbem/Daniel Garcia. Só viável
  com proxy. Fica no radar se algum dia houver crédito de proxy sobrando.
- **Lopes Leilões / João Lopes Cavalcante** (`lopesleiloes.net.br`, JUCEC
  10/2004) — não chegou a ser validado; terceira opção.
- DETRAN-CE / AMC Fortaleza fazem leilão de veículo mas terceirizam para
  leiloeiros — os últimos usaram o pátio da Celso Cunha, que já raspamos.

## Como o scraper funciona (`_raspar_hastapublica`)

1. `GET /grupos/11` → extrai os IDs de leilão (`/leilao/(\d+)/`).
2. Para cada leilão: `GET /leilao/{id}/x` → confere evidência de CE no texto
   (`_HP_CE_RE`, seguro porque o rodapé da HastaPública não tem endereço) e
   extrai os IDs de lote (`/lote/(\d+)/`).
3. Para cada lote: `GET /lote/{id}/x` e parseia do HTML:
   - **título**: `<h1-4>` que começa com "N.N - " (o prefixo evita pegar o
     `<h4>Faça seu login</h4>` do modal);
   - **categoria**: breadcrumb (`Praça <Top> > <Sub> Leiloeiro`) + palavras-
     chave do título → `imoveis` / `equipamentos` / `caminhoes` / `motos` /
     `carros`; imóvel segue a convenção da Soleon (`marca` = título sem o
     sufixo " - Cidade/CE", `modelo` = cidade, `ano` = 0);
   - **cidade**: `CIDADES_CE` no título/texto, senão `Cidade/CE` do título;
   - **lance**: "Lance Inicial" → "Avaliação do Bem" → "1ª Praça (...)" →
     `_extrair_lance`;
   - **data**: "Encerra em dd/mm/aaaa hh:mm" → "1ª Praça (dd/mm/aaaa)" →
     `_extrair_data_leilao`;
   - **descrição**: bloco "Descrição do Lote:" até "Ônus:/Local Depositado:";
   - **foto**: primeira imagem `s3-sa-east-1.amazonaws.com/cdnhp/content/...`.
4. FIPE/ref de mercado + análise de IA (cacheada) + `_lote_dict`, igual aos
   outros. `fonte = "hastapublica"`; label no dashboard = "HastaPública".

## Limitações conhecidas

- Só cobre o **grupo TJ-CE** (judicial). Se a HastaPública passar a ter
  leilão extrajudicial/Caixa no CE fora do grupo 11, não é pego.
- Volume baixo (~4 leilões, ~1 lote cada) — normal para leilão judicial.
- Descrições às vezes vêm com typo da origem (ex.: "M APARTAMENTO" em vez de
  "UM APARTAMENTO") — copiado como está.
