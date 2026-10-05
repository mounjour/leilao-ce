# Operação da VPS (monitoramento, snapshot, logs, certificado)

Complementa [`SETUP_HOSTINGER_VPS.md`](SETUP_HOSTINGER_VPS.md). A VPS é 1 vCPU/4 GB: ponto
único de falha, então o que importa é **saber rápido que caiu** e **ter como voltar**.

## 1. Alerta de uptime (automatizado)

`.github/workflows/uptime.yml` roda a cada 15 min: confere o health do Streamlit (`/app/_stcore/health`; aceita também o caminho antigo
`/_stcore/health` até o [cutover da landing](CUTOVER_LANDING.md), 3 tentativas), se `GET /` responde 200 e a
validade do certificado (alerta com menos de 14 dias). Se falhar, o GitHub
manda e-mail de "workflow failed" ao dono do repo.

**Checar uma vez:** GitHub > Settings (conta) > Notifications > Actions — deixar ligado
"Send notifications for failed workflows only". Teste: Actions > Monitor de uptime > Run workflow.

Limite: o cron do Actions pode atrasar; detecta queda de minutos, não de segundos. Se quiser
alerta mais rápido ou por WhatsApp/SMS, o complemento é um serviço externo grátis
(UptimeRobot/Better Stack, checagem a cada 5 min) apontando para a mesma URL.

## 2. Snapshot / backup da VPS (manual, no painel)

Hostinger > VPS > Backups & Monitoring. Conferir se o plano inclui backup semanal automático;
se não, tirar **um snapshot manual** depois de qualquer mudança grande de configuração
(Nginx, systemd, `.env`). O `.env` da VPS **não está no git** — o snapshot é a única cópia
dele; guarde também uma cópia off-site (gerenciador de senhas).

## 3. Renovação do Certbot (rodar uma vez na VPS)

```bash
systemctl list-timers | grep certbot
sudo certbot renew --dry-run
```

Esperado: timer ativo e `Congratulations, all simulated renewals succeeded`. O alerta de
certificado do item 1 cobre o caso de a renovação falhar em silêncio.

## 4. Logs e disco (rodar uma vez na VPS)

```bash
journalctl --disk-usage          # journald do app
df -h /                          # disco
ls /etc/logrotate.d/nginx        # nginx ja vem com rotacao no Ubuntu
```

Limitar o journal para não crescer sem fim:

```bash
sudo sed -i 's/^#\?SystemMaxUse=.*/SystemMaxUse=500M/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

## Rollback para o Streamlit Community Cloud

Enquanto `leilaoce.streamlit.app` existir (pausado ou não), ele é o plano B: basta apontar o
`APP_URL`/Redirect URLs do Supabase de volta. Ao deletar o app, esse plano B some — por isso
o desligamento só acontece depois de alguns dias de VPS estável (ver
[`PENDENCIAS_2026-10-02.md`](../PENDENCIAS_2026-10-02.md)).
