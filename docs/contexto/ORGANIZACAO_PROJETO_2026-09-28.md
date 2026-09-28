# Análise de organização do projeto (2026-09-28)

Levantamento do diretório inteiro do `leilao-ce` pedido pelo dono, com uma
proposta de arrumação. **Nada foi movido ainda** — este documento só registra
o diagnóstico e o plano, para aprovação antes de qualquer mudança (conforme
convenção do CLAUDE.md).

## O que já está bem decidido (não mexer)

`docs/agents/domain.md` já declara a estrutura do repo como "single-context":
`CONTEXT.md` + `docs/adr/` na raiz, com os módulos Python soltos na raiz
(`dashboard.py`, `scraper.py`, ...). Ou seja, **não é bug** os `.py` estarem
todos na raiz — é uma decisão de arquitetura já tomada. Este documento não
propõe criar `src/`, mover `scraper.py`/`dashboard.py`/`auth.py` etc., nem
contrariar essa convenção.

## Estado atual (visão geral)

```
leilao-ce/
├── CLAUDE.md                    461 linhas — contexto do projeto p/ IA
├── .env, .gitignore, requirements*.txt
├── alertas.py, auth.py, dashboard.py, favorites.py, scraper.py,
│   scraper_health.py, whatsapp_log.py     — módulos da aplicação
├── teste_alerta.py              script manual (dispara WhatsApp real)
├── conftest.py                  stub de libs p/ pytest
├── leiloes.json                 1.1M  — dados raspados, versionado de propósito
├── analises_ia_cache.json       148K  — cache de análise de IA
├── historico_tokens_ia.jsonl    20K   — log de consumo de tokens de IA
├── scraper_health.json          8K    — placar de saúde por fonte
├── docs/
│   ├── agents/                  3 arquivos (issue-tracker, triage-labels, domain)
│   └── contexto/                20 arquivos .md, todos soltos na mesma pasta
├── supabase/                    migrations, functions, config
├── tests/                       3 arquivos de teste + fixtures
└── .github/workflows/           5 workflows (deploy, scraper, tests, backup, teste_alerta)
```

Linhas por módulo (pra dar noção de tamanho, não é problema a resolver aqui):
`scraper.py` 3545, `dashboard.py` 1711, `auth.py` 1016, `scraper_health.py`
266, `favorites.py` 177, `alertas.py` 195, `whatsapp_log.py` 60,
`teste_alerta.py` 83, `conftest.py` 31.

## Onde está a desorganização de verdade

### 1. `docs/contexto/` é uma gaveta única com 20 arquivos de naturezas diferentes

Hoje tudo — guia de setup de infra, decisão de descartar um leiloeiro,
correção de bug de scraper, investigação de novas fontes, plano geral do
projeto — fica solto no mesmo diretório, ordenado só por nome. Dá pra
separar em 4 grupos que já existem implicitamente pelo conteúdo:

- **Setup/infra** (guias operacionais duradouros, não mudam por evento):
  `SETUP_HOSTINGER_VPS.md`, `SETUP_GITHUB_ACTIONS.md`, `SETUP_BACKUP_DB.md`,
  `SETUP_EVOLUTION.md`, `DEPLOY_CHECKLIST.md`
- **Fontes adicionadas** (uma fonte de leilão nova, documentação de origem):
  `FRANCISCO_FREITAS_ADICIONADO.md`, `GRUPO_LANCE_ADICIONADO.md`,
  `MARIA_FIXER_ADICIONADO.md`, `PEREIRA_LEILOES_ADICIONADO.md`,
  `RECEITA_SLE_ADICIONADO.md`, `SPY_LEILOES_ADICIONADO.md`
- **Fontes pausadas/descartadas** (decisão de não usar ou pausar por ora):
  `CELSO_CUNHA_DORMENTE.md`, `MGL_SCRAPER_PENDENTE.md`,
  `SODRE_SANTORO_DESCARTADO.md`
- **Incidentes/regressões de fonte** (site mudou, bug, reescrita):
  `LEILO_REDESIGN_2026-09.md`, `LEILO_REESCRITO_2026-09.md`,
  `PACTO_REGRESSAO_2026-09.md`, `DEDUP_ENTRE_FONTES.md`
- **Investigação/planejamento** (não é sobre 1 fonte específica):
  `INVESTIGACAO_NOVAS_FONTES_2026-09-14.md`, `PLANO-DO-PROJETO.md`

**Proposta:** criar subpastas dentro de `docs/contexto/`:

```
docs/contexto/
├── setup/           SETUP_*.md, DEPLOY_CHECKLIST.md
├── fontes/
│   ├── ativas/      *_ADICIONADO.md
│   ├── pausadas/    *_DORMENTE.md, *_PENDENTE.md, *_DESCARTADO.md
│   └── incidentes/  *REGRESSAO*, *REDESIGN*, *REESCRITO*, DEDUP_ENTRE_FONTES.md
└── PLANO-DO-PROJETO.md, INVESTIGACAO_NOVAS_FONTES_2026-09-14.md   (ficam na raiz de contexto/)
```

É um `git mv` puro (sem reescrever conteúdo) — baixo risco, mas exige
atualizar os links que o `CLAUDE.md` faz pra esses arquivos (~15 menções
`docs/contexto/NOME.md`).

### 2. `CLAUDE.md` cresceu para um log histórico de 461 linhas

O bloco `STATUS` hoje é essencialmente um changelog cronológico desde
2026-09-02 — cada correção de scraper vira um parágrafo novo, e o arquivo só
cresce (é recarregado por inteiro em toda sessão). Boa parte do detalhe já
está duplicado nos docs de `docs/contexto/` (ex.: o parágrafo do MJ Leilões
podia ser 2 linhas + link para um `MJ_LEILOES_CORRIGIDO_2026-09.md`, que hoje
nem existe — o detalhe só está no CLAUDE.md).

**Proposta:** tratar `STATUS` como "o que está valendo agora", não como
histórico. Quando uma correção some do topo (vira passado), resumir para
1-3 linhas com link pro doc de contexto correspondente (criando o doc se
ainda não existir, como no caso do MJ Leilões). Isso já é o padrão que
funciona bem pros itens que têm "Ver docs/contexto/X.md" — só falta aplicar
de forma consistente e podar o que já virou história.

### 3. Arquivos de dados/cache soltos na raiz, junto com código-fonte

`leiloes.json`, `analises_ia_cache.json`, `historico_tokens_ia.jsonl` e
`scraper_health.json` são todos dados gerados (não código), todos
versionados no git, mas ficam misturados com `scraper.py`/`dashboard.py`/etc.
na raiz. `leiloes.json` já é versionado por decisão explícita (ver STATUS);
os outros 3 parecem ser consequência de terem sido criados no mesmo lugar,
sem decisão deliberada.

**Proposta (opcional, mexe em paths no código):** uma pasta `data/` só para
esses 4 arquivos gerados, com os módulos apontando pro novo caminho. Como
isso toca `scraper.py`, `dashboard.py`, `scraper_health.py` e os workflows do
GitHub Actions que fazem commit desses arquivos, é a mudança de **maior
risco** desta lista — só vale a pena se o dono achar que a raiz está
poluída; do contrário, deixar como está é uma escolha razoável.

### 4. `teste_alerta.py` é script manual, mas mora junto dos módulos da aplicação

Já documentado no CLAUDE.md como "script manual separado (dispara WhatsApp
real, não é parte da suite)", mas fisicamente indistinguível de
`alertas.py`/`favorites.py` na raiz. Como a convenção do projeto (via
`domain.md`) é manter os módulos soltos na raiz, criar uma pasta `scripts/`
só pra esse um arquivo é opcional — mencionado aqui só para registrar a
opção, não como recomendação forte.

### 5. Ausência de `README.md` na raiz

Não há nenhum `README.md` — quem abre o repo pela primeira vez (ou um agente
novo) cai direto no `CLAUDE.md`, que é contexto operacional para IA, não uma
porta de entrada humana. Um `README.md` curto (o que é o projeto, como rodar
localmente, onde fica o quê) ajudaria, mas não é bloqueante.

## Prioridade sugerida

1. **Reorganizar `docs/contexto/` em subpastas** — baixo risco, alto ganho de
   navegabilidade, só exige atualizar links no CLAUDE.md.
2. **Podar o `STATUS` do CLAUDE.md** conforme itens viram passado, movendo
   detalhe pra `docs/contexto/` — processo contínuo, não uma tarefa única.
3. **README.md mínimo** — opcional, rápido de fazer.
4. **`data/` para os JSON/JSONL gerados** — opcional, maior risco (toca
   paths em código e workflows), só fazer se incomodar de verdade.
5. **`scripts/` para `teste_alerta.py`** — opcional, cosmético.

Itens 1–3 dá pra fazer numa sessão só, sem risco de quebrar produção. Itens
4–5 ficam de escolha do dono.
