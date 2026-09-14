# Setup da VPS Hostinger — deploy do site (Achadin Leilões)

Guia de migração do site de **Streamlit Community Cloud**
(`leilaoce.streamlit.app`) para uma **VPS da Hostinger**, usando um endereço
`*.sslip.io` (sem domínio próprio) com TLS válido via Let's Encrypt/Certbot.

O scraper **não** muda: continua no GitHub Actions 1×/dia (ver
[`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md)). O Supabase e o Stripe
**não** mudam — só passam a apontar para a URL da VPS.

> **Por que substituir o plano do Render (nunca chegou a subir):** ver
> [`DEPLOY_CHECKLIST.md`](DEPLOY_CHECKLIST.md). O `render.yaml` foi removido —
> este guia é o caminho de deploy atual.

> **Sobre o `sslip.io`:** é um serviço de DNS público que resolve
> `SEU-IP.sslip.io` (com os pontos do IP trocados por hífen, ex.
> `203-0-113-10.sslip.io`) para o próprio IP, sem precisar comprar domínio.
> Como é um domínio de verdade (não um IP nu), o Let's Encrypt emite
> certificado TLS válido para ele normalmente. Se um dia você comprar um
> domínio de verdade, é só trocar o DNS e reemitir o certificado — a
> [seção 6](#6-apontar-supabase-e-stripe-para-a-vps) explica o que mais muda.

---

## Arquitetura depois da migração

| Peça | Onde roda | Muda? |
|---|---|---|
| Site (`dashboard.py`, Streamlit) | **VPS Hostinger**, atrás de Nginx (TLS) | ✅ sai do Community Cloud |
| Scraper (`scraper.py`) | GitHub Actions (cron 1×/dia) | ❌ |
| Deploy automático | GitHub Actions faz SSH na VPS a cada push no `main`: `git pull` + reinstala deps + `systemctl restart` | ✅ novo, substitui o autodeploy de PaaS |
| Banco + Auth | Supabase | só Redirect URLs |
| Cobrança (Checkout + Portal) | Stripe | só as URLs de retorno (via `APP_URL`) |
| Webhook do Stripe | Supabase Edge Function (`*.supabase.co`) | ❌ nada |
| Alertas de lance | GitHub Actions, junto do scraper | ❌ |

Fluxo do dado dos lotes: o Actions gera o `leiloes.json`, dá commit no `main`,
o workflow de deploy faz `git pull` na VPS. O `dashboard.py` já lê o arquivo
com `st.cache_data(ttl=1800)` — em até 30 min os lotes novos aparecem mesmo
sem reiniciar o processo; o passo de deploy reinicia de qualquer forma (mais
simples que separar os dois casos).

---

## Plano de VPS recomendado

**KVM 1** (1 vCPU / 4 GB RAM / 50 GB NVMe / 4 TB banda) — o plano de entrada
da Hostinger. O app não usa pandas/numpy/playwright no processo do site
(ver `requirements-web.txt`), e o `leiloes.json` tem ~650 KB em memória — o
footprint é pequeno mesmo somando SO + Nginx + Certbot + o processo do
Streamlit. Sem plano de rodar a Evolution API (WhatsApp) na mesma máquina por
enquanto (ver `DEPLOY_CHECKLIST.md`, bloco C) — se isso mudar, reavaliar para
KVM 2 (2 vCPU / 8 GB).

### O KVM 1 aguenta a expansão para 1200–1600 lotes?

Sim, com folga confortável — medido, não estimado (2026-09-14, `leiloes.json`
com 558 lotes na época):

| Dimensão | Hoje (558 lotes) | Projeção (1600 lotes) | Impacto no KVM 1 |
|---|---|---|---|
| `leiloes.json` em disco | 632 KB | ~1,8 MB | Irrelevante (50 GB NVMe) |
| Estrutura em memória (Python, `tracemalloc`) | 5,6 MB | ~16 MB (linear) | Irrelevante (4 GB RAM) |
| Filtro + sort por rerun do Streamlit (`dashboard.py`) | 0,21 ms | ~0,59 ms (linear) | Irrelevante (orçamento de rerun é dezenas de ms) |
| Cards renderizados por página | 50 (fixo) | 50 (fixo) | **Não escala com o total** — `ITEMS_PER_PAGE = 50` (`dashboard.py:1047`) pagina antes de renderizar; o filtro/sort acima roda sobre a lista inteira, mas isso é a linha da tabela anterior, não a renderização |

O tamanho do catálogo não é o eixo que algum dia forçaria upgrade de VPS —
nessa dimensão o KVM 1 sobraria até para uma ordem de grandeza a mais de
lotes. O eixo que de fato limita é **sessões simultâneas**: o Streamlit é um
processo único, guarda sessão em RAM por usuário conectado, e cada rerun é
CPU-bound — um vCPU serializa esse trabalho, então muitos usuários ativos ao
mesmo tempo (não o tamanho do catálogo) é o que eventualmente pediria mais
CPU/RAM. Nesse eixo o KVM 1 já é uma melhora sobre o Render Starter que o
time havia validado como suficiente (1 vCPU dedicado vs. 0,5 CPU
compartilhado; 4 GB vs. 512 MB) — daí a recomendação permanecer o KVM 1
também com o crescimento do catálogo para 1200–1600 lotes. Se o gatilho for
esse (mais usuários simultâneos, não mais lotes), o upgrade é só trocar o
Instance Type no painel da Hostinger — sem mudar código.

---

## Checklist

**Provisionamento**
- [ ] VPS KVM 1 criada na Hostinger, Ubuntu 24.04 LTS
- [ ] Acesso SSH com chave (sem senha) confirmado
- [ ] Endereço `SEU-IP.sslip.io` anotado (ex.: IP `203.0.113.10` → `203-0-113-10.sslip.io`)

**Servidor**
- [ ] Passos 1–5 abaixo executados (usuário, firewall, Python/venv, systemd, Nginx+Certbot)
- [ ] `curl https://SEU-IP.sslip.io/_stcore/health` responde `ok`

**Deploy automático**
- [ ] Secrets `VPS_HOST`, `VPS_SSH_KEY`, `VPS_USER` no GitHub Actions ([seção 6](#6-deploy-automático-via-github-actions))
- [ ] `.github/workflows/deploy.yml` no `main`
- [ ] Push de teste dispara o workflow e o site atualiza

**Apontar os serviços externos**
- [ ] Supabase → Auth → URL Configuration com a URL da VPS ([seção 7](#7-apontar-supabase-e-stripe-para-a-vps))
- [ ] Stripe → Customer portal: return URL conferida (cosmético)
- [ ] Teste completo: cadastro, login, paywall, checkout, portal, favoritar

**Fechamento**
- [ ] App no Community Cloud pausado/deletado ([seção 8](#8-desligar-o-community-cloud))
- [ ] `CLAUDE.md` e `PLANO-DO-PROJETO.md` atualizados (deploy = VPS Hostinger)

---

## 1. Provisionar a VPS

1. Hostinger → **VPS** → contratar **KVM 1** (Ubuntu 24.04 LTS, sem painel
   extra — só o SO).
2. Anotar o IP público. Confirmar SSH: `ssh root@SEU-IP`.
3. Montar o endereço sslip.io trocando os pontos do IP por hífen:
   `203.0.113.10` → `203-0-113-10.sslip.io`. Teste: `ping 203-0-113-10.sslip.io`
   deve resolver para o mesmo IP.

## 2. Usuário, firewall e dependências

```bash
# como root
adduser --disabled-password --gecos "" leilao
usermod -aG sudo leilao
mkdir -p /home/leilao/.ssh
cp ~/.ssh/authorized_keys /home/leilao/.ssh/  # reaproveita sua chave
chown -R leilao:leilao /home/leilao/.ssh
chmod 700 /home/leilao/.ssh && chmod 600 /home/leilao/.ssh/authorized_keys

# firewall: só SSH, HTTP, HTTPS
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

apt update && apt install -y python3.11 python3.11-venv git nginx certbot python3-certbot-nginx
```

A partir daqui, logar como `leilao` (`ssh leilao@SEU-IP`), não mais como root.

## 3. Clonar o repositório e criar o ambiente

```bash
cd ~
git clone https://github.com/mounjour/leilao-ce.git
cd leilao-ce
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-web.txt
```

Criar o `.env` (mesmas chaves do `.env` local / do `render.yaml` antigo —
**não** commitado, já está no `.gitignore`):

```bash
nano .env
```

```dotenv
APP_URL=https://SEU-IP.sslip.io
SUPABASE_URL=https://tybfusbovbihrkmcncux.supabase.co
SUPABASE_ANON_KEY=eyJ...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_PRICE_ID=price_...
STRIPE_PLAN_PRICE_LABEL=R$ 47
# EVOLUTION_API_URL / EVOLUTION_API_KEY / EVOLUTION_INSTANCE: deixe de fora —
# instância perdida, ver DEPLOY_CHECKLIST.md bloco C. O site funciona sem elas.
```

> **NÃO** coloque no `.env` do site: `SUPABASE_SERVICE_ROLE_KEY`,
> `ANTHROPIC_API_KEY`, `ZENROWS_API_KEY`, `SCRAPERAPI_KEY`, `OWNER_WHATSAPP`,
> `STRIPE_WEBHOOK_SECRET` — nenhum é usado pelo site (são do scraper/alertas
> ou da Edge Function, e ficam só nos secrets do GitHub Actions/Supabase).

```bash
chmod 600 .env
```

## 4. Serviço systemd

```bash
sudo nano /etc/systemd/system/leilao-ce.service
```

```ini
[Unit]
Description=Achadin Leiloes - dashboard Streamlit
After=network.target

[Service]
Type=simple
User=leilao
WorkingDirectory=/home/leilao/leilao-ce
EnvironmentFile=/home/leilao/leilao-ce/.env
ExecStart=/home/leilao/leilao-ce/.venv/bin/streamlit run dashboard.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --browser.gatherUsageStats false
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now leilao-ce
sudo systemctl status leilao-ce   # deve estar "active (running)"
```

O Streamlit escuta só em `127.0.0.1:8501` (não exposto direto à internet) —
quem recebe tráfego externo é o Nginx, configurado a seguir.

## 5. Nginx + TLS (Certbot)

```bash
sudo nano /etc/nginx/sites-available/leilao-ce
```

```nginx
server {
    listen 80;
    server_name SEU-IP.sslip.io;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/leilao-ce /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Emite o certificado e reescreve o server block pra HTTPS automaticamente
sudo certbot --nginx -d SEU-IP.sslip.io --redirect -m SEU-EMAIL --agree-tos --no-eff-email
```

O `proxy_set_header Upgrade`/`Connection "upgrade"` acima é o equivalente ao
truque de CORS/XSRF que o Render às vezes exigia — sem ele, o WebSocket do
Streamlit não conecta e a página trava em "Please wait…".

Renovação do certificado já vem agendada pelo `certbot` (timer systemd
`certbot.timer` — confirme com `systemctl list-timers | grep certbot`).

Teste: `curl https://SEU-IP.sslip.io/_stcore/health` → deve responder `ok`.

## 6. Deploy automático via GitHub Actions

Gerar um par de chaves **dedicado ao deploy** (não reaproveitar sua chave
pessoal):

```bash
ssh-keygen -t ed25519 -f ~/deploy_leilao_ce -N ""
# cat ~/deploy_leilao_ce.pub >> na VPS: /home/leilao/.ssh/authorized_keys
```

Permitir que o usuário `leilao` reinicie o serviço sem senha (o SSH do
Actions não tem como responder a um prompt de senha do `sudo`):

```bash
sudo visudo -f /etc/sudoers.d/leilao-ce-deploy
```

```
leilao ALL=(root) NOPASSWD: /usr/bin/systemctl restart leilao-ce, /usr/bin/systemctl is-active --quiet leilao-ce
```

No GitHub → repositório → **Settings** → **Secrets and variables** →
**Actions**, criar:

| Secret | Valor |
|---|---|
| `VPS_HOST` | IP da VPS ou `SEU-IP.sslip.io` |
| `VPS_USER` | `leilao` |
| `VPS_SSH_KEY` | conteúdo de `~/deploy_leilao_ce` (a chave **privada**) |

O workflow [`deploy.yml`](../../.github/workflows/deploy.yml) faz SSH na VPS
a cada push no `main`, sincroniza o repositório com `origin/main` (`git
fetch` + `reset --hard` — evita divergência se alguém mexer na VPS na mão),
reinstala `requirements-web.txt` e reinicia o serviço.

## 7. Apontar Supabase e Stripe para a VPS

### 7.1 Confirmar o `APP_URL`
`.env` na VPS → `APP_URL=https://SEU-IP.sslip.io` (sem barra no final;
reiniciar o serviço se mudar: `sudo systemctl restart leilao-ce`). É a partir
daí que `auth.py` monta as URLs do Checkout e do Billing Portal.

### 7.2 Supabase Auth
Supabase → projeto `tybfusbovbihrkmcncux` → **Authentication** → **URL
Configuration**:

- **Site URL:** `https://SEU-IP.sslip.io`
- **Redirect URLs:**
  - `https://SEU-IP.sslip.io`
  - `https://SEU-IP.sslip.io/**`
  - `https://leilaoce.streamlit.app` (mantenha ~1 semana, durante a transição)
  - `http://localhost:8501` (dev local)

> O fluxo PKCE (`auth.py`) redireciona de volta para `APP_URL`; se essa URL
> não estiver na lista, o login quebra com erro de `redirect_to`.

### 7.3 Stripe
- URLs de sucesso/cancelamento do Checkout e o `return_url` do Billing Portal
  são passadas por sessão pelo código (a partir de `APP_URL`) — **nada a
  mudar no painel** para elas.
- Só confira, por estética: Stripe → **Settings** → **Billing** → **Customer
  portal** → se houver um *default return link* no domínio antigo, atualize.
- O **webhook** (`stripe-webhook` no Supabase) continua igual — endpoint
  `*.supabase.co/functions/v1/stripe-webhook`, não depende da URL do site.

### 7.4 Teste final
Repita o checklist abaixo, agora com atenção a: e-mail de confirmação do
Supabase com link da VPS, Checkout retornando para a VPS, portal de cobrança
retornando para a VPS.

- [ ] Página de login/cadastro abre (sem "Please wait…" travado)
- [ ] Cadastro de usuário novo funciona
- [ ] Login funciona e cai no dashboard
- [ ] Sem assinatura → aparece o **paywall**
- [ ] Botão de assinar abre o **Stripe Checkout**
- [ ] Com assinatura ativa → dashboard completo, lotes carregando
- [ ] **Favoritar um lote** salva e reflete no Supabase (sem `EVOLUTION_*`, não dispara WhatsApp — esperado)
- [ ] Menu do usuário → **portal de cobrança** abre

## 8. Desligar o Community Cloud

Só depois de validado (recomendo esperar 3–7 dias).

1. <https://share.streamlit.io> → o app → **Settings** → **Delete app** (ou
   *Pause*, para manter como rollback rápido por mais uns dias).
2. Atualizar no repo: `CLAUDE.md` (linha "Deploy") e `PLANO-DO-PROJETO.md`
   (seções 1/7/13) para **VPS Hostinger**.
3. Trocar links para `leilaoce.streamlit.app` que existirem por aí.

---

## Operação depois do deploy

**Logs:** `sudo journalctl -u leilao-ce -f` (app), `sudo tail -f
/var/log/nginx/error.log` (proxy/TLS).

**Métricas (CPU/RAM):** `htop` ou `free -h` — olhar na 1ª semana para
confirmar que os 4 GB do KVM 1 aguentam com folga.

**Rollback:** `git log` no repo da VPS → `git checkout <commit-anterior>` →
`sudo systemctl restart leilao-ce`. Diferente do Render, não há botão de
rollback com 1 clique — se isso incomodar, considerar manter os 2 últimos
releases em pastas separadas com symlink (over-engineering para o estágio
atual; revisitar se o time crescer).

**Downtime por deploy:** um `systemctl restart` interrompe as conexões
WebSocket ativas por ~2–5s. Sem swap zero-downtime como no Render — aceitável
no volume atual (scraper 1×/dia + pushes ocasionais).

**Custos:** KVM 1 ~R$ 27,99/mês (ou US$ 6,49/mês na promo de assinatura
longa — confirme o valor de renovação antes de assinar). Sem domínio próprio,
sem custo adicional de DNS/TLS (sslip.io + Let's Encrypt são gratuitos).

---

## Troubleshooting

**App carrega mas fica em "Please wait…" / "Connection error" / reconectando.**
Confirme os headers `Upgrade`/`Connection "upgrade"` no bloco Nginx (seção 5)
— sem eles o WebSocket do Streamlit não conecta.

**Certbot falha ao emitir certificado.** Confirme que a porta 80 está liberada
no `ufw` e que `SEU-IP.sslip.io` resolve para o IP certo (`dig SEU-IP.sslip.io`).

**Serviço não sobe (`systemctl status leilao-ce` mostra `failed`).** Ver
`journalctl -u leilao-ce -n 50`. Causas comuns: `.env` com permissão errada
(precisa ser legível pelo usuário `leilao`), dependência faltando no venv.

**Login dá erro de `redirect_to` / volta para a URL errada.** `APP_URL` no
`.env` da VPS e a lista de **Redirect URLs** no Supabase precisam bater
([seção 6](#6-apontar-supabase-e-stripe-para-a-vps)).

**Deploy automático falha no GitHub Actions.** Confira os 3 secrets
(`VPS_HOST`/`VPS_USER`/`VPS_SSH_KEY`) e que a chave pública correspondente
está em `/home/leilao/.ssh/authorized_keys` na VPS.

**OOM / reinícios frequentes.** `free -h` → se a RAM apertar nos 4 GB do
KVM 1 (improvável para este app), migrar para KVM 2 no painel da Hostinger —
é redimensionamento, não recriação da VPS.
