# Setup do Render — deploy do site (Achadin Leilões)

Guia de migração do site de **Streamlit Community Cloud** (`leilaoce.streamlit.app`)
para o **Render**, usando o endereço grátis **`leilao-ce.onrender.com`** como
URL definitiva (sem domínio próprio).

O scraper **não** muda: continua no GitHub Actions 2×/dia (ver
[`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md)). O Supabase e o Stripe
**não** mudam — só passam a apontar para a URL do Render.

> **Sobre usar o `onrender.com`:** é o endereço público permanente do site.
> Sem marca própria na URL, e se um dia você quiser um domínio de verdade vai
> precisar refazer o ajuste de Redirect URLs (Supabase + Stripe) da
> [seção 5](#5-apontar-supabase-e-stripe-para-o-render). Para um SaaS em
> estágio inicial, é aceitável e custa R$ 0.

---

## Arquitetura depois da migração

| Peça | Onde roda | Muda? |
|---|---|---|
| Site (`dashboard.py`, Streamlit) | **Render** (Web Service, plano Starter) | ✅ sai do Community Cloud |
| Scraper (`scraper.py`) | GitHub Actions (cron 2×/dia) | ❌ |
| Banco + Auth | Supabase | só Redirect URLs |
| Cobrança (Checkout + Portal) | Stripe | só as URLs de retorno (via `APP_URL`) |
| Webhook do Stripe | Supabase Edge Function (`*.supabase.co`) | ❌ nada |
| Alertas de lance | GitHub Actions, junto do scraper | ❌ |

Fluxo do dado dos lotes: o Actions gera o `leiloes.json`, dá commit no `main`,
o Render vê o push e redeploya o site com os dados novos. Igual ao que o
Community Cloud faz hoje.

---

## Checklist

**Preparação**
- [ ] Valores dos segredos em mãos ([seção 1](#1-juntar-os-segredos))
- [ ] `render.yaml` e `requirements-web.txt` no `main` (já estão, via PR)

**Render**
- [ ] Conta no Render criada e repositório `mounjour/leilao-ce` conectado
- [ ] Blueprint aplicado — só o Web Service `leilao-ce` ([seção 2](#2-criar-o-serviço-no-render))
- [ ] Envs `sync: false` preenchidas (as 3 `EVOLUTION_*` ficam em branco)
- [ ] `APP_URL` = a URL exata `*.onrender.com` que o Render gerou
- [ ] Primeiro deploy verde; `/_stcore/health` responde `ok`
- [ ] Teste manual passou ([seção 3](#3-testar))

**Apontar os serviços externos**
- [ ] Supabase → Auth → URL Configuration com a URL do Render ([seção 5](#5-apontar-supabase-e-stripe-para-o-render))
- [ ] Stripe → Customer portal: return URL conferida (cosmético)
- [ ] Teste completo: cadastro, login, paywall, checkout, portal, favoritar

**Fechamento**
- [ ] App no Community Cloud pausado/deletado ([seção 6](#6-desligar-o-community-cloud))
- [ ] `CLAUDE.md` e `PLANO-DO-PROJETO.md` atualizados (deploy = Render)

---

## 1. Juntar os segredos

O Render vai pedir estes valores ao aplicar o Blueprint:

| Env | Valor |
|---|---|
| `SUPABASE_URL` | `https://tybfusbovbihrkmcncux.supabase.co` |
| `SUPABASE_ANON_KEY` | chave `anon` / `public` (o `eyJ…`) |
| `STRIPE_SECRET_KEY` | `sk_live_…` se o site cobra de verdade; `sk_test_…` serve para validar |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_…` / `pk_test_…` (mesmo modo da secret) |
| `STRIPE_PRICE_ID` | `price_…` (confirme se é o preço certo) |
| `EVOLUTION_API_URL` | **deixe em branco** |
| `EVOLUTION_API_KEY` | **deixe em branco** |
| `EVOLUTION_INSTANCE` | **deixe em branco** |

`PYTHON_VERSION` (3.11.9) e `STRIPE_PLAN_PRICE_LABEL` (R$ 47) já vêm fixos no
`render.yaml` — o Render não pergunta.

> **`EVOLUTION_*` em branco:** essas três só servem para mandar o WhatsApp
> quando alguém favorita um lote. Os valores não estão salvos em lugar
> recuperável, e essa função já não roda hoje (nem no Community Cloud). O site
> sobe e funciona sem elas. Se um dia recuperar/recriar a instância da
> Evolution, adiciona em Render → serviço → **Environment**.

> **NÃO** coloque no Render: `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`,
> `ZENROWS_API_KEY`, `SCRAPERAPI_KEY`, `OWNER_WHATSAPP`, `STRIPE_WEBHOOK_SECRET`
> — nenhum é usado pelo site (são do scraper/alertas ou da Edge Function).

---

## 2. Criar o serviço no Render

1. Criar conta em <https://render.com> (pode entrar com o GitHub `mounjour`).
2. **New +** → **Blueprint**.
3. Conectar/autorizar o repositório `mounjour/leilao-ce`. O Render lê o
   `render.yaml` e mostra **1 serviço**: o Web Service `leilao-ce`.
4. Ele lista as variáveis `sync: false`. Preencha pela [seção 1](#1-juntar-os-segredos).
   Em `APP_URL`, coloque **a URL exata que o Render mostra no topo** (padrão
   `https://leilao-ce.onrender.com`; se `leilao-ce` estiver tomado ele
   acrescenta um sufixo — use o texto exato).
5. **Apply**. O primeiro build roda `pip install -r requirements-web.txt`
   (~30–60 s) e sobe o Streamlit.
6. Quando o deploy ficar **Live**, abra
   `https://SEU-APP.onrender.com/_stcore/health` — tem que responder `ok`.

> **Plano:** o `render.yaml` vem com `plan: starter` (512 MB / 0.5 CPU,
> US$ 7/mês, sempre ligado) — suficiente para o footprint atual. Para subir
> para `standard` (2 GB / 1 CPU, US$ 25) troque no painel em
> **Settings → Instance Type** — sem mexer em código.

---

## 3. Testar

Em `https://SEU-APP.onrender.com`:

- [ ] Página de login/cadastro abre (sem "Please wait…" travado — se travar, ver [Troubleshooting](#troubleshooting))
- [ ] Cadastro de usuário novo funciona (chega o e-mail do Supabase — pode vir com link da URL antiga até a [seção 5](#5-apontar-supabase-e-stripe-para-o-render))
- [ ] Login funciona e cai no dashboard
- [ ] Sem assinatura → aparece o **paywall** (`render_paywall`)
- [ ] Botão de assinar abre o **Stripe Checkout** (cartão de teste se a chave for `test`; em `live`, cancele antes de pagar)
- [ ] Com assinatura ativa → dashboard completo, lotes carregando do `leiloes.json`
- [ ] **Favoritar um lote** salva e reflete no Supabase (sem `EVOLUTION_*`, não dispara WhatsApp — é esperado)
- [ ] Menu do usuário → **portal de cobrança** (Billing Portal) abre

---

## 4. _(sem etapa de domínio)_

Não há compra de domínio nem DNS. `https://SEU-APP.onrender.com` é o endereço
final. TLS já vem pronto pelo Render.

---

## 5. Apontar Supabase e Stripe para o Render

### 5.1 Confirmar o `APP_URL`
Render → `leilao-ce` → **Environment** → `APP_URL` = `https://SEU-APP.onrender.com`
(sem barra no final). Se você já preencheu certo na [seção 2](#2-criar-o-serviço-no-render),
não precisa mexer. É a partir daí que `auth.py` monta as URLs do Checkout e do
Billing Portal.

### 5.2 Supabase Auth
Supabase → projeto `tybfusbovbihrkmcncux` → **Authentication** → **URL
Configuration**:

- **Site URL:** `https://SEU-APP.onrender.com`
- **Redirect URLs:**
  - `https://SEU-APP.onrender.com`
  - `https://SEU-APP.onrender.com/**`
  - `https://leilaoce.streamlit.app` (mantenha ~1 semana, durante a transição)
  - `http://localhost:8501` (dev local)

> O fluxo PKCE (`auth.py`) redireciona de volta para `APP_URL`; se essa URL não
> estiver na lista, o login quebra com erro de `redirect_to`.

### 5.3 Stripe
- URLs de sucesso/cancelamento do Checkout e o `return_url` do Billing Portal
  são passadas por sessão pelo código (a partir de `APP_URL`) — **nada a mudar
  no painel** para elas.
- Só confira, por estética: Stripe → **Settings** → **Billing** → **Customer
  portal** → se houver um *default return link* no domínio antigo, atualize.
- O **webhook** (`stripe-webhook` no Supabase) continua igual — endpoint
  `*.supabase.co/functions/v1/stripe-webhook`, não depende da URL do site.

### 5.4 Teste final
Repita o checklist da [seção 3](#3-testar), agora com atenção a: e-mail de
confirmação do Supabase com link do Render, Checkout retornando para o Render,
portal de cobrança retornando para o Render.

---

## 6. Desligar o Community Cloud

Só depois de validado (recomendo esperar 3–7 dias).

1. <https://share.streamlit.io> → o app → **Settings** → **Delete app** (ou
   *Reboot/Pause*, para manter como rollback rápido por mais uns dias).
2. Atualizar no repo: `CLAUDE.md` (linha "Deploy") e `PLANO-DO-PROJETO.md`
   (seções 1/7/13) para **Render (`leilao-ce.onrender.com`)**.
3. Trocar links para `leilaoce.streamlit.app` que existirem por aí.

---

## 7. Operação depois do deploy

**Deploy automático.** Todo push no `main` redeploya — inclusive os commits
`chore: atualiza leiloes.json [auto ...]` do scraper (2×/dia). O deploy é
zero-downtime (o Render só troca quando o novo passa no health check).

**Se o churn de deploy incomodar** (opcional, futuro): ou põe `autoDeploy: false`
no `render.yaml` + um **Deploy Hook** chamado pelo `scraper.yml` no fim do run,
ou passa o dashboard a carregar o `leiloes.json` em runtime (GitHub raw ou um
bucket do Supabase Storage).

**Logs:** Render → serviço → **Logs**. **Métricas** (CPU/RAM): aba **Metrics** —
olhar na 1ª semana para confirmar que 512 MB / 0.5 CPU do Starter aguentam.

**Rollback:** Render → **Deploys** → num deploy anterior → **Rollback to this
deploy**.

**Custos:** Starter US$ 7/mês + banda (100 GB/mês inclusos, depois
US$ 0,10/GB — irrelevante aqui). URL `onrender.com` e TLS: grátis. Subir para
Standard (US$ 25) só se a aba Metrics acusar pressão de RAM/CPU.

---

## Troubleshooting

**App carrega mas fica em "Please wait…" / "Connection error" / reconectando.**
WebSocket do Streamlit barrado pelo proxy. Em `render.yaml`, acrescente ao
`startCommand`: `--server.enableCORS false --server.enableXsrfProtection false`
e faça push.

**Build falha em `pip install`.** Confirme que `requirements-web.txt` está no
`main` e que o `buildCommand` no painel é `pip install -r requirements-web.txt`.

**`ModuleNotFoundError` de `playwright`/`anthropic` no site.** O dashboard não
importa isso. Se aparecer, algum import novo em `dashboard.py`/`auth.py`/
`favorites.py` puxou dependência do scraper — mover para trás de um import
tardio ou adicionar a lib em `requirements-web.txt`.

**Login dá erro de `redirect_to` / volta para a URL errada.** `APP_URL` no
Render e a lista de **Redirect URLs** no Supabase precisam bater
([seção 5](#5-apontar-supabase-e-stripe-para-o-render)).

**Health check falha e o deploy não fica Live.** Confirme
`healthCheckPath: /_stcore/health` e que o `startCommand` usa
`--server.port $PORT`.

**OOM / reinícios frequentes.** Aba Metrics → se a RAM encostar em 512 MB,
subir o Instance Type no painel (Starter → Standard, 2 GB).
