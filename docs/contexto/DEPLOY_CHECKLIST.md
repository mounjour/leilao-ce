# Checklist de deploy — Achadin Leilões

Passo a passo para fechar a migração do site para o **Render** e reativar o que
está pendente em volta (Evolution API, backup, IA).

Ordem de execução: os blocos **A → B** são o caminho crítico do site;
**C → F** podem ser feitos em paralelo; **G → H** são o fechamento.

Referências: [`SETUP_RENDER.md`](SETUP_RENDER.md), [`SETUP_BACKUP_DB.md`](SETUP_BACKUP_DB.md),
[`SETUP_GITHUB_ACTIONS.md`](SETUP_GITHUB_ACTIONS.md), [`render.yaml`](render.yaml).

---

## A. Render — subir o site

- [ ] Criar conta em <https://render.com> (entrar com o GitHub `mounjour`)
- [ ] Autorizar o repositório `mounjour/leilao-ce`
- [ ] Juntar os segredos que o Blueprint vai pedir:
  - [ ] `SUPABASE_URL` = `https://tybfusbovbihrkmcncux.supabase.co`
  - [ ] `SUPABASE_ANON_KEY` (chave `anon` / `public`, o `eyJ…`)
  - [ ] `STRIPE_SECRET_KEY` — **`sk_live_…`** se o site cobra de verdade (`sk_test_…` só para validar sem cobrar)
  - [ ] `STRIPE_PUBLISHABLE_KEY` — `pk_live_…` / `pk_test_…` (mesmo modo da secret)
  - [ ] `STRIPE_PRICE_ID` = `price_…` — **confirmar que é o preço certo** (e que bate com o rótulo `R$ 47` fixo no `render.yaml`)
- [ ] Render → **New +** → **Blueprint** → apontar para o repo. Ele lê o `render.yaml` e mostra **1 Web Service** (`leilao-ce`, plano **Starter**)
- [ ] Preencher as envs `sync: false`. As **3 `EVOLUTION_*` deixe em branco por enquanto** (bloco C)
- [ ] `APP_URL` = a URL **exata** que o Render mostra no topo (padrão `https://leilao-ce.onrender.com`; se o nome estiver tomado ele põe sufixo — copie o texto exato, **sem barra no final**)
- [ ] **Apply**. Esperar o deploy ficar **Live**
- [ ] Abrir `https://SEU-APP.onrender.com/_stcore/health` → tem que responder `ok`
- [ ] Se o app abrir mas travar em "Please wait…" / "Connection error": no `render.yaml`, acrescentar ao `startCommand` `--server.enableCORS false --server.enableXsrfProtection false` e dar push

## B. Apontar Supabase e Stripe para a URL do Render

- [ ] **Supabase** → projeto `tybfusbovbihrkmcncux` → **Authentication** → **URL Configuration**:
  - [ ] **Site URL:** `https://SEU-APP.onrender.com`
  - [ ] **Redirect URLs:** `https://SEU-APP.onrender.com`, `https://SEU-APP.onrender.com/**`, `https://leilaoce.streamlit.app` (manter ~1 semana), `http://localhost:8501`
- [ ] **Stripe** → Settings → Billing → Customer portal → se houver *default return link* no domínio antigo, atualizar (cosmético; o código já passa as URLs por sessão via `APP_URL`)
- [ ] **Webhook do Stripe:** nada a fazer — o endpoint é `*.supabase.co/functions/v1/stripe-webhook`, não depende da URL do site
- [ ] **Teste E2E** em `https://SEU-APP.onrender.com`:
  - [ ] Página de login/cadastro abre sem travar
  - [ ] Cadastro novo funciona (chega e-mail do Supabase com link do Render)
  - [ ] Login cai no dashboard
  - [ ] Sem assinatura → aparece o paywall
  - [ ] Botão de assinar abre o Stripe Checkout (cartão de teste se chave `test`; em `live`, cancelar antes de pagar)
  - [ ] Com assinatura ativa → dashboard completo, lotes carregando
  - [ ] Favoritar um lote salva e reflete no Supabase
  - [ ] Menu do usuário → portal de cobrança abre e volta pro Render

## C. Evolution API (WhatsApp) — opcional, mas hoje está desligado

O envio de WhatsApp (favoritar um lote → `favorites.py`; alertas de lance →
`alertas.py`; aviso de fonte zerada → `scraper_health.py`) **não funciona hoje** —
a instância da Evolution se perdeu e as credenciais não estão salvas em lugar
recuperável. O site sobe e opera sem isso.

- [ ] **Decidir:** reativar WhatsApp agora ou deixar para depois? (se depois, pule este bloco — nada quebra)
- [ ] Subir/recriar uma instância da **Evolution API** (self-host num VPS, ou provedor gerenciado)
- [ ] Parear o número do WhatsApp (QR code) e nomear a instância
- [ ] Anotar os 3 valores: `EVOLUTION_API_URL` (base, sem `/`), `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`
- [ ] Colocar os 3 em **Render** → serviço → **Environment** (é o que `favorites.py` usa quando alguém favorita)
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

## G. Desligar o Community Cloud (só depois de 3–7 dias com o Render validado)

- [ ] <https://share.streamlit.io> → o app → Settings → **Pause** (rollback rápido) ou **Delete**
- [ ] Trocar links `leilaoce.streamlit.app` que existirem por aí

## H. Documentação final

- [ ] `CLAUDE.md` — tirar o "em andamento" da linha Deploy quando o serviço estiver no ar e validado
- [ ] `PLANO-DO-PROJETO.md` — seções 1/7/13 para **Render (`leilao-ce.onrender.com`)**
- [ ] (Opcional, futuro) Se o redeploy a cada commit do scraper (2×/dia) incomodar: `autoDeploy: false` no `render.yaml` + Deploy Hook chamado no fim do `scraper.yml`, ou o dashboard passar a ler `leiloes.json` em runtime
