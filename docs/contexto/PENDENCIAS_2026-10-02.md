# Pendências consolidadas (2026-10-02)

Consolida o CLAUDE.md e [`PROXIMOS_PASSOS_2026-09-29.md`](PROXIMOS_PASSOS_2026-09-29.md)
numa lista só. Não foi feita auditoria do código.

## 1. Bloqueia cobrar de verdade

- [ ] **Chaves Stripe live.** O site na VPS roda com `sk_test_`/`pk_test_`. A conta Stripe está
      travada no 2FA por app autenticador, sem posse confirmada. Resolver isso antes da troca.
- [~] **Páginas legais.** Implementadas em `legal.py` (2026-10-02): `?pagina=termos|privacidade|reembolso`,
      públicas, com links no login/cadastro/paywall e checkbox de aceite no cadastro. Política: 7 dias de
      reembolso integral (CDC art. 49), depois sem proporcional. `_CONTROLADOR` preenchido em 2026-10-05
      (nome + CNPJ). **Falta:** revisar o texto (idealmente com advogado).
- [x] **Migração para `achadinleiloes.tech` fora do repo** (feito 2026-10-02): `APP_URL` corrigido
      na VPS (estava no `sslip.io`), Supabase Auth ajustado pelo dono; webhook do Stripe não
      depende do domínio. Ver seção G de [`setup/DEPLOY_CHECKLIST.md`](setup/DEPLOY_CHECKLIST.md).

## 2. Confiabilidade e operação

- [x] **Restaurar um backup do Postgres** (feito 2026-10-02): artifact do run de 02/10 restaurado
      num Postgres 17 descartável (Docker local), 0 erros; 13 `auth.users`, 12 `profiles`,
      3 `favorites`, 6 `whatsapp_send_log`, triggers recriados. Ver
      [`setup/SETUP_BACKUP_DB.md`](setup/SETUP_BACKUP_DB.md). Falta só o hábito de baixar 1 artifact/mês.
- [x] **Monitoramento da VPS** (feito 2026-10-02): alerta de uptime + validade do certificado
      (`.github/workflows/uptime.yml`, a cada 15 min, run de teste verde); backups semanais da
      Hostinger ativos (22/09 e 29/09); `certbot renew --dry-run` ok e timer ativo; disco 5%,
      journal 22 MB; certificado antigo do `sslip.io` removido. Passo a passo em
      [`setup/OPERACAO_VPS.md`](setup/OPERACAO_VPS.md). O VPS ainda e ponto unico de falha (1 vCPU).
- [ ] **Desligar o Streamlit Community Cloud** (`leilaoce.streamlit.app`) após alguns dias de
      VPS estável em uso real.

## 3. Qualidade de produto

- [ ] **Crédito da IA (Anthropic).** Sem crédito, todos os lotes caem no fallback "Não
      informado". Depois, limitar custo por run (cache por lote, só lotes novos ou alterados).
- [ ] **`leiloes.json` no git (médio prazo).** O bot commita 2x/dia e infla o histórico.
      Considerar tabela do Supabase ou artefato.
- [ ] Favoritos Pacto no formato antigo (`ano.NNNN`) continuam sem casar.

## 4. Crescimento

- [ ] Novas fontes: Nasar Leilões (reaproveitar Zenrows do MGL), depois Leilão Imóvel. Ver
      [`INVESTIGACAO_NOVAS_FONTES_2026-09-14.md`](INVESTIGACAO_NOVAS_FONTES_2026-09-14.md).
- [ ] Funil e métricas (Supabase + Stripe).
- [ ] Landing page pública com preview de lotes antes do paywall.

## Resolvido (não é mais pendência)

- MGL: 13 lotes CE via API HTTP do Zenrows (2026-09-29).
- Grupo Lance: 8 lotes CE confirmados nos runs de 26 a 29/09.
- Favoritos por uuid Pacto/Leilo (2026-09-29).

## Fora de escopo (decisão do dono)

- Relatórios e exportação.
- Notificação de lote novo por filtro salvo.
- Migração do WhatsApp para a Cloud API oficial da Meta.
