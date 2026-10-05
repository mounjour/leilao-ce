# Cutover da landing (site estático em `/`, Streamlit em `/app/`)

Preparado em 2026-10-05, branch `feat/landing-estatica` (fases 1–3 do plano B). **Status: preparado, ainda
não executado na VPS.** Ao executar, atualizar este cabeçalho, o `CLAUDE.md` e o `SETUP_HOSTINGER_VPS.md`.

```
achadinleiloes.tech/        → site estático (site/), servido direto pelo Nginx de /var/www/achadin
achadinleiloes.tech/app/    → Streamlit (127.0.0.1:8501, server.baseUrlPath=app)
```

## O que o cutover muda na VPS

| Peça | Antes | Depois |
|---|---|---|
| Nginx (`/etc/nginx/sites-available/leilao-ce`) | `location /` → Streamlit | `deploy/nginx/leilao-ce.conf`: `/` estático, `/app/` → Streamlit, redirect de links antigos |
| systemd | Streamlit na raiz | drop-in `leilao-ce.service.d/baseurl.conf` (`STREAMLIT_SERVER_BASE_URL_PATH=app`) |
| `.env` | `APP_URL=https://achadinleiloes.tech` | `APP_URL=https://achadinleiloes.tech/app` |
| Site | — | `/var/www/achadin` (publicado de `site/` a cada deploy) |

Continuam iguais: código do app, Supabase, Stripe (as URLs de retorno saem de `APP_URL`), o webhook e o
login já aberto (o cookie de sessão é `path=/`, vale nos dois). Sessões do Streamlit abertas na hora do
restart caem e recarregam.

**Nomes de domínio (conferido na VPS em 2026-10-05):** o certificado `achadinleiloes.tech` cobre o domínio e o
`www`, mas não o `2-25-223-119.sslip.io` (que já não funcionava por HTTPS). O Nginx novo atende os dois nomes do
certificado: `www` redireciona (301) para o domínio principal e HTTP redireciona para HTTPS (antes,
`http://achadinleiloes.tech` dava 404). O `sslip.io` sai da configuração.

**Links antigos continuam funcionando:** pedidos em `/` com `?code=`, `?mode=`, `?payment=`, `?pagina=`
ou `?error=` recebem 302 para `/app/` com a mesma query. Cobre e-mails de confirmação/recuperação já
enviados, Checkouts do Stripe em andamento e links das páginas legais.

## 0. Antes (uma vez)

- [ ] Branch mergeada em `main` (depende de você aprovar o push/PR) e o workflow **Deploy do site** verde.
      É seguro mergear antes do cutover: o passo da landing no `deploy.yml` só age se `/var/www/achadin`
      existir, e o `uptime.yml` aceita o health nos dois caminhos.
- [ ] **Snapshot da VPS** no painel da Hostinger ([`OPERACAO_VPS.md`](OPERACAO_VPS.md) §2). O `.env` não está no git.
- [ ] **Supabase** → Authentication → URL Configuration → *Redirect URLs*: adicionar
      `https://achadinleiloes.tech/app` e `https://achadinleiloes.tech/app/**` (manter as atuais).
      **Não** trocar o *Site URL* ainda.
- [ ] Horário de pouco uso. A troca leva segundos, mas derruba sessões abertas.

## 1. Executar

O usuário `leilao` não tem senha de `sudo` (só NOPASSWD para o restart), então rode como **root**:

```bash
ssh root@2.25.223.119
cd /home/leilao/leilao-ce
runuser -u leilao -- git status --short   # limpo; (git como root dá "dubious ownership": use o runuser)
./deploy/cutover-landing.sh aplicar
```

O script: confere pré-requisitos (certificado, arquivos do Certbot, `.venv`, `rsync`…) e aborta **sem
alterar nada** se faltar algo → mostra o diff do Nginx e pede confirmação → faz backup em
`~leilao/backup-cutover/<data>` → publica o site → instala Nginx e drop-in → `nginx -t` → reload/restart →
verifica `/app/_stcore/health`, a landing em `/`, o redirect de legado, `/app/`, `robots.txt`, o redirect do `www`, HTTP→HTTPS e o
**WebSocket (101)** através do Nginx. **Qualquer falha dispara o rollback sozinho.**

## 2. Depois (manual)

- [ ] Supabase → *Site URL* → `https://achadinleiloes.tech/app`.
- [ ] `./deploy/cutover-landing.sh status` (tudo `ok`).
- [ ] `sudo certbot renew --dry-run` — confirma que a renovação do certificado segue funcionando com o Nginx novo.
- [ ] GitHub → Actions → **Monitor de uptime** → Run workflow (verde).
- [ ] Teste ponta a ponta (como em 2026-09-15), de preferência no celular:
  - [ ] `/` abre a landing; "Entrar" e "Começar agora" levam a `/app/`; "Voltar ao site" volta.
  - [ ] Cadastro com e-mail novo → e-mail de confirmação → o link cai em `/app/?mode=confirmed` com "E-mail confirmado".
  - [ ] Login → paywall (R$ 47 igual ao da landing) → Checkout em modo teste → volta em `/app/?payment=success` → acesso liberado.
  - [ ] Favoritar um lote; recarregar `/app/`; continua logado.
  - [ ] "Esqueci minha senha" → link → definir nova senha.
  - [ ] Rodapé da landing: Termos, Privacidade e Reembolso abrem em `/app/?pagina=…`.
  - [ ] Link antigo: abrir `https://achadinleiloes.tech/?pagina=termos` → cai em `/app/?pagina=termos`.
- [ ] Atualizar `CLAUDE.md` (deploy: landing + `/app`), `SETUP_HOSTINGER_VPS.md` (§4 drop-in, §5 Nginx, §7 `APP_URL`/Supabase)
      e o status deste arquivo.

## 3. Rollback

```bash
cd /home/leilao/leilao-ce
./deploy/cutover-landing.sh rollback     # restaura Nginx, remove o drop-in, volta o APP_URL, reinicia
```

Depois, no Supabase, voltar o *Site URL* se já tiver sido trocado. Se o próprio script falhar:

```bash
cp ~leilao/backup-cutover/<data>/leilao-ce.nginx /etc/nginx/sites-available/leilao-ce
rm /etc/systemd/system/leilao-ce.service.d/baseurl.conf && systemctl daemon-reload
cp ~leilao/backup-cutover/<data>/.env /home/leilao/leilao-ce/.env
nginx -t && systemctl reload nginx && systemctl restart leilao-ce
```

Último recurso: `leilaoce.streamlit.app` segue no ar (basta o Redirect URL antigo no Supabase).

## 4. Depois do cutover: mexer no Nginx

Edite `deploy/nginx/leilao-ce.conf` no repo e aplique na VPS:

```bash
sudo install -m 644 deploy/nginx/leilao-ce.conf /etc/nginx/sites-available/leilao-ce
sudo nginx -t && sudo systemctl reload nginx
```

## Limites conhecidos

- O Nginx novo não foi testado num Nginx real antes da VPS (sem Docker/Nginx na máquina de desenvolvimento).
  O script foi exercitado com binários simulados (sucesso, falha de verificação, falha de `nginx -t`, pré-requisito ausente),
  e a rede de segurança é o `nginx -t` + verificações + rollback automático.
- O favicon e o título dentro de `/app/` continuam sendo os do Streamlit (o título é reescrito pelo `sub_filter`).
- A landing carrega a fonte Inter do Google Fonts, como o app já fazia.
- Sem analytics (decisão de 2026-10-05): nenhuma mudança na página de Privacidade.
