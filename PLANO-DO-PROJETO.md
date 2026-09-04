# Plano do Projeto — Achadin Leilões (leilao-ce)

> **Documento de análise/status** · 04/09/2026
> **Base:** leitura direta do código (`scraper.py`, `dashboard.py`, `auth.py`, `favorites.py`,
> `alertas.py`), do `CLAUDE.md`, das migrations/Edge Functions do Supabase e do histórico do git.
> **Status:** MVP em produção (`leilaoce.streamlit.app`), com cobrança ativa. O que falta é
> sobretudo **destravar fontes bloqueadas** (crédito de proxy/IA) e **construir relatórios**.

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

- **Deploy:** [leilaoce.streamlit.app](https://leilaoce.streamlit.app) (Streamlit Community
  Cloud) — atualiza automaticamente a cada push no `main`.
- **Repositório:** [github.com/mounjour/leilao-ce](https://github.com/mounjour/leilao-ce).
- **Coleta:** GitHub Actions (`.github/workflows/scraper.yml`) roda `scraper.py` 2×/dia
  (03h e 15h de Fortaleza), sobrescreve `leiloes.json` e faz commit automático — ver
  [`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md).
- **9 fontes de leilão ativas** hoje (Leilo, Mega, Pacto, Montenegro, MJ Leilões, Celso Cunha,
  HastaPública, Receita Federal/SLE, Francisco Freitas) + **3 bloqueadas** por
  Cloudflare/crédito de proxy (MGL, Construbem, Daniel Garcia) — detalhe na
  [seção 5](#5-fontes-de-leilão-scrapers).
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
- Classificação por categoria (carros/motos/caminhões/imóveis/equipamentos), extração de
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

### Fora do escopo por ora

- Relatórios/exportação (Excel, PDF) — não existe nenhuma rota de relatório hoje.
- Notificação de novo lote (hoje só alerta **mudança de lance** de quem já é favorito).
- Qualquer papel de administrador dentro do app (gestão de usuários, ver todos os favoritos
  etc.) — administração é feita direto no painel do Supabase/Stripe.
- Fontes atrás de Cloudflare sem proxy pago (MGL, Construbem, Daniel Garcia, Nasar Leilões) —
  ver [seção 10](#10-pendências-e-bloqueios).
- Filtro server-side por estado/cidade nas APIs de terceiros que não respeitam `estado=`
  (contornado lote a lote no código, não é um problema do nosso sistema).

---

## 4. Módulos funcionais

### 4.1 — Scraper (`scraper.py`, 2849 linhas)

Um `_raspar_<fonte>()` por leiloeiro (13 no total, 9 ativos), rodando ou via **Playwright**
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

### 4.2 — Dashboard (`dashboard.py`, 1594 linhas)

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

### 4.4 — Favoritos (`favorites.py`, 164 linhas)

CRUD de favoritos autenticado (RLS por `access_token`, não pela service key), com
normalização de URL (`_normalizar_url`) pra evitar duplicar favorito por causa de UTM/trailing
slash, e disparo de WhatsApp best-effort ao favoritar.

### 4.5 — Alertas (`alertas.py`, 142 linhas)

Roda **depois** do scraper no mesmo workflow do GitHub Actions: compara `lance_atual` de cada
lote favoritado contra o `lote_data` salvo em `favorites`, manda WhatsApp via Evolution API
para quem mudou, e atualiza o snapshot salvo (`lote_data`) — é o que faz o alerta ser
"só quando muda", não repetitivo todo dia.

### 4.6 — Cobrança (Stripe + Supabase Edge Function)

Webhook (`supabase/functions/stripe-webhook/index.ts`) processa eventos do Stripe, é
idempotente via `billing_webhook_events`, e tem um fallback de emergência que lê
telefone/nome de `auth.users.raw_user_meta_data` quando `handle_new_user` falhou no signup —
sem isso, `alertas.py` não teria telefone pra mandar WhatsApp.

---

## 5. Fontes de leilão (scrapers)

| Fonte | Método | Status | Observação |
| :---- | :---- | :---- | :---- |
| **Leilo** | Playwright | ✅ Ativa | Maior volume hoje (58 lotes no último snapshot). |
| **Mega** | Playwright | ✅ Ativa | — |
| **Pacto** | Playwright | ✅ Ativa | — |
| **Montenegro** | Playwright (scroll infinito) | ✅ Ativa | `_scroll_ate_carregar_todos`. |
| **MJ Leilões** | `requests` | ✅ Ativa | Sem Cloudflare. |
| **Celso Cunha** | `requests` | ✅ Ativa | Trata mojibake de encoding (`_demojibake`). |
| **HastaPública** | `requests` | ✅ Ativa | Contrato dos leilões judiciais do TJ-CE (leiloeiro Silvio Cesar Maraschi); lotes do CE no "grupo 11". |
| **Receita Federal (SLE)** | `requests` (API `.gov`) | ✅ Ativa | Filtro CE por lote (exige "Cidade/CE" na descrição); só entram veículo/máquina pesada. |
| **Francisco Freitas** (Norte Nordeste) | `requests` (API JSON) | ✅ Ativa | **Maior fonte já integrada** — 91 lotes CE na investigação, 77 após filtro de categoria. |
| **MGL** | Playwright + API JSON | ❌ Bloqueada | Cloudflare barra o IP do runner do GitHub Actions (403 confirmado em 2 runs). Precisa de proxy residencial. |
| **Construbem** (Soleon) | `requests` | ❌ Bloqueada | Zenrows sem crédito (402). |
| **Daniel Garcia** (Soleon) | `requests` | ❌ Bloqueada | ScraperAPI com timeout. |
| Nasar Leilões | — | 🔍 Descartada por ora | Muito imóvel no CE, mas atrás de Cloudflare — sem proxy, fica no radar. |
| Sodré Santoro | — | 🚫 Descartada | Pátios só em SP/PR, sem estoque no CE. |
| Copart | — | 🚫 Descartada | Login obrigatório + anti-bot agressivo. |
| Lopes Leilões | — | 🚫 Descartada | Site sem Cloudflare, mas dormente (zero lotes). |
| VIP Leilões | — | 🚫 Descartada | Venda direta, não é leilão. |
| freitasleiloeiro.com.br (Santo André/SP) | — | 🚫 Descartada | Sobrenome parecido com Francisco Freitas, leiloeiro diferente — quase zero CE. |

**Snapshot atual do `leiloes.json`** (gerado 04/09 11:33 UTC, **antes** de Receita Federal e
Francisco Freitas entrarem no pipeline): 156 lotes — Leilo 58, Pacto 30, Montenegro 26, Mega
22, MJ 16, HastaPública 4, Celso Cunha 0 nesta rodada. A próxima execução agendada (03h/15h
Fortaleza) já deve trazer os lotes de Receita Federal e Francisco Freitas.

---

## 6. Modelo de dados

### 6.1 — Lote (`leiloes.json`, gerado por `_lote_dict()`)

Não é uma tabela — é uma lista de objetos JSON, regravada por inteiro a cada rodada do
scraper e commitada no git.

| Campo | Observação |
| :---- | :---- |
| `fonte` | Slug do leiloeiro (`leilo`, `mega`, `hastapublica`, ...). |
| `categoria` / `icone` | carros/motos/caminhoes/imoveis/equipamentos + emoji. |
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

### 6.2 — Supabase (Postgres)

| Tabela | Campos-chave | Observação |
| :---- | :---- | :---- |
| **`profiles`** | `id · phone · subscription_status · stripe_customer_id · stripe_subscription_id · subscription_current_period_end · billing_exempt · updated_at` | Criada pelo trigger `handle_new_user`; colunas de cobrança adicionadas pela migration `20260903000000_billing_columns.sql`. |
| **`favorites`** | `id · user_id · lote_url · lote_data(jsonb) · created_at` | `UNIQUE(user_id, lote_url)`; `lote_data` é uma cópia do objeto do lote no momento do favorito (usada por `alertas.py` para detectar mudança de lance). |
| **`billing_webhook_events`** | `event_id (pk) · event_type · received_at` | Dedupe de eventos do webhook do Stripe; RLS ligada, sem policy — só a service role enxerga. |

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
- **Hospedagem**: Streamlit Community Cloud (deploy automático no push); sem servidor próprio
  para a aplicação. Backup do banco fica a cargo do Supabase (não há rotina própria de backup
  documentada).

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
| Falha de envio | Não desfaz nada — é best-effort; se a Evolution API cair, o favorito e o `lote_data` continuam sendo tratados normalmente (o `try/except` de `_whatsapp_favorito` engole a exceção). |
| Número de origem | Da instância Evolution configurada (`EVOLUTION_INSTANCE`), não o WhatsApp pessoal de alguém do time. |

**Risco em aberto:** Evolution API é uma integração **não oficial** com o WhatsApp — mesmo
risco de bloqueio de número citado em projetos parecidos. Migrar para a **Cloud API oficial**
(Meta, via BSP) resolveria isso, mas não está no backlog hoje.

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
| **Desbloqueio de MGL/Construbem/Daniel Garcia** | ⏳ Pendente | Depende de crédito Zenrows/ScraperAPI ou proxy residencial. |
| **Recarga de crédito Anthropic** | ⏳ Pendente | IA em fallback desde 02/09. |
| **Relatórios** | ❌ Não iniciado | Nenhuma exportação ou visão agregada além do painel de tokens de IA. |
| **Notificação de lote novo** | ❌ Não iniciado | Hoje só alerta mudança de lance em favorito existente. |

---

## 10. Pendências e bloqueios

| Bloqueio | Fonte afetada | O que destrava |
| :---- | :---- | :---- |
| Cloudflare no IP do runner do GitHub Actions | MGL | Proxy residencial (ver `MGL_SCRAPER_PENDENTE.md`). |
| Zenrows sem crédito (402) | Construbem | Recarregar crédito Zenrows. |
| ScraperAPI com timeout | Daniel Garcia | Recarregar/trocar crédito ScraperAPI, ou rotear pelo mesmo padrão do Zenrows. |
| Créditos Anthropic esgotados desde 02/09 | Todas (campo `estado`) | Recarregar em console.anthropic.com — o circuit breaker já protege o resto do pipeline enquanto isso não acontece. |
| Cloudflare (sem proxy avaliado ainda) | Nasar Leilões | Fica no radar como próxima fonte candidata, se algum dia houver proxy disponível. |

Essas quatro pendências (3 fontes + IA) são hoje o principal fator limitando o volume e a
qualidade de dado do painel — não são bugs, são bloqueios de crédito/infraestrutura externos.

---

## 11. Riscos e mitigações

| Risco | Mitigação atual / recomendada |
| :---- | :---- |
| `leiloes.json` como "banco" cresce demais e o commit/diff fica pesado. | Ok para o volume atual (centenas de lotes); se crescer para milhares, migrar os lotes para uma tabela no Postgres. |
| Evolution API (WhatsApp não oficial) pode ser bloqueada pela Meta a qualquer momento. | Migrar para WhatsApp Cloud API oficial via BSP quando o volume de alertas justificar o custo/verificação de empresa. |
| Runner do GitHub Actions tem IP de datacenter — vulnerável a bloqueio por Cloudflare em qualquer fonte nova, não só nas 3 já bloqueadas. | Avaliar proxy residencial compartilhado entre todas as fontes bloqueadas, em vez de resolver uma de cada vez. |
| `_IA_ATIVA` desliga globalmente ao primeiro erro de crédito e só volta a `True` em um novo processo do scraper — uma rodada inteira pode ficar sem IA mesmo depois de recarregar crédito no meio dela. | Aceitável dado que o scraper roda do zero a cada execução (2×/dia); não vale complexidade de detectar recarga em tempo real. |
| Dependência de uma única pessoa entendendo o sistema (arquivos grandes, sem testes automatizados visíveis no repo). | Nenhum teste unitário encontrado (`teste_alerta.py` é um script manual, não uma suite). Vale avaliar cobertura mínima para `classificar`/`oportunidade_preco`/parsers críticos. |
| Falha silenciosa de `_whatsapp_favorito` / `alertas.send_whatsapp` (exceção engolida). | Intencional (best-effort), mas sem log persistente de falhas — difícil saber se a Evolution API está fora do ar sem olhar os logs do Actions manualmente. |
| Cobrança duplicada de assinatura Stripe. | Já mitigado: `create_checkout_url` verifica assinaturas existentes (`ExistingSubscriptionError`) antes de criar uma nova sessão. |
| Falha do trigger `handle_new_user` deixando profile sem telefone. | Já mitigado: fallback no webhook do Stripe lê `auth.users.raw_user_meta_data`. |

---

## 12. Próximos passos imediatos

1. **Recarregar crédito Zenrows/ScraperAPI** — destrava Construbem e Daniel Garcia de uma vez
   (ambos já têm código pronto, só falta a rota de proxy funcionar).
2. **Avaliar proxy residencial para MGL** — é a única saída, já que o Cloudflare bloqueia o IP
   do runner mesmo com o código validado.
3. **Recarregar crédito Anthropic** — reativa a análise de estado do item (`estado`/`selo`)
   em todos os lotes, hoje em fallback "Não informado".
4. **Confirmar se o próximo run agendado (03h/15h Fortaleza) trouxe Receita Federal e
   Francisco Freitas** para o `leiloes.json` — essas duas fontes ainda não apareceram em
   nenhum snapshot commitado.
5. Decidir se vale investir em **relatórios/exportação** (hoje inexistentes) ou em
   **notificação de lote novo** (hoje só alerta mudança de lance de favorito) como próxima
   funcionalidade de produto, já que a base de fontes está relativamente robusta.

---

## 13. Stack técnica

| Camada | Escolha | Observação |
| :---- | :---- | :---- |
| Front-end + back-end | **Streamlit 1.62** | Single-file por responsabilidade; sem separação cliente/servidor. |
| Scraping (JS pesado) | **Playwright** + `playwright-stealth` | Leilo, Mega, Pacto, MGL, Montenegro. |
| Scraping (server-rendered) | `requests` puro | MJ, Celso Cunha, HastaPública, Receita SLE, Francisco Freitas, Soleon (Construbem/Daniel Garcia). |
| Proxy anti-bloqueio | Zenrows / ScraperAPI | Só usados quando `requests` puro apanha de Cloudflare; ambos sem crédito hoje. |
| IA | **Anthropic Claude Haiku 4.5** | Só análise de estado do item; classificação de oportunidade é local (sem IA). |
| Referência de preço | API pública da **FIPE** (`parallelum.com.br`) | Casamento por aproximação de texto (`_score_modelo`). |
| Banco/Auth | **Supabase** (Postgres + Auth PKCE) | `profiles`, `favorites`, `billing_webhook_events`. |
| Cobrança | **Stripe** (Checkout + Billing Portal + Webhook) | Webhook roda como Supabase Edge Function em **Deno**. |
| Alertas | **WhatsApp via Evolution API** (não oficial) | Ver risco na seção 11. |
| Automação | **GitHub Actions** (cron 2×/dia) | Scraper → commit `leiloes.json` → alertas, tudo em um workflow. |
| Hospedagem | **Streamlit Community Cloud** | Deploy automático no push do `main`. |
| Dados | `leiloes.json` + `analises_ia_cache.json` + `historico_tokens_ia.jsonl` **commitados no git** | Funciona como banco de dados versionado para os lotes; ver riscos. |

---

## 14. Backlog — o que falta

### Bloqueios externos (crédito/infra, não é trabalho de código)

- [ ] Crédito Zenrows → destrava Construbem
- [ ] Crédito/roteamento ScraperAPI → destrava Daniel Garcia
- [ ] Proxy residencial → destrava MGL
- [ ] Crédito Anthropic → reativa análise de IA em todos os lotes

### Produto

- [ ] Relatórios/exportação (nenhuma rota existe hoje)
- [ ] Notificação de **lote novo** que bate com um filtro salvo (hoje só existe alerta de
  mudança de lance em favorito já existente)
- [ ] Avaliar Nasar Leilões como fonte, se/quando houver proxy disponível
- [ ] Migrar alertas para WhatsApp Cloud API oficial (risco de bloqueio da Evolution API)

### Técnico

- [ ] Cobertura de testes automatizados para os parsers críticos (`classificar`,
  `oportunidade_preco`, `_extrair_lance`, `_score_modelo`) — hoje não há suite, só
  `teste_alerta.py` como script manual
- [ ] Reavaliar se `leiloes.json` commitado no git ainda é a estrutura certa se o volume de
  lotes crescer significativamente
- [ ] Log persistente de falha de envio de WhatsApp (hoje a exceção é engolida silenciosamente
  em `favorites.py` e só aparece no stdout do Actions em `alertas.py`)
