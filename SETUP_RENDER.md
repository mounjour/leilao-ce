# Setup do Render — deploy do site (Achadin Leilões)

Guia de migração do site de **Streamlit Community Cloud** (`leilaoce.streamlit.app`)
para o **Render**, com domínio próprio comprado no Registro.br.

O scraper **não** muda: continua no GitHub Actions 2×/dia (ver
[`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md)). O Supabase e o Stripe
**não** mudam — só passam a apontar para o domínio novo.

---

## Arquitetura depois da migração

| Peça | Onde roda | Muda? |
|---|---|---|
| Site (`dashboard.py`, Streamlit) | **Render** (Web Service, plano Standard) | ✅ sai do Community Cloud |
| Scraper (`scraper.py`) | GitHub Actions (cron 2×/dia) | ❌ |
| Banco + Auth | Supabase | só Redirect URLs |
| Cobrança (Checkout + Portal) | Stripe | só as URLs de retorno (via `APP_URL`) |
| Webhook do Stripe | Supabase Edge Function (`*.supabase.co`) | ❌ nada |
| Alertas de lance | GitHub Actions, junto do scraper | ❌ |

Fluxo do dado dos lotes: o Actions gera o `leiloes.json`, dá commit no `main`,
o Render vê o push e redeploya o site com os dados novos. Igual ao que o
Community Cloud faz hoje.

---

## Checklist de migração

Marque conforme for fazendo. O passo a passo detalhado está nas seções abaixo.

**Preparação**
- [ ] Juntar os valores dos segredos (do `.env` local e/ou dos Secrets do app no Community Cloud) — lista na [seção 1](#1-juntar-os-segredos)
- [ ] `render.yaml` e `requirements-web.txt` commitados e no `main` ([seção 2](#2-subir-os-arquivos-novos))

**Render**
- [ ] Conta no Render criada e repositório `mounjour/leilao-ce` conectado
- [ ] Blueprint aplicado, os 3 serviços não — só o Web Service `leilao-ce` ([seção 3](#3-criar-o-serviço-no-render))
- [ ] Todas as envs `sync: false` preenchidas no painel
- [ ] `APP_URL` = a URL `*.onrender.com` provisória (por enquanto)
- [ ] Primeiro deploy verde; `/_stcore/health` responde `ok`
- [ ] Teste manual na URL `*.onrender.com` passou ([seção 4](#4-testar-na-url-provisória))

**Domínio**
- [ ] Domínio comprado no Registro.br
- [ ] Domínio(s) adicionado(s) em Render → Settings → Custom Domains
- [ ] Registros DNS criados no painel do Registro.br exatamente como o Render mandou
- [ ] Render marcou o domínio como **Verified** e emitiu o certificado TLS ([seção 5](#5-comprar-e-ligar-o-domínio))

**Cutover**
- [ ] `APP_URL` trocado para `https://SEU-DOMINIO` e o serviço redeployado
- [ ] Supabase → Auth → URL Configuration: Site URL + Redirect URLs com o domínio novo ([seção 6](#6-cutover-app_url-supabase-e-stripe))
- [ ] Stripe → Customer portal: default return URL conferida (cosmético)
- [ ] Teste completo no domínio novo: cadastro, login, paywall, checkout, portal, favoritar
- [ ] App no Community Cloud pausado/deletado ([seção 7](#7-desligar-o-community-cloud))
- [ ] `CLAUDE.md` e `PLANO-DO-PROJETO.md` atualizados (deploy = Render)

---

## 1. Juntar os segredos

O Render vai pedir estes valores ao aplicar o Blueprint. Pegue do `.env` local
(não versionado) ou de **Streamlit Community Cloud → o app → Settings →
Secrets**:

| Env | O que é |
|---|---|
| `SUPABASE_URL` | URL do projeto Supabase (`https://tybfusbovbihrkmcncux.supabase.co`) |
| `SUPABASE_ANON_KEY` | chave `anon` / `public` do Supabase |
| `STRIPE_SECRET_KEY` | chave secreta **live** (`sk_live_...`) |
| `STRIPE_PUBLISHABLE_KEY` | chave publicável **live** (`pk_live_...`) |
| `STRIPE_PRICE_ID` | ID do preço da assinatura (`price_...`) |
| `EVOLUTION_API_URL` | URL da instância Evolution |
| `EVOLUTION_API_KEY` | API key da Evolution |
| `EVOLUTION_INSTANCE` | nome da instância |

> `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `ZENROWS_API_KEY`,
> `SCRAPERAPI_KEY`, `OWNER_WHATSAPP` **não vão para o Render** — são só do
> scraper/alertas, que rodam no GitHub Actions.

---

## 2. Subir os arquivos novos

No PowerShell, na pasta do projeto:

```powershell
git status
git add render.yaml requirements-web.txt SETUP_RENDER.md
git commit -m "chore: blueprint e checklist de deploy no Render"
git push
```

> Isso ainda não muda nada em produção — o Community Cloud ignora esses
> arquivos. Só passam a existir no repo para o Render ler.

---

## 3. Criar o serviço no Render

1. Criar conta em <https://render.com> (pode entrar com o GitHub).
2. **New** → **Blueprint**.
3. Conectar/autorizar o repositório `mounjour/leilao-ce`. O Render lê o
   `render.yaml` e mostra **1 serviço**: o Web Service `leilao-ce`.
4. Ele lista as variáveis `sync: false`. Preencha cada uma com os valores da
   [seção 1](#1-juntar-os-segredos). Em `APP_URL`, por enquanto, coloque
   **a URL que o Render vai gerar** (padrão `https://leilao-ce.onrender.com` —
   confirme o nome exato na tela; se estiver tomado o Render acrescenta um
   sufixo).
5. **Apply**. O primeiro build roda `pip install -r requirements-web.txt`
   (~30–60 s) e sobe o Streamlit.
6. Quando o deploy ficar **Live**, abra `https://SEU-APP.onrender.com/_stcore/health`
   — tem que responder `ok`.

> **Plano:** o `render.yaml` já vem com `plan: standard` (2 GB / 1 CPU,
> US$ 25/mês, sempre ligado). Para baixar para `starter` (US$ 7) depois,
> troque no painel em **Settings → Instance Type** — não precisa mexer em
> código.

---

## 4. Testar na URL provisória

Na `https://SEU-APP.onrender.com`, confira **antes de mexer no domínio**:

- [ ] Página de login/cadastro abre (sem "Please wait…" travado — se travar, ver [Troubleshooting](#troubleshooting))
- [ ] Cadastro de usuário novo funciona (chega o e-mail do Supabase)
- [ ] Login funciona e cai no dashboard
- [ ] Sem assinatura → aparece o **paywall** (`render_paywall`)
- [ ] Botão de assinar abre o **Stripe Checkout** (pode usar cartão de teste se a chave for de teste; em `live`, cancele antes de pagar)
- [ ] Com assinatura ativa → dashboard completo, lotes carregando do `leiloes.json`
- [ ] **Favoritar um lote** dispara o WhatsApp (Evolution) e grava/reflete no Supabase
- [ ] Menu do usuário → **portal de cobrança** (Billing Portal) abre

> Se algo depender do domínio (link de e-mail do Supabase apontando para a URL
> antiga), é esperado nesta fase — resolve no cutover (seção 6).

---

## 5. Comprar e ligar o domínio

### 5.1 Comprar no Registro.br

1. <https://registro.br> → pesquisar o domínio → registrar (`.com.br` = R$ 40/ano).
2. Precisa de CPF/CNPJ. O WHOIS já sai privado para pessoa física.

### 5.2 Adicionar no Render

1. Render → o serviço `leilao-ce` → **Settings** → **Custom Domains** → **Add Custom Domain**.
2. Adicione **os dois**: `SEU-DOMINIO.com.br` (apex) e `www.SEU-DOMINIO.com.br`.
3. O Render mostra, para cada um, **o registro DNS exato** a criar — normalmente:
   - apex → um registro **A** apontando para um IP do Render;
   - `www` → um registro **CNAME** apontando para `SEU-APP.onrender.com`.
   Anote os valores exatos que aparecerem (não invente/copie de outro lugar).

### 5.3 Criar os registros no Registro.br

1. <https://painel.registro.br> → seu domínio → **DNS** → **Editar Zona**.
2. Crie os registros exatamente como o Render pediu (A para o apex, CNAME para
   o `www`). TTL padrão serve.
3. Salve. Propagação costuma levar de minutos a algumas horas.

### 5.4 Esperar o Render verificar

- Render → Custom Domains fica **Verified** quando o DNS resolve.
- O certificado TLS (Let's Encrypt) é emitido automático logo depois — sem
  ação sua.
- Deixe um dos dois como **primary** (ex.: o apex) e o Render redireciona o
  outro sozinho.

---

## 6. Cutover: `APP_URL`, Supabase e Stripe

Faça na ordem. Só depois que o domínio estiver **Verified** com TLS.

### 6.1 `APP_URL` no Render

1. Render → `leilao-ce` → **Environment** → editar `APP_URL` para
   `https://SEU-DOMINIO.com.br` (sem barra no final).
2. Salvar → o Render redeploya. É isso que faz o Checkout e o Billing Portal
   voltarem para o domínio certo (o código monta as URLs a partir de
   `APP_URL`, em `auth.py`).

### 6.2 Supabase Auth

Supabase → projeto `tybfusbovbihrkmcncux` → **Authentication** → **URL
Configuration**:

- **Site URL:** `https://SEU-DOMINIO.com.br`
- **Redirect URLs:** adicione (mantendo as antigas por ~1 semana):
  - `https://SEU-DOMINIO.com.br`
  - `https://SEU-DOMINIO.com.br/**`
  - `https://SEU-APP.onrender.com` (transição)
  - `http://localhost:8501` (dev local)

> O fluxo PKCE (`auth.py`) redireciona de volta para `APP_URL`; se essa URL não
> estiver na lista de Redirect URLs, o login quebra com erro de
> `redirect_to`.

### 6.3 Stripe

- As URLs de sucesso/cancelamento do Checkout e o `return_url` do Billing
  Portal são passadas por sessão pelo código (a partir de `APP_URL`) — **não
  há nada a mudar no painel** do Stripe para elas.
- Só confira, por estética: Stripe → **Settings** → **Billing** → **Customer
  portal** → se houver um *default return link* fixado no domínio antigo,
  atualize.
- O **webhook** (`stripe-webhook` no Supabase) continua igual — endpoint
  `*.supabase.co/functions/v1/stripe-webhook`, não depende do domínio.

### 6.4 Teste final no domínio novo

Repita o checklist da [seção 4](#4-testar-na-url-provisória), agora em
`https://SEU-DOMINIO.com.br`, com atenção a: e-mail de confirmação do Supabase
chegando com link do domínio novo, Checkout retornando para o domínio novo,
portal de cobrança retornando para o domínio novo.

---

## 7. Desligar o Community Cloud

Só depois de 100% validado no domínio novo (recomendo esperar 3–7 dias).

1. <https://share.streamlit.io> → o app → **Settings** → **Delete app** (ou
   só *Reboot/Pause* se quiser manter como rollback rápido por mais uns dias).
2. Atualizar no repo: `CLAUDE.md` e `PLANO-DO-PROJETO.md` (seções de
   Deploy/Hospedagem/Stack) para dizer **Render + domínio próprio**.
3. Se houver link para `leilaoce.streamlit.app` em algum lugar (bio, material
   de divulgação), trocar.

---

## 8. Operação depois do deploy

**Deploy automático.** Todo push no `main` redeploya — inclusive os commits
`chore: atualiza leiloes.json [auto ...]` do scraper (2×/dia). O deploy é
zero-downtime (o Render só troca quando o novo passa no health check).

**Se o churn de deploy incomodar** (opcional, futuro): ou põe `autoDeploy: false`
no `render.yaml` + um **Deploy Hook** chamado pelo `scraper.yml` no fim do run,
ou passa o dashboard a carregar o `leiloes.json` em runtime (GitHub raw ou um
bucket do Supabase Storage) e aí o site nem precisa redeployar para atualizar
dado. Fora do escopo desta migração.

**Logs:** Render → serviço → **Logs** (tempo real). **Métricas** (CPU/RAM):
aba **Metrics** — olhar na 1ª semana para confirmar que 2 GB sobra.

**Rollback:** Render → **Deploys** → num deploy anterior → **Rollback to this
deploy**.

**Custos:** Standard US$ 25/mês + banda (100 GB/mês inclusos, depois
US$ 0,10/GB — irrelevante aqui). Domínio R$ 40/ano. TLS e custom domain: grátis.

---

## Troubleshooting

**App carrega mas fica em "Please wait…" / "Connection error" / reconectando.**
WebSocket do Streamlit barrado pelo proxy. Em `render.yaml`, acrescente ao
`startCommand`:
`--server.enableCORS false --server.enableXsrfProtection false`
e faça push.

**Build falha em `pip install`.** Confirme que `requirements-web.txt` está no
`main` e que o `buildCommand` no painel é `pip install -r requirements-web.txt`.

**`ModuleNotFoundError` de `playwright`/`anthropic` no site.** O dashboard não
deveria importar isso. Se aparecer, algum import novo em `dashboard.py`/
`auth.py`/`favorites.py` puxou dependência do scraper — mover para trás de um
import tardio ou adicionar a lib em `requirements-web.txt`.

**Login dá erro de `redirect_to` / volta para a URL errada.** `APP_URL` no
Render e a lista de **Redirect URLs** no Supabase precisam bater com o domínio
que está sendo usado ([seção 6](#6-cutover-app_url-supabase-e-stripe)).

**Health check falha e o deploy não fica Live.** Confirme
`healthCheckPath: /_stcore/health` e que o `startCommand` usa
`--server.port $PORT` (o Render injeta `$PORT`).

**OOM / reinícios frequentes.** Aba Metrics → se a RAM encostar em 2 GB, subir
o Instance Type no painel (não precisa mexer em código).
