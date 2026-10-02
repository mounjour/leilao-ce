# Pendências consolidadas (2026-10-02)

Consolida o CLAUDE.md e [`PROXIMOS_PASSOS_2026-09-29.md`](PROXIMOS_PASSOS_2026-09-29.md)
numa lista só. Não foi feita auditoria do código.

## 1. Bloqueia cobrar de verdade

- [ ] **Chaves Stripe live.** O site na VPS roda com `sk_test_`/`pk_test_`. A conta Stripe está
      travada no 2FA por app autenticador, sem posse confirmada. Resolver isso antes da troca.
- [ ] **Páginas legais.** Termos de Uso, Política de Privacidade (LGPD: o site guarda telefone
      e nome) e política de cancelamento e reembolso.
- [ ] **Conferir a migração para `achadinleiloes.tech` fora do repo.** `APP_URL` no `.env` da
      VPS, Site URL/Redirect URLs no Supabase Auth e URL do webhook no Stripe. DNS e HTTPS já
      verificados. Ver seção G de [`setup/DEPLOY_CHECKLIST.md`](setup/DEPLOY_CHECKLIST.md).

## 2. Confiabilidade e operação

- [ ] **Restaurar um backup do Postgres** num projeto Supabase descartável. O `pg_dump` diário
      roda (5 runs verdes em 2026-09-29), mas nunca foi restaurado. Ver
      [`setup/SETUP_BACKUP_DB.md`](setup/SETUP_BACKUP_DB.md).
- [ ] **Monitoramento da VPS.** Alerta de uptime, snapshot da VPS, renovação do Certbot e
      rotação de logs. 1 vCPU/4 GB é ponto único de falha.
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
