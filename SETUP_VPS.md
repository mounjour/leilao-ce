# Setup do deploy — VPS Hostinger + Coolify

Guia de migração do site (`dashboard.py` / Streamlit) de **Streamlit Community
Cloud** (`leilaoce.streamlit.app`) para uma **VPS na Hostinger** com **Coolify**
por cima, e domínio próprio comprado na própria Hostinger.

Coolify é um "Render/Heroku open-source" que roda na sua máquina: deploy por
git-push, HTTPS automático (Traefik + Let's Encrypt), restart automático, logs e
rollback pelo painel. Você troca ~metade do custo do Render por administrar o
sistema operacional da VPS.

O scraper **não** muda: continua no GitHub Actions 2×/dia (ver
[`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md)). Supabase e Stripe **não**
mudam — só passam a apontar para o domínio novo.

---

## Arquitetura depois da migração

| Peça | Onde roda | Muda? |
|---|---|---|
| Site (`dashboard.py`, Streamlit, via `Dockerfile`) | **VPS Hostinger** (Coolify) | ✅ sai do Community Cloud |
| Scraper (`scraper.py`) | GitHub Actions (cron 2×/dia) | ❌ |
| Banco + Auth | Supabase | só Redirect URLs |
| Cobrança (Checkout + Portal) | Stripe | só as URLs de retorno (via `APP_URL`) |
| Webhook do Stripe | Supabase Edge Function (`*.supabase.co`) | ❌ nada |
| Alertas de lance | GitHub Actions, junto do scraper | ❌ |

Fluxo do dado dos lotes: o Actions gera o `leiloes.json`, dá commit no `main`,
o GitHub dispara o webhook do Coolify, o Coolify rebuilda a imagem (o
`Dockerfile` faz `COPY . .`) e troca a versão sem downtime. Mesmo efeito do
Community Cloud hoje.

---

## Checklist

**Contratar e preparar a VPS** ([seção 1](#1-contratar-na-hostinger), [2](#2-travar-o-servidor))
- [ ] VPS KVM 2 (2 vCPU, 8 GB) + domínio contratados na Hostinger
- [ ] Ubuntu 24.04 LTS instalado
- [ ] Acesso SSH por **chave** funcionando; login por senha desativado
- [ ] `ufw`, `fail2ban`, `unattended-upgrades` ativos

**Coolify** ([seção 3](#3-instalar-o-coolify), [4](#4-criar-o-serviço-no-coolify))
- [ ] Coolify instalado, painel acessível em `http://IP_DA_VPS:8000`
- [ ] Conta admin criada
- [ ] Repositório `mounjour/leilao-ce` conectado (GitHub App)
- [ ] Recurso criado: build pack **Dockerfile**, porta **8501**
- [ ] Variáveis de ambiente preenchidas ([tabela](#variáveis-de-ambiente))
- [ ] Deploy manual verde; container **healthy**
- [ ] "Automatic Deployment" ligado (webhook no repo)

**Domínio** ([seção 5](#5-domínio-e-dns))
- [ ] `A` records (`@` e `www`) apontando para o IP da VPS, no DNS da Hostinger
- [ ] Domínio adicionado no recurso do Coolify; certificado emitido (cadeado ok)

**Cutover** ([seção 6](#6-cutover-app_url-supabase-e-stripe))
- [ ] `APP_URL` trocado para `https://SEU-DOMINIO` e redeploy
- [ ] Supabase → Auth → URL Configuration com o domínio novo
- [ ] Stripe → Customer portal: return URL conferida
- [ ] Teste completo no domínio: cadastro, login, paywall, checkout, portal, favoritar
- [ ] App no Community Cloud pausado/deletado
- [ ] `CLAUDE.md` e `PLANO-DO-PROJETO.md` atualizados (deploy = VPS/Coolify)

---

## 0. O que só você pode fazer

| Item | Onde |
|---|---|
| Contratar a VPS + o domínio | hostinger.com.br |
| Rodar os comandos de SSH (travar servidor, instalar Coolify) | terminal, conectado na VPS |
| Criar a conta admin do Coolify e conectar o GitHub | painel do Coolify |
| Colar os segredos (Supabase/Stripe) | painel do Coolify |
| Criar os registros DNS | painel da Hostinger |

Os valores de `SUPABASE_*` e `STRIPE_*` você já tem. `EVOLUTION_*` (WhatsApp ao
favoritar) ficam **em branco** — o site funciona sem, e isso já não roda hoje.

---

## 1. Contratar na Hostinger

1. **VPS** → plano **KVM 2** (2 vCPU, 8 GB RAM, ~100 GB NVMe). O KVM 1 (4 GB)
   roda, mas o Coolify sozinho come ~2 GB e os builds apertam.
2. Sistema operacional: **Ubuntu 24.04 LTS** (imagem limpa; **não** use o
   template "Coolify" pré-pronto da Hostinger — a gente instala na mão para
   passar antes pelo endurecimento do servidor).
3. **Domínio**: registre o `.com.br` no mesmo carrinho (ex.: `achadinleiloes.com.br`).
4. Anote o **IP público** da VPS e a senha de root inicial.

## 2. Travar o servidor

Conecte: `ssh root@IP_DA_VPS`. Depois:

```bash
# usuário sem privilégio de root para o dia a dia
adduser deploy
usermod -aG sudo deploy

# leve sua chave pública para os dois usuários (rode no SEU PC, não na VPS):
#   ssh-copy-id deploy@IP_DA_VPS
#   ssh-copy-id root@IP_DA_VPS

# firewall
apt update && apt install -y ufw fail2ban unattended-upgrades
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp        # painel do Coolify (pode fechar depois de pôr atrás de domínio)
ufw --force enable

# só chave, sem senha
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# updates de segurança automáticos
dpkg-reconfigure -f noninteractive unattended-upgrades
```

> Teste abrir uma **nova** sessão SSH com a chave **antes** de fechar a atual,
> para não se trancar do lado de fora.

## 3. Instalar o Coolify

Como root na VPS:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Ao terminar, abra **`http://IP_DA_VPS:8000`** no navegador, crie a **conta admin**
(primeiro cadastro vira dono) e finalize o onboarding — o Coolify registra a
própria VPS como servidor "localhost".

## 4. Criar o serviço no Coolify

1. **Sources** → conecte o **GitHub App** do Coolify à sua conta e dê acesso ao
   repo `mounjour/leilao-ce`. (Isso é o que habilita o deploy automático.)
2. **Projects** → **+ New** → um projeto (ex.: `achadin`) → ambiente `production`.
3. **+ New Resource** → **Private Repository (with GitHub App)** → escolha
   `mounjour/leilao-ce`, branch **`main`**.
4. Configuração do recurso:
   - **Build Pack:** `Dockerfile`
   - **Dockerfile Location:** `/Dockerfile`
   - **Ports Exposes:** `8501`
   - **Health Check Path:** `/_stcore/health` (porta `8501`) — ou deixe usar o
     `HEALTHCHECK` do próprio `Dockerfile`.
5. **Environment Variables** → adicione a tabela abaixo.
6. **Deploy**. Acompanhe em **Logs**. Quando o container ficar **healthy**, abra
   a URL temporária que o Coolify gera (`http://IP:porta` ou o subdomínio
   `sslip.io` que ele oferece) e confira `/_stcore/health` → `ok`.
7. Ligue **Automatic Deployment** nas settings do recurso — o Coolify grava um
   webhook no repo; a partir daí, `push` no `main` redeploya sozinho.

### Variáveis de ambiente

| Variável | Valor |
|---|---|
| `APP_URL` | **por enquanto** a URL temporária do Coolify; troca no cutover |
| `SUPABASE_URL` | `https://tybfusbovbihrkmcncux.supabase.co` |
| `SUPABASE_ANON_KEY` | o `eyJ…` (chave anon/pública) |
| `STRIPE_SECRET_KEY` | `sk_test_…` por enquanto; `sk_live_…` no cutover se o site cobra de verdade |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_…` (idem) |
| `STRIPE_PRICE_ID` | `price_1TYmBh2KWJL12IMokdOGWIR1` (confirme se é o preço certo) |
| `STRIPE_PLAN_PRICE_LABEL` | `R$ 47` |
| `EVOLUTION_API_URL` | (em branco) |
| `EVOLUTION_API_KEY` | (em branco) |
| `EVOLUTION_INSTANCE` | (em branco) |

**Não** coloque `ANTHROPIC_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`ZENROWS_API_KEY`, `SCRAPERAPI_KEY`, `OWNER_WHATSAPP` nem `STRIPE_WEBHOOK_SECRET`
— nenhum é usado pelo site.

## 5. Domínio e DNS

1. Hostinger → **Domínios** → `SEU-DOMINIO.com.br` → **DNS / Nameservers** →
   **Gerenciar registros DNS**.
2. Crie:
   - `A` — host `@` — valor: **IP da VPS**
   - `A` — host `www` — valor: **IP da VPS**
3. Espere propagar (minutos a algumas horas). Cheque com
   `nslookup SEU-DOMINIO.com.br`.
4. No Coolify → recurso → **Domains** → adicione
   `https://SEU-DOMINIO.com.br` **e** `https://www.SEU-DOMINIO.com.br`.
   O Coolify configura o Traefik e emite o Let's Encrypt automaticamente
   (precisa do DNS já resolvendo e das portas 80/443 abertas no `ufw`).
5. Defina o apex como principal e um redirect `www → apex` (opção no próprio
   campo de domínio do Coolify).

## 6. Cutover: `APP_URL`, Supabase e Stripe

Só depois do cadeado (HTTPS) funcionando no domínio.

### 6.1 `APP_URL` no Coolify
Recurso → Environment Variables → `APP_URL` = `https://SEU-DOMINIO.com.br`
(sem barra no final) → **Redeploy**. É isso que faz o Stripe Checkout e o portal
de cobrança voltarem para o domínio certo (`auth.py` monta as URLs a partir daí).

### 6.2 Supabase Auth
Supabase → projeto `tybfusbovbihrkmcncux` → **Authentication** → **URL
Configuration**:
- **Site URL:** `https://SEU-DOMINIO.com.br`
- **Redirect URLs** (mantenha as antigas por ~1 semana):
  - `https://SEU-DOMINIO.com.br`
  - `https://SEU-DOMINIO.com.br/**`
  - a URL temporária do Coolify (transição)
  - `http://localhost:8501` (dev local)

> O login (fluxo PKCE) redireciona de volta para `APP_URL`; se essa URL não
> estiver na lista, o login quebra com erro de `redirect_to`.

### 6.3 Stripe
- URLs de sucesso/cancelamento do Checkout e o `return_url` do portal são
  passadas por sessão pelo código (a partir de `APP_URL`) — **nada a mudar no
  painel** para elas.
- Só confira, por estética: Stripe → **Settings** → **Billing** → **Customer
  portal** → se houver um *default return link* no domínio antigo, atualize.
- O **webhook** (`stripe-webhook` no Supabase) não muda — endpoint
  `*.supabase.co/functions/v1/stripe-webhook`.

### 6.4 Teste final
No domínio novo: e-mail de confirmação do Supabase com link do domínio novo,
Checkout retornando ao domínio novo, portal retornando ao domínio novo,
favoritar salvando.

## 7. Desligar o Community Cloud

Só depois de 3–7 dias validado no domínio novo.

1. <https://share.streamlit.io> → o app → **Settings** → **Delete app** (ou
   *Pause*, para manter como rollback rápido por mais uns dias).
2. Atualizar no repo: `CLAUDE.md` (linha "Deploy") e `PLANO-DO-PROJETO.md`
   (seções 1/7/13) para **VPS Hostinger + Coolify**.
3. Trocar links para `leilaoce.streamlit.app` que existirem por aí.

---

## 8. Operação

**Deploy:** `push` no `main` → webhook → Coolify rebuilda e troca (sem
downtime, espera o healthcheck). Inclui os commits `chore: atualiza leiloes.json`
do scraper, 2×/dia.

**Rollback:** Coolify → recurso → **Deployments** → num deploy anterior →
**Rollback**.

**Logs:** Coolify → recurso → **Logs**. **Notificações:** Coolify → Settings →
Notifications (e-mail/Telegram/Discord) → ligue "deployment failed" e
"container unhealthy".

**Updates do SO:** `unattended-upgrades` cuida dos patches; reinicie a VPS de
vez em quando para pegar kernel novo (`sudo reboot`, ~1 min fora do ar).

**Updates do Coolify:** painel → **Settings** → **Update** (ou ligue o
auto-update).

**Backup:** o site é stateless — a fonte de verdade é o repo (GitHub) + o
Supabase (que tem backup próprio). Só vale exportar a config do **Coolify**
(Settings → Backup, opcionalmente para um bucket S3).

**Custos:** VPS KVM 2 ~R$ 55–70/mês (plano longo; mais no mensal) + domínio
`.com.br` ~R$ 40–60/ano. **~R$ 60–75/mês**, contra ~R$ 135/mês do Render Standard.

---

## Troubleshooting

**App carrega mas fica em "Please wait…" / reconectando.** WebSocket do Streamlit
barrado. No Coolify, em **Custom Start Command** do recurso, use:
`streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false`

**502 / Bad Gateway depois do deploy.** Confirme **Ports Exposes = 8501** no
Coolify e que o container subiu (aba Logs).

**Certificado não emite.** DNS precisa resolver para o IP da VPS e as portas
80/443 abertas no `ufw`. Veja os logs do Traefik/Proxy no Coolify.

**Build falha por falta de memória.** É por isso que o plano é KVM 2 (8 GB). Não
tente no KVM 1 se o build estourar.

**Perdi o acesso ao painel do Coolify.** Ele fica em `:8000`. Garanta
`ufw allow 8000/tcp`, ou acesse por túnel: `ssh -L 8000:localhost:8000 deploy@IP_DA_VPS`.

**Login dá erro de `redirect_to`.** `APP_URL` no Coolify e a lista de Redirect
URLs no Supabase precisam bater com o domínio em uso ([6.2](#62-supabase-auth)).
