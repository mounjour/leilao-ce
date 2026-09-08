# Plano do Projeto — Achadin Leilões (leilao-ce)

> **Documento de análise/status** · atualizado 08/09/2026
> **Base:** leitura direta do código (`scraper.py`, `scraper_health.py`, `dashboard.py`,
> `auth.py`, `favorites.py`, `alertas.py`, `whatsapp_log.py`), do `CLAUDE.md`, das
> migrations/Edge Functions do Supabase e do histórico do git.
> **Status:** MVP em produção (`leilaoce.streamlit.app`), com cobrança ativa. A dívida
> técnica que existia (sem testes, falha de WhatsApp engolida, fonte morrendo sem alarme)
> foi fechada em 08/09. O que falta é sobretudo **destravar fontes bloqueadas** (crédito de
> proxy/IA). Relatórios, notificação de lote novo e migração do WhatsApp para a API oficial
> ficaram **fora de escopo por decisão do dono** (ver §3 e §14).

SaaS de monitoramento de leilões (carros, motos, caminhões, imóveis, equipamentos) no
**Ceará**. Agrega lotes de vários leiloeiros, cruza com a tabela FIPE, usa IA para avaliar o
estado do item e apresenta tudo num painel único, com favoritos e alerta de mudança de lance
por WhatsApp.

Este documento é a fonte de contexto consolidada do projeto — o `CLAUDE.md` continua sendo o
changelog vivo (atualizado a cada sessão); este arquivo é a "foto" estruturada de onde o
projeto está agora, para orientar as próximas decisões.

## Índice

1. [Contexto atual](#1-contexto-atual)
2. [Objetivos do sistema](#2-objetivos-do-sistema)
3. [Escopo](#3-escopo)
4. [Módulos funcionais](#4-módulos-funcionais)
5. [Fontes de leilão (scrapers)](#5-fontes-de-leilão-scrapers)
6. [Modelo de dados](#6-modelo-de-dados)
7. [Arquitetura técnica](#7-arquitetura-técnica)
8. [Alertas — decisão de canal](#8-alertas--decisão-de-canal)
9. [Roadmap de entrega](#9-roadmap-de-entrega)
10. [Pendências e bloqueios](#10-pendências-e-bloqueios)
11. [Riscos e mitigações](#11-riscos-e-mitigações)
12. [Próximos passos imediatos](#12-próximos-passos-imediatos)
13. [Stack técnica](#13-stack-técnica)
14. [Backlog — o que falta](#14-backlog--o-que-falta)

---

## 1. Contexto atual

O projeto já está **em produção** e cobrando assinantes — diferente de um anteprojeto, este é
um sistema rodando. O corpo do app é essencialmente **quatro scripts Python** (`scraper.py`,
`dashboard.py`, `auth.py`, `favorites.py` + `alertas.py`) mais a infraestrutura do Supabase e
do Stripe. Não há framework web nem back-end separado: o Streamlit *é* o front-end e o
back-end ao mesmo tempo.

- **Deploy:** hoje em [leilaoce.streamlit.app](https://leilaoce.streamlit.app) (Streamlit
  Community Cloud), atualiza a cada push no `main`. **Migração para o Render em andamento**
  (blueprint `render.yaml`, `requirements-web.txt` e [`SETUP_RENDER.md`](SETUP_RENDER.md)) —
  enquanto a URL de produção não mudar, o deploy vigente ainda é o Streamlit Cloud. Ao
  concluir, revisar as seções 7 e 13.
- **Repositório:** [github.com/mounjour/leilao-ce](https://github.com/mounjour/leilao-ce).
- **Coleta:** GitHub Actions (`.github/workflows/scraper.yml`) roda `scraper.py` 2×/dia
  (03h e 15h de Fortaleza), sobrescreve `leiloes.json` e faz commit automático — ver
  [`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md).
- **8 fontes de leilão ativas** hoje (Leilo, Mega, Pacto, Montenegro, MJ Leilões,
  HastaPública, Receita Federal/SLE, Francisco Freitas) + **3 bloqueadas** por
  Cloudflare/crédito de proxy (MGL, Construbem, Daniel Garcia — Construbem voltou a
  render em 1 run em 08/09, em observação) + **1 dormente** (Celso Cunha — site
  reconstruído, sem leilão ativo; ver [`CELSO_CUNHA_DORMENTE.md`](CELSO_CUNHA_DORMENTE.md))
  — detalhe na [seção 5](#5-fontes-de-leilão-scrapers).
- **Health check do scraper** (`scraper_health.py`, desde 08/09): se uma fonte ativa fica
  3 runs seguidos com 0 lote, loga `::warning::` e manda WhatsApp pro dono. Placar por
  fonte em `scraper_health.json` (commitado junto do `leiloes.json`).
- **`leiloes.json` é o banco de dados dos lotes** — não há tabela de leilões no Postgres; o
  arquivo é gerado pelo scraper e commitado no git a cada rodada (ver
  [seção 7](#7-arquitetura-técnica)).

### Dores que o sistema resolve

- Ninguém teria tempo de checar manualmente ~10 sites de leiloeiro diferentes todo dia para
  achar oportunidade no Ceará.
- Comparação com a FIPE e leitura do estado do veículo (batido/sinistrado/recuperado de
  financiamento) via IA, para não precisar ler a descrição completa de cada lote.
- Não perder um lote favoritado: alerta por WhatsApp quando o lance dele muda.

### Quem usa

- **Assinantes pagantes** (Stripe, cobrança mensal) — usam o painel para buscar, filtrar e
  favoritar lotes.
- **Contas `billing_exempt`** — passam pela cobrança sem cartão (ex.: o próprio dono, testes).
- Login individual via Supabase Auth (fluxo PKCE); sem distinção de papéis além de
  assinante/isento — não há um perfil "admin" separado no código hoje.

---

## 2. Objetivos do sistema

- Agregar automaticamente os lotes de leilão do Ceará de múltiplos leiloeiros num único lugar.
- Classificar cada lote (categoria, estado do item via IA, oportunidade de preço vs. FIPE).
- Atualizar a base **2× por dia** sem intervenção manual.
- Deixar o usuário favoritar lotes e ser avisado no WhatsApp quando o lance mudar.
- Cobrar assinatura recorrente (Stripe) e bloquear quem não tem acesso ativo.
- Manter custo de IA sob controle (cache de análises + fallback quando o crédito acaba).

---

## 3. Escopo

### Já entregue (em produção)

- Scraper multi-fonte com dedupe por URL normalizada (`vistos`), rodando 2×/dia via GitHub
  Actions.
- Classificação por categoria (carros/motos/caminhões/imóveis/equipamentos/eletrônicos), extração de
  marca/modelo/ano/km/lance/foto/descrição por regex e parsing de HTML por fonte.
- Comparação com a **tabela FIPE** (`parallelum.com.br/fipe`) e cálculo de
  `oportunidade_preco` (ótimo/mediano/ruim/inspecionar).
- Análise de estado do item por **IA** (Claude Haiku 4.5), com **cache em disco**
  (`analises_ia_cache.json`) e **circuit breaker** que desliga a IA e cai no fallback
  "Não informado" quando o crédito da Anthropic acaba.
- Painel "Economia de tokens da IA" (`render_painel_tokens`) — mostra quantas chamadas foram
  evitadas pelo cache/circuit breaker.
- Dashboard Streamlit com abas por categoria, pílulas de classificação/estado, cards com foto
  e fallback de ícone quando a foto quebra.
- Cadastro/login via Supabase Auth (PKCE) + trigger `handle_new_user`.
- Favoritos sincronizados com Supabase (`favorites`, upsert por `user_id,lote_url`), com envio
  de WhatsApp na hora de favoritar (best-effort, não desfaz o favorito se falhar).
- Alerta de mudança de lance via WhatsApp para quem tem lote favoritado (`alertas.py`, roda
  depois do scraper no mesmo workflow).
- Cobrança recorrente via **Stripe Checkout** + **Billing Portal**, com paywall
  (`render_paywall`) bloqueando quem não tem `is_subscribed()`.
- Webhook do Stripe (`stripe-webhook`, Supabase Edge Function em Deno) sincronizando
  `subscription_status`/`stripe_customer_id`/etc. em `profiles`, com fallback que busca
  telefone/nome em `auth.users` quando o trigger de signup falhou.
- Páginas institucionais: "Sobre", "Como comprar", "Favoritos", "Informações".

### Fora do escopo (decisão do dono, 08/09/2026)

- **Relatórios/exportação (Excel, PDF)** — não entra. Nenhuma rota de relatório.
- **Notificação de lote novo** que bate com filtro salvo — não entra. Fica só o alerta de
  **mudança de lance** em favorito já existente.
- **Migrar o WhatsApp da Evolution API para a Cloud API oficial da Meta** — não entra.
  Mantém na Evolution, ciente do risco de bloqueio de número (ver [seção 11](#11-riscos-e-mitigações)).
- Qualquer papel de administrador dentro do app (gestão de usuários, ver todos os favoritos
  etc.) — administração é feita direto no painel do Supabase/Stripe.
- Fontes atrás de Cloudflare sem proxy pago (MGL, Construbem, Daniel Garcia, Nasar Leilões) —
  ver [seção 10](#10-pendências-e-bloqueios).
- Filtro server-side por estado/cidade nas APIs de terceiros que não respeitam `estado=`
  (contornado lote a lote no código, não é um problema do nosso sistema).

---

## 4. Módulos funcionais

### 4.1 — Scraper (`scraper.py`, ~3000 linhas)

Um `_raspar_<fonte>()` por leiloeiro (13 no total; 8 ativos, 3 bloqueados, 1 dormente e a
chamada da Celso Cunha comentada), rodando ou via **Playwright**
(sites com JS pesado: Leilo, Mega, Pacto, MGL, Montenegro) ou via **`requests` puro** (sites
renderizados no servidor, sem Cloudflare: MJ, Celso Cunha, HastaPública, Receita SLE,
Francisco Freitas, e a plataforma Soleon usada por Construbem/Daniel Garcia). Todas convergem
para `_lote_dict()`, o formato único de saída — ver [seção 6](#6-modelo-de-dados).

Sub-responsabilidades dentro do arquivo:
- **Categorização** por palavras-chave (`PALAVRAS_MOTO/CAMINHAO/MAQUINA/IMOVEL`) quando a
  fonte não entrega categoria estruturada.
- **FIPE** (`buscar_fipe`, `_score_modelo`) — casa marca/modelo/ano com a API da FIPE por
  aproximação de texto.
- **IA** (`analisar`, `_analisar_cached`) — chama Claude só quando há descrição ou km (uma
  análise genérica sem dado não vale o token), com cache versionado em disco por hash dos
  dados do veículo.
- **Extração de texto genérica** (`_extrair_lance`, `_extrair_km`, `_extrair_descricao`,
  `_extrair_data_leilao`, `_extrair_foto`) reaproveitada por várias fontes.

### 4.2 — Dashboard (`dashboard.py`, ~1700 linhas)

Streamlit single-file: CSS inline extenso (cards, pílulas, botão de favoritar, sidebar,
header/toolbar — CSS já consolidado em blocos únicos, ver `CONVENÇÕES` no `CLAUDE.md`),
filtros, abas por categoria, cards de lote (`render_lotes`), menu de usuário
(`render_user_menu`) com acesso ao portal de cobrança, páginas institucionais e o painel de
economia de tokens de IA.

### 4.3 — Autenticação e cobrança (`auth.py`, 918 linhas)

- Sessão Supabase (PKCE), `ensure_valid_session()` renovando token a cada carregamento.
- `login` / `signup` / `reset_password` / `update_password` / `logout`.
- `is_subscribed()` — gate único usado pelo dashboard: `billing_exempt` **ou**
  `subscription_status` ativo.
- `create_checkout_url()` — cria sessão do Stripe Checkout vinculada ao `user.id` do Supabase
  (`client_reference_id` + metadata), com **cache de 15 min** pra não recriar sessão a cada
  rerun do Streamlit, e bloqueio (`ExistingSubscriptionError`) contra assinatura duplicada.
- `create_billing_portal_url()` — portal de autoatendimento do Stripe.
- `render_paywall()` — tela de bloqueio com preço, features e CTA de assinatura.

### 4.4 — Favoritos (`favorites.py`)

CRUD de favoritos autenticado (RLS por `access_token`, não pela service key), com
normalização de URL (`_normalizar_url`) pra evitar duplicar favorito por causa de UTM/trailing
slash, e disparo de WhatsApp best-effort ao favoritar. A falha de envio não desfaz o favorito,
mas **agora deixa rastro**: grava uma linha em `whatsapp_send_log` no Supabase via
`whatsapp_log.registrar_falha` (antes era `except Exception: pass`).

### 4.5 — Alertas (`alertas.py`)

Roda **depois** do scraper no mesmo workflow do GitHub Actions: compara `lance_atual` de cada
lote favoritado contra o `lote_data` salvo em `favorites`, manda WhatsApp via Evolution API
para quem mudou, e atualiza o snapshot salvo (`lote_data`) — é o que faz o alerta ser
"só quando muda", não repetitivo todo dia. Falha de envio também vai para `whatsapp_send_log`.

### 4.6 — Cobrança (Stripe + Supabase Edge Function)

Webhook (`supabase/functions/stripe-webhook/index.ts`) processa eventos do Stripe, é
idempotente via `billing_webhook_events`, e tem um fallback de emergência que lê
telefone/nome de `auth.users.raw_user_meta_data` quando `handle_new_user` falhou no signup —
sem isso, `alertas.py` não teria telefone pra mandar WhatsApp.

### 4.7 — Health check do scraper (`scraper_health.py`)

Chamado no fim de `raspar_leiloes()` (best-effort, nunca derruba o run). Mantém um placar por
fonte em `scraper_health.json` (commitado junto do `leiloes.json`); quando uma fonte de
`FONTES_ATIVAS` fica 3 runs seguidos com 0 lote, loga `::warning::` e manda WhatsApp pro dono
(`OWNER_WHATSAPP`). `FONTES_ESPERADAS_ZERO` (mgl/construbem/danielgarcia/celsocunha) são
rastreadas mas nunca alertam.

---

## 5. Fontes de leilão (scrapers)

| Fonte | Método | Status | Observação |
| :---- | :---- | :---- | :---- |
| **Leilo** | Playwright | ✅ Ativa | Maior volume hoje (58 lotes no último snapshot). |
| **Mega** | Playwright | ✅ Ativa | — |
| **Pacto** | Playwright | ✅ Ativa | — |
| **Montenegro** | Playwright (scroll infinito) | ✅ Ativa | `_scroll_ate_carregar_todos`. |
| **MJ Leilões** | `requests` | ✅ Ativa | Sem Cloudflare. |
| **Celso Cunha** | `requests` | 😴 Dormente | Site reconstruído ~28/08 (esquema de URL antigo removido, lotes por AJAX) e **sem leilão ativo** (`/agenda-de-leiloes` só tem editais de 2019). Rendia 119 lotes/run até 26/08, 0 desde então. Chamada comentada. Reativar estilo MGL quando voltar. Ver [`CELSO_CUNHA_DORMENTE.md`](CELSO_CUNHA_DORMENTE.md). |
| **HastaPública** | `requests` | ✅ Ativa | Contrato dos leilões judiciais do TJ-CE (leiloeiro Silvio Cesar Maraschi); lotes do CE no "grupo 11". |
| **Receita Federal (SLE)** | `requests` (API `.gov`) | ✅ Ativa | Filtro CE por lote. Veículo/máquina: exige "Cidade/CE" na descrição. Eletrônico (desde 08/09, categoria `eletronicos`): filtro CE pelo `recintoArmazenador`, referência de preço = `valorAvaliacao` da RFB. **287 lotes no snapshot de 08/09** (era 5 antes dos eletrônicos). Ver RECEITA_SLE_ADICIONADO.md. |
| **Francisco Freitas** (Norte Nordeste) | `requests` (API JSON) | ✅ Ativa | **Maior fonte de veículo/imóvel** — 77 lotes CE estáveis. |
| **MGL** | Playwright + API JSON | ❌ Bloqueada | Cloudflare barra o IP do runner do GitHub Actions (403 confirmado em 2 runs). Precisa de proxy residencial. |
| **Construbem** (Soleon) | `requests` | ⚠️ Bloqueada (voltou 1 run) | Zenrows sem crédito (402). Rendeu 7 lotes no run de 08/09 — em observação; se firmar, sai de `FONTES_ESPERADAS_ZERO`. |
| **Daniel Garcia** (Soleon) | `requests` | ❌ Bloqueada | ScraperAPI com timeout. |
| Nasar Leilões | — | 🔍 Descartada por ora | Muito imóvel no CE, mas atrás de Cloudflare — sem proxy, fica no radar. |
| Sodré Santoro | — | 🚫 Descartada | Pátios só em SP/PR, sem estoque no CE. |
| Copart | — | 🚫 Descartada | Login obrigatório + anti-bot agressivo. |
| Lopes Leilões | — | 🚫 Descartada | Site sem Cloudflare, mas dormente (zero lotes). |
| VIP Leilões | — | 🚫 Descartada | Venda direta, não é leilão. |
| freitasleiloeiro.com.br (Santo André/SP) | — | 🚫 Descartada | Sobrenome parecido com Francisco Freitas, leiloeiro diferente — quase zero CE. |

**Snapshot do `leiloes.json` em 08/09/2026:** 529 lotes — Receita Federal 287 (com
eletrônicos), Francisco Freitas 77, Leilo 61, Pacto 30, Montenegro 27, Mega 20, MJ 16,
Construbem 7, HastaPública 4. Celso Cunha, MGL e Daniel Garcia em 0 (dormente/bloqueadas).

---

## 6. Modelo de dados

### 6.1 — Lote (`leiloes.json`, gerado por `_lote_dict()`)

Não é uma tabela — é uma lista de objetos JSON, regravada por inteiro a cada rodada do
scraper e commitada no git.

| Campo | Observação |
| :---- | :---- |
| `fonte` | Slug do leiloeiro (`leilo`, `mega`, `hastapublica`, ...). |
| `categoria` / `icone` | carros/motos/caminhoes/imoveis/equipamentos/eletronicos + emoji. |
| `marca` / `modelo` / `ano` / `cidade` / `km` | Extraídos do HTML/API de cada fonte. |
| `lance_atual` | Valor numérico do lance/proposta no momento da raspagem. |
| `fipe_valor` / `fipe_str` | Referência FIPE casada por aproximação de texto. |
| `classificacao` | Resultado de `classificar()` (ótimo/mediano/ruim/...) cruzando lance × FIPE. |
| `oportunidade` | Rótulo de oportunidade de preço (`oportunidade_preco`). |
| `estado` / `estado_selo` | Estado do item segundo a IA (BOM/BATIDO/SINISTRADO/RECUPERADO_FINANCIAMENTO/SUCATA/NAO_INFORMADO). |
| `uso_sugerido` / `positivos` / `negativos` / `avaliacao_plataforma` | Saída livre da IA. |
| `foto` / `descricao` / `url` / `data_leilao` | — |
| `scraped_at` | Timestamp da raspagem (`YYYY-MM-DDTHH:MM`). |

Arquivos irmãos, também commitados (o runner do Actions é efêmero, então sem commit eles não
persistem entre rodadas):
- `analises_ia_cache.json` — cache de análises de IA por hash dos dados do veículo.
- `historico_tokens_ia.jsonl` — alimenta o painel "Economia de tokens da IA" do dashboard.
- `scraper_health.json` — placar por fonte do health check (`zero_streak`, `ultima_contagem`,
  `alertado_streak`). Criado no primeiro run após 08/09.

### 6.2 — Supabase (Postgres)

| Tabela | Campos-chave | Observação |
| :---- | :---- | :---- |
| **`profiles`** | `id · phone · subscription_status · stripe_customer_id · stripe_subscription_id · subscription_current_period_end · billing_exempt · updated_at` | Criada pelo trigger `handle_new_user`; colunas de cobrança adicionadas pela migration `20260903000000_billing_columns.sql`. |
| **`favorites`** | `id · user_id · lote_url · lote_data(jsonb) · created_at` | `UNIQUE(user_id, lote_url)`; `lote_data` é uma cópia do objeto do lote no momento do favorito (usada por `alertas.py` para detectar mudança de lance). |
| **`billing_webhook_events`** | `event_id (pk) · event_type · received_at` | Dedupe de eventos do webhook do Stripe; RLS ligada, sem policy — só a service role enxerga. |
| **`whatsapp_send_log`** | `id · created_at · user_id · origem · telefone · lote_url · erro · http_status · corpo` | Só linhas de **falha** de envio de WhatsApp (`favorito` / `alerta_lance` / `teste` / `scraper_health`). RLS ligada: `authenticated` insere a própria linha; leitura só via service role / painel do Supabase. Migration `20260908000000_whatsapp_send_log.sql`. Sem retenção automática (revisitar se crescer); sem visão no app hoje — o dono consulta pelo painel. |

---

## 7. Arquitetura técnica

- **Monolito Python single-file por responsabilidade** — sem framework web; Streamlit serve
  de front-end e de "back-end" (roda a lógica a cada interação do usuário).
- **`leiloes.json` como banco de dados dos lotes** — gerado pelo scraper, commitado no `main`,
  lido direto pelo dashboard (`carregar()`) a cada carregamento de página. Funciona porque o
  volume é pequeno (centenas de lotes) e a atualização é só 2×/dia; não escala para milhares de
  lotes ou updates em tempo real.
- **Banco relacional (Supabase/Postgres)** só para o que precisa de consistência
  transacional/autenticação: usuários, favoritos, cobrança.
- **Coleta assíncrona por cron**: GitHub Actions, não um worker de longa duração — cada
  execução sobe um runner do zero, roda Playwright + scrapers `requests`, salva e sai.
- **Autenticação**: Supabase Auth (PKCE), com trigger de banco (`handle_new_user`) para criar
  o profile no signup, e fallback na Edge Function do Stripe para o caso do trigger falhar.
- **Cobrança**: Stripe Checkout + Billing Portal + webhook (Deno/Supabase Edge Functions),
  sem integração de pagamento dentro do próprio `auth.py` além de gerar as URLs.
- **IA**: Anthropic (Claude Haiku 4.5), chamada síncrona durante o scraping, com cache em
  disco e circuit breaker — a IA nunca bloqueia a geração do `leiloes.json`, só empobrece o
  campo `estado`.
- **Alertas**: WhatsApp via **Evolution API** (instância própria/terceiro, não é a Cloud API
  oficial da Meta) — ver riscos na [seção 11](#11-riscos-e-mitigações).
- **Alertas de operação**: `scraper_health.py` avisa o dono por WhatsApp se uma fonte ativa
  para de render lote por 3 runs seguidos (não falha o job).
- **Hospedagem**: hoje Streamlit Community Cloud (deploy automático no push do `main`);
  **migração para o Render em andamento** (blueprint `render.yaml`, `requirements-web.txt`,
  `SETUP_RENDER.md`). Em qualquer um dos dois: sem ambiente de **staging** — todo push no
  `main` vai direto pra produção. O gate de testes (`pytest` no `tests.yml` e no
  `scraper.yml`) é a única barreira; não há smoke test do app em si.
- **Backup**: fica a cargo do que o plano do Supabase oferece — **não há rotina própria**.
  Confirmar o tier: no Free não há backup automático; no Pro há backup diário com retenção
  de 7 dias (PITR é add-on). `leiloes.json` e afins estão versionados no git (histórico
  completo), então o risco real de perda é o Postgres (usuários, favoritos, cobrança,
  `whatsapp_send_log`).

---

## 8. Alertas — decisão de canal

Diferente de um sistema de cobrança com "lembrete para operador vs. mensagem direta ao
cliente", aqui só existe **um** canal, já implementado e em produção:

| Ponto | Como está |
| :---- | :---- |
| Canal | **WhatsApp direto ao usuário**, via Evolution API (não oficial). |
| Gatilho | Mudança no `lance_atual` de um lote que o usuário já favoritou — **não** avisa sobre lote novo. |
| Frequência | Só quando muda (o snapshot em `favorites.lote_data` é atualizado a cada verificação, evitando reenvio do mesmo alerta). |
| Quando roda | Depois do scraper, no mesmo workflow do GitHub Actions (2×/dia). |
| Falha de envio | Não desfaz nada — é best-effort; se a Evolution API cair, o favorito e o `lote_data` continuam normais. Desde 08/09 a falha **grava uma linha em `whatsapp_send_log`** (via `whatsapp_log.registrar_falha`), então dá pra auditar sem cavar log do Actions. |
| Número de origem | Da instância Evolution configurada (`EVOLUTION_INSTANCE`), não o WhatsApp pessoal de alguém do time. |

**Risco assumido:** Evolution API é uma integração **não oficial** com o WhatsApp — risco de
bloqueio de número. O dono decidiu em 08/09 **manter na Evolution** (não migrar para a Cloud
API oficial da Meta). Fica registrado como risco aceito, não como pendência.

---

## 9. Roadmap de entrega

Reconstruído a partir do histórico de commits e do `CLAUDE.md` — não há fases numeradas
formalmente no repo, mas dá pra ler a ordem real de entrega:

| Marco | Entregue | Conteúdo |
| :---- | :---- | :---- |
| **Scraper base** | ✅ | Leilo + Mega + Pacto + MGL + Montenegro — primeira versão funcional, FIPE + IA + categorização. |
| **Auth + Favoritos** | ✅ | Supabase Auth (PKCE), trigger `handle_new_user`, `favorites` com upsert por `user_id,lote_url`. |
| **Cobrança (Stripe)** | ✅ | Checkout + Billing Portal + enforcement no dashboard + webhook Edge Function. |
| **Automação 2×/dia** | ✅ | GitHub Actions: scraper → commit do `leiloes.json` → alertas WhatsApp, tudo num workflow. |
| **Expansão de fontes (rodada 1)** | ✅ | Construbem/Daniel Garcia (Soleon), MJ Leilões, Celso Cunha — mas Construbem/Daniel Garcia acabaram bloqueados por Cloudflare depois. |
| **Expansão de fontes (rodada 2)** | ✅ | HastaPública (03/09), Receita Federal/SLE (03/09), Francisco Freitas (04/09) — as três somam mais fontes CE reais sem depender de proxy pago. |
| **Endurecimento da cobrança** | ✅ | Migration `billing_columns`, fallback de telefone/nome no webhook, deploy da Edge Function (03/09). |
| **Eletrônicos da Receita Federal** | ✅ | Categoria `eletronicos`; `receita_sle` foi de 5 → 287 lotes (08/09). |
| **Dívida técnica fechada** | ✅ | Testes (`tests/`, `pytest` no CI, 08/09) · log de falha de WhatsApp (`whatsapp_send_log`, 08/09) · health check do scraper (`scraper_health.py`, 08/09) · Celso Cunha marcada dormente (08/09). |
| **Desbloqueio de MGL/Construbem/Daniel Garcia** | ⏳ Pendente | Depende de crédito Zenrows/ScraperAPI ou proxy residencial. Construbem rendeu 1 run em 08/09. |
| **Recarga de crédito Anthropic** | ⏳ Pendente | IA em fallback desde 02/09. |
| **Relatórios / exportação** | 🚫 Fora de escopo | Decisão do dono (08/09) — não entra. |
| **Notificação de lote novo por filtro salvo** | 🚫 Fora de escopo | Decisão do dono (08/09) — fica só o alerta de mudança de lance. |
| **WhatsApp na Cloud API oficial da Meta** | 🚫 Fora de escopo | Decisão do dono (08/09) — mantém na Evolution, risco assumido. |

---

## 10. Pendências e bloqueios

| Bloqueio | Fonte afetada | O que destrava |
| :---- | :---- | :---- |
| Cloudflare no IP do runner do GitHub Actions | MGL | Proxy residencial (ver `MGL_SCRAPER_PENDENTE.md`). |
| Zenrows sem crédito (402) | Construbem | Recarregar crédito Zenrows. |
| ScraperAPI com timeout | Daniel Garcia | Recarregar/trocar crédito ScraperAPI, ou rotear pelo mesmo padrão do Zenrows. |
| Créditos Anthropic esgotados desde 02/09 | Todas (campo `estado`) | Recarregar em console.anthropic.com — o circuit breaker já protege o resto do pipeline enquanto isso não acontece. |
| Cloudflare (sem proxy avaliado ainda) | Nasar Leilões | Fica no radar como próxima fonte candidata, se algum dia houver proxy disponível. |
| Site reconstruído + sem leilão ativo | Celso Cunha | Nada a fazer agora (dormente). Reescrever `_raspar_celso_cunha` estilo MGL quando o site voltar a ter leilão. Ver `CELSO_CUNHA_DORMENTE.md`. |

Essas pendências (fontes + IA) são hoje o principal fator limitando o volume e a
qualidade de dado do painel — não são bugs, são bloqueios de crédito/infraestrutura externos
(ou, no caso da Celso Cunha, o próprio site parado).

---

## 11. Riscos e mitigações

| Risco | Mitigação atual / recomendada |
| :---- | :---- |
| `leiloes.json` como "banco" cresce demais e o commit/diff fica pesado. | Ok para o volume atual (centenas de lotes); se crescer para milhares, migrar os lotes para uma tabela no Postgres. |
| Evolution API (WhatsApp não oficial) pode ser bloqueada pela Meta a qualquer momento. | Migrar para WhatsApp Cloud API oficial via BSP quando o volume de alertas justificar o custo/verificação de empresa. |
| Runner do GitHub Actions tem IP de datacenter — vulnerável a bloqueio por Cloudflare em qualquer fonte nova, não só nas 3 já bloqueadas. | Avaliar proxy residencial compartilhado entre todas as fontes bloqueadas, em vez de resolver uma de cada vez. |
| `_IA_ATIVA` desliga globalmente ao primeiro erro de crédito e só volta a `True` em um novo processo do scraper — uma rodada inteira pode ficar sem IA mesmo depois de recarregar crédito no meio dela. | Aceitável dado que o scraper roda do zero a cada execução (2×/dia); não vale complexidade de detectar recarga em tempo real. |
| Dependência de uma única pessoa entendendo o sistema (arquivos grandes). | **Mitigado (08/09):** `tests/` com pytest cobrindo os parsers/classificação críticos de `scraper.py`, `whatsapp_log` e `scraper_health`; roda no `tests.yml` (push/PR) e como gate no `scraper.yml`. `teste_alerta.py` segue como script manual à parte. |
| Falha silenciosa de `_whatsapp_favorito` / `alertas.send_whatsapp` (exceção engolida). | **Mitigado (08/09):** as duas rotas gravam a falha em `whatsapp_send_log` (Supabase) via `whatsapp_log.registrar_falha` — auditável pelo painel, sem cavar log do Actions. |
| Fonte de leilão muda de site e para de render lote sem ninguém notar (aconteceu com a Celso Cunha: 12 dias em 0). | **Mitigado (08/09):** `scraper_health.py` alerta o dono por WhatsApp se uma fonte de `FONTES_ATIVAS` fica 3 runs seguidos zerada. |
| Deploy direto em produção (sem staging) — um push quebrado no `main` derruba o app. | Parcial: o gate de `pytest` pega regressão de lógica pura; não há smoke test do app. Aceito por ora (app pequeno, rollback = revert + push). Vale reavaliar na migração pro Render. |
| Perda do Postgres do Supabase (usuários/favoritos/cobrança). | Sem rotina própria de backup — depende do tier do Supabase (confirmar; Free não faz backup). `leiloes.json` e afins estão no git. |
| Cobrança duplicada de assinatura Stripe. | Já mitigado: `create_checkout_url` verifica assinaturas existentes (`ExistingSubscriptionError`) antes de criar uma nova sessão. |
| Falha do trigger `handle_new_user` deixando profile sem telefone. | Já mitigado: fallback no webhook do Stripe lê `auth.users.raw_user_meta_data`. |

---

## 12. Próximos passos imediatos

1. **Concluir a migração para o Render** — blueprint pronto (`render.yaml`,
   `requirements-web.txt`, `SETUP_RENDER.md`); falta subir o serviço, apontar a URL de
   produção e desligar o deploy do Streamlit Cloud. Ao terminar, revisar as seções 1, 7 e 13.
2. **Recarregar crédito Zenrows/ScraperAPI** — destrava Construbem e Daniel Garcia de uma vez
   (ambos já têm código pronto, só falta a rota de proxy funcionar).
3. **Avaliar proxy residencial para MGL** — é a única saída, já que o Cloudflare bloqueia o IP
   do runner mesmo com o código validado.
4. **Recarregar crédito Anthropic** — reativa a análise de estado do item (`estado`/`selo`)
   em todos os lotes, hoje em fallback "Não informado".
5. **Confirmar o tier de backup do Supabase** (Free = sem backup; Pro = diário 7 dias). Se
   Free, decidir se vale um `pg_dump` agendado.
6. **Observar Construbem** nos próximos runs — se firmar (>1 run com lote), tirar de
   `FONTES_ESPERADAS_ZERO` em `scraper_health.py` e voltar ao status "Ativa" na seção 5.
7. **Checar `/agenda-de-leiloes` da Celso Cunha** de vez em quando — se voltar a ter leilão
   ativo, reimplementar `_raspar_celso_cunha` estilo MGL.

---

## 13. Stack técnica

| Camada | Escolha | Observação |
| :---- | :---- | :---- |
| Front-end + back-end | **Streamlit 1.62** | Single-file por responsabilidade; sem separação cliente/servidor. |
| Scraping (JS pesado) | **Playwright** + `playwright-stealth` | Leilo, Mega, Pacto, MGL, Montenegro. |
| Scraping (server-rendered) | `requests` puro | MJ, HastaPública, Receita SLE, Francisco Freitas, Soleon (Construbem/Daniel Garcia). Celso Cunha (dormente). |
| Proxy anti-bloqueio | Zenrows / ScraperAPI | Só usados quando `requests` puro apanha de Cloudflare; ambos sem crédito hoje. |
| Saúde da coleta | `scraper_health.py` + `scraper_health.json` | Alerta o dono por WhatsApp se fonte ativa fica 3 runs seguidos sem lote. |
| IA | **Anthropic Claude Haiku 4.5** | Só análise de estado do item; classificação de oportunidade é local (sem IA). |
| Referência de preço | API pública da **FIPE** (`parallelum.com.br`) | Casamento por aproximação de texto (`_score_modelo`). |
| Banco/Auth | **Supabase** (Postgres + Auth PKCE) | `profiles`, `favorites`, `billing_webhook_events`, `whatsapp_send_log`. |
| Cobrança | **Stripe** (Checkout + Billing Portal + Webhook) | Webhook roda como Supabase Edge Function em **Deno**. |
| Alertas | **WhatsApp via Evolution API** (não oficial) | Ver risco na seção 11. |
| Automação | **GitHub Actions** (cron 2×/dia) | Scraper → commit `leiloes.json` → alertas, tudo em um workflow. |
| Hospedagem | **Streamlit Community Cloud** (migração pro **Render** em andamento) | Deploy automático no push do `main`. Ver `SETUP_RENDER.md` / `render.yaml`. |
| Dados | `leiloes.json` + `analises_ia_cache.json` + `historico_tokens_ia.jsonl` + `scraper_health.json` **commitados no git** | Funciona como banco de dados versionado para os lotes; ver riscos. |

---

## 14. Backlog — o que falta

### Bloqueios externos (crédito/infra, não é trabalho de código)

- [ ] Crédito Zenrows → destrava Construbem
- [ ] Crédito/roteamento ScraperAPI → destrava Daniel Garcia
- [ ] Proxy residencial → destrava MGL
- [ ] Crédito Anthropic → reativa análise de IA em todos os lotes

### Produto — decisões do dono (08/09/2026)

- 🚫 **Relatórios/exportação (Excel, PDF)** — não entra.
- 🚫 **Notificação de lote novo por filtro salvo** — não entra; fica só o alerta de mudança
  de lance em favorito.
- 🚫 **Migrar alertas para a WhatsApp Cloud API oficial** — não entra; mantém na Evolution,
  risco assumido.
- [ ] Avaliar Nasar Leilões como fonte, se/quando houver proxy disponível (segue no radar).

### Técnico

- [x] **Cobertura de testes** dos parsers/classificação críticos de `scraper.py`
  (`classificar`, `oportunidade_preco`, `_extrair_lance`, `_extrair_km`, `_score_modelo`,
  `_parse_brl`, `buscar_referencia_mercado`, `detectar_categoria`) — 08/09,
  `tests/test_scraper.py`. `conftest.py` faz stub de Playwright/anthropic/dotenv. CI em
  `tests.yml` (push/PR) + gate no `scraper.yml`. `teste_alerta.py` segue manual à parte.
- [x] **Log persistente de falha de envio de WhatsApp** — 08/09. `favorites.py` e
  `alertas.py` gravam a falha em `whatsapp_send_log` (Supabase) via
  `whatsapp_log.registrar_falha`. Migration `20260908000000_whatsapp_send_log.sql` aplicada.
  Testes em `tests/test_whatsapp_log.py`.
- [x] **Health check do scraper** — 08/09. `scraper_health.py` alerta o dono por WhatsApp se
  uma fonte de `FONTES_ATIVAS` fica 3 runs seguidos com 0 lote. Placar em
  `scraper_health.json`. Testes em `tests/test_scraper_health.py`. Secret `OWNER_WHATSAPP`.
- [x] **Celso Cunha marcada dormente** — 08/09. Chamada comentada, doc em
  `CELSO_CUNHA_DORMENTE.md`.
- [x] **`debug.py` removido** — 08/09. Era script solto de dev, não importado em lugar nenhum.
- [ ] **Retenção do `whatsapp_send_log`** — cresce sem limite. Ok por ora (falha é rara);
  revisitar se passar de alguns milhares de linhas. Sem visão no app — dono consulta pelo
  painel do Supabase.
- [ ] **Backup do Postgres do Supabase** — confirmar o tier (Free = sem backup automático).
  Se necessário, `pg_dump` agendado.
- [ ] **`leiloes.json` como "banco" no git** — decisão do dono: **manter**. Reavaliar só se
  o volume passar de milhares de lotes.
- [ ] **Sem staging / smoke test do app** — aceito por ora; rollback = `git revert` + push.
