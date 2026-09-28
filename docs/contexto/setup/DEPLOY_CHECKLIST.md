# Checklist de deploy — Achadin Leilões

Passo a passo para fechar a migração do site para uma **VPS Hostinger** e
reativar o que está pendente em volta (Evolution API, backup, IA).

Ordem de execução: os blocos **A → B** são o caminho crítico do site;
**C → G** podem ser feitos em paralelo; **H → I** são o fechamento.

Referências: [`SETUP_HOSTINGER_VPS.md`](SETUP_HOSTINGER_VPS.md), [`SETUP_BACKUP_DB.md`](SETUP_BACKUP_DB.md),
[`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md), [`deploy.yml`](../../.github/workflows/deploy.yml).

---

## A. VPS Hostinger — subir o site

- [x] VPS **KVM 1** (1 vCPU / 4 GB RAM) contratada na Hostinger, Ubuntu 24.04 LTS
- [x] Acesso SSH confirmado; endereço `2-25-223-119.sslip.io` anotado
- [x] Usuário `leilao` criado (com sudo), firewall (`ufw`) e dependências instalados (seções 1–2 do guia)
- [x] Repositório clonado, venv criado, `requirements-web.txt` instalado (seção 3)
- [x] `.env` criado na VPS com os segredos do site:
  - [x] `SUPABASE_URL` = `https://tybfusbovbihrkmcncux.supabase.co`
  - [x] `SUPABASE_ANON_KEY` (chave `anon` / `public`, o `eyJ…`)
  - [x] `STRIPE_SECRET_KEY` — **`sk_live_…`** se o site cobra de verdade (`sk_test_…` só para validar sem cobrar)
  - [X] `STRIPE_PUBLISHABLE_KEY` — `pk_live_…` / `pk_test_…` (mesmo modo da secret)
  - [x] `STRIPE_PRICE_ID` = `price_…` — **confirmar que é o preço certo** (e que bate com o rótulo `R$ 47`)
    - [ ] Estão com chaves de teste, trocar para chabes reais depois
  - [x] `APP_URL` = `https://2-25-223-119.sslip.io` (sem barra no final)
  - [ ] **3 `EVOLUTION_*` deixe de fora por enquanto** (bloco C)
- [x] Serviço systemd `leilao-ce` criado e ativo (seção 4)
- [x] Nginx + Certbot configurados, certificado TLS emitido para `2-25-223-119.sslip.io` (seção 5)
- [x] Abrir `https://2-25-223-119.sslip.io/_stcore/health` → tem que responder `ok`
- [x] Se o app abrir mas travar em "Please wait…" / "Connection error": conferir os headers `Upgrade`/`Connection "upgrade"` no bloco Nginx

## B. Apontar Supabase e Stripe para a URL da VPS

- [x] **Supabase** → projeto `tybfusbovbihrkmcncux` → **Authentication** → **URL Configuration**:
  - [x] **Site URL:** `https://2-25-223-119.sslip.io`
  - [x] **Redirect URLs:** `https://2-25-223-119.sslip.io`, `https://2-25-223-119.sslip.io/**`, `https://leilaoce.streamlit.app` (manter ~1 semana), `http://localhost:8501`
- [ ] **Stripe** → Settings → Billing → Customer portal → se houver *default return link* no domínio antigo, atualizar (cosmético; o código já passa as URLs por sessão via `APP_URL`)
- [x] **Webhook do Stripe:** nada a fazer — o endpoint é `*.supabase.co/functions/v1/stripe-webhook`, não depende da URL do site
- [x] **Deploy automático:** secrets `VPS_HOST`/`VPS_USER`/`VPS_SSH_KEY` no GitHub Actions e `sudoers` configurado para restart sem senha (seção 6 do guia) — configurado 2026-09-15, aguardando o próximo push no `main` disparar de verdade
- [x] **Teste E2E** em `https://2-25-223-119.sslip.io`:
  - [x] Página de login/cadastro abre sem travar
  - [x] Cadastro novo funciona (chega e-mail do Supabase com link da VPS)
  - [X] Login cai no dashboard
  - [x] Sem assinatura → aparece o paywall
  - [x] Botão de assinar abre o Stripe Checkout (cartão de teste se chave `test`; em `live`, cancelar antes de pagar)
  - [x] Com assinatura ativa → dashboard completo, lotes carregando
  - [x] Favoritar um lote salva e reflete no Supabase
  - [x] Menu do usuário → portal de cobrança abre e volta pra VPS

## C. Evolution API (WhatsApp) — opcional, mas hoje está desligado

O envio de WhatsApp (favoritar um lote → `favorites.py`; alertas de lance →
`alertas.py`; aviso de fonte zerada → `scraper_health.py`) **não funciona hoje** —
a instância da Evolution se perdeu e as credenciais não estão salvas em lugar
recuperável. O site sobe e opera sem isso.

- [ ] **Decidir:** reativar WhatsApp agora ou deixar para depois? (se depois, pule este bloco — nada quebra)
- [ ] Subir/recriar uma instância da **Evolution API** (self-host na própria VPS Hostinger — reavaliar plano para KVM 2 se for essa a rota — ou provedor gerenciado)
- [ ] Parear o número do WhatsApp (QR code) e nomear a instância
- [ ] Anotar os 3 valores: `EVOLUTION_API_URL` (base, sem `/`), `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`
- [ ] Colocar os 3 no `.env` da VPS (é o que `favorites.py` usa quando alguém favorita) e reiniciar o serviço (`sudo systemctl restart leilao-ce`)
- [ ] Colocar os 3 como **secrets do GitHub Actions** (Settings → Secrets → Actions) — usados por `alertas.py` e `scraper_health.py` no `scraper.yml`
- [ ] Testar: favoritar um lote no site → chega mensagem; rodar `python teste_alerta.py` local para o disparo real de alerta

## D. Secrets do GitHub Actions

- [ ] `OWNER_WHATSAPP` — número do dono, para o health check do scraper avisar quando uma fonte zera (ausente = só `::warning::` no log, sem WhatsApp)
- [ ] `SUPABASE_DB_URL` — connection string do **Session pooler** (porta **5432**; o Transaction pooler 6543 não serve para `pg_dump`). Para o `backup-db.yml` (bloco E)
- [ ] Conferir que os já existentes continuam válidos: `ANTHROPIC_API_KEY`, `ZENROWS_API_KEY`, `SCRAPERAPI_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

## E. Backup do Postgres (workflow já commitado, falta ativar)

- [ ] Configurar o secret `SUPABASE_DB_URL` (bloco D) — passo a passo na seção "Configuração" do [`SETUP_BACKUP_DB.md`](SETUP_BACKUP_DB.md)
- [ ] Actions → **Backup do banco (Supabase)** → **Run workflow** → conferir que o artifact `supabase-<timestamp>.sql.gz` aparece no fim do run
- [ ] **Testar 1 restauração** num projeto Supabase descartável (um backup nunca testado não é um backup)
- [ ] Decidir a cópia off-site mensal (o artifact do Actions expira em 90 dias) — baixar 1 por mês, ou evoluir o workflow para mandar direto a um bucket

## F. IA (Anthropic)

- [ ] Recarregar crédito da Anthropic — destrava a análise de estado dos lotes (`estado` / `selo`), hoje toda em fallback "Não informado". Não bloqueia o deploy, mas o painel fica com dado pobre até isso

## G. Domínio próprio (opcional)

Hoje o site usa `2-25-223-119.sslip.io` (sem domínio, TLS via Let's Encrypt
comum). Trocar por um domínio de verdade é opcional, mas fica mais fácil de
divulgar e de confiar do que um endereço com IP no meio.

- [x] Buscar alternativas de nome nos domínios **grátis/baratos da
      Hostinger** — na primeira busca só `achadinleiloes.tech` apareceu
      disponível (`.com`, `.com.br` etc. já estavam ocupados); tentar outras
      variações de nome (não só "achadinleiloes") para ver se aparece algum
      TLD mais popular (`.com`, `.com.br`, `.online`, `.site`) em vez de cair
      sempre no `.tech`
  - Conclusão: todos os domínios pesquisados caem no `.tech`
- [ ] Registrar o domínio escolhido
- [ ] Apontar o DNS do domínio para o IP da VPS (`2.25.223.119`)
- [ ] Reemitir o certificado TLS pro domínio novo: `sudo certbot --nginx -d
      SEU-DOMINIO --redirect -m SEU-EMAIL --agree-tos --no-eff-email`
      (seção 5 do `SETUP_HOSTINGER_VPS.md`)
- [ ] Atualizar `APP_URL` no `.env` da VPS e reiniciar o serviço
- [ ] Atualizar Site URL / Redirect URLs no Supabase Auth (bloco B) pro
      domínio novo
- [ ] Atualizar `server_name` no bloco do Nginx
- [ ] Atualizar `CLAUDE.md` e `PLANO-DO-PROJETO.md` trocando as referências
      de `2-25-223-119.sslip.io` pelo domínio novo

## H. Desligar o Community Cloud (só depois de 3–7 dias com a VPS validada)

- [ ] <https://share.streamlit.io> → o app → Settings → **Pause** (rollback rápido) ou **Delete**
- [ ] Trocar links `leilaoce.streamlit.app` que existirem por aí

## I. Documentação final

- [x] `CLAUDE.md` — tirar o "em andamento" da linha Deploy (feito 2026-09-15)
- [x] `PLANO-DO-PROJETO.md` — seções 1/7/12/13 para **VPS Hostinger (`2-25-223-119.sslip.io`)** (feito 2026-09-15)
- [ ] (Opcional, futuro) Se o restart a cada commit do scraper (1×/dia) incomodar: o dashboard já lê `leiloes.json` via `st.cache_data(ttl=1800)`, então dá para trocar o `deploy.yml` por um cron simples de `git pull` sem restart nos commits só de dados — reservar o restart só para pushes que mudem código
