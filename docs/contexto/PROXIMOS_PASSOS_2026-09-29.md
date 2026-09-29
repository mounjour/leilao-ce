# Próximos passos sugeridos (2026-09-29)

Levantamento feito a partir do CLAUDE.md e do histórico, sem auditar o código.
Nada abaixo está implementado. Ordenado por prioridade dentro de cada bloco.

Já registrados em outro lugar (não repetidos aqui):
- Trocar chaves Stripe de teste por live (bloqueio: 2FA da conta) — ver bullet "Deploy" do CLAUDE.md.
- Conferir `APP_URL`, Supabase Auth e webhook do Stripe no domínio novo — ver BACKLOG do CLAUDE.md e seção G de [`setup/DEPLOY_CHECKLIST.md`](setup/DEPLOY_CHECKLIST.md).

## 1. Bloqueador para cobrar

- [ ] **Páginas legais.** Termos de Uso, Política de Privacidade (LGPD: o site guarda
      telefone e nome) e política de cancelamento e reembolso. Nada disso consta no STATUS.

## 2. Confiabilidade e operação

- [ ] **Backup do Postgres.** Secret `SUPABASE_DB_URL` configurado (09/09) e `pg_dump` diário
      rodando com sucesso (conferido em 2026-09-29, 5 runs seguidos verdes). Falta só testar uma
      restauração num projeto Supabase descartável (ver
      [`setup/SETUP_BACKUP_DB.md`](setup/SETUP_BACKUP_DB.md)). Backup nunca restaurado não conta.
- [ ] **Monitoramento da VPS.** Alerta de uptime (UptimeRobot ou similar, grátis), backup/snapshot
      da própria VPS, vigilância da renovação do Certbot e rotação de logs. É 1 vCPU/4 GB, ponto único de falha.
- [ ] **Fontes pendentes (conferido nos runs do Actions de 26 a 29/09):** Grupo Lance OK (8 lotes CE,
      403 no acesso direto mas recupera). **MGL corrigido em 2026-09-29** (13 lotes CE via API HTTP do Zenrows,
      ver [`fontes/pausadas/MGL_SCRAPER_PENDENTE.md`](fontes/pausadas/MGL_SCRAPER_PENDENTE.md)); passou a ser vigiada pelo health check.
- [ ] **Desligar o Streamlit Community Cloud** (`leilaoce.streamlit.app`) depois de alguns dias
      de VPS estável em uso real.

## 3. Qualidade de produto

- [x] **Favoritos por uuid (feito 2026-09-29).** `favorites._normalizar_url` compara a URL inteira; como Pacto e
      Leilo mudaram de URL, favoritos antigos quebram em silêncio. Normalizar por uuid
      (dedup Pacto/Leilo já é por uuid). Correção pequena, impacto direto no usuário.
- [ ] **Análise de IA.** Sem crédito Anthropic, todos os lotes caem no fallback "Não informado".
      Recarregar o crédito e, depois, limitar custo por run (cache por lote, analisar só lotes
      novos ou alterados).
- [ ] **Dados no repositório (médio prazo, não urgente).** O bot commita `leiloes.json` 2x/dia e
      infla o histórico do git. Considerar gravar numa tabela do Supabase ou servir como
      artefato, deixando o git só para código.

## 4. Crescimento

- [ ] **Novas fontes:** Nasar Leilões (reaproveitar Zenrows do MGL) e depois Leilão Imóvel
      (ver [`INVESTIGACAO_NOVAS_FONTES_2026-09-14.md`](INVESTIGACAO_NOVAS_FONTES_2026-09-14.md)).
- [ ] **Funil e métricas.** Painel simples com dados do Supabase e do Stripe: cadastros,
      assinantes, onde desistem.
- [ ] **Landing page pública** com preview de alguns lotes antes do paywall, para converter melhor.

## Fora de escopo (decisão do dono, não sugerir)

- Relatórios e exportação
- Notificação de lote novo por filtro salvo
- Migração do WhatsApp para a Cloud API oficial da Meta (ressalva: o WhatsApp fora da API
  oficial tem risco de banimento do número; rever se virar canal pago do produto)
