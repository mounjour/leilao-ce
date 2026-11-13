CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: Achadin Leiloes em producao numa VPS Hostinger (plano KVM 1, 1 vCPU/4GB RAM, ~R$ 28/mes), endereco `achadinleiloes.tech` (IP `2.25.223.119`, dominio proprio; DNS e HTTPS verificados em 2026-09-29, TLS via Let's Encrypt/Certbot; antes usava `2-25-223-119.sslip.io`), autodeploy via GitHub Actions SSH no push do main (`.github/workflows/deploy.yml`). Migracao concluida em 2026-09-15 (testada ponta a ponta: cadastro, login, paywall, Stripe Checkout, favoritar). Migracao do Render abandonada antes de ir ao ar (nunca chegou a subir o servico) — trocado pela VPS por decisao do dono em 2026-09-14. Streamlit Community Cloud (leilaoce.streamlit.app) ainda no ar como rollback rapido — desligar so apos alguns dias validando a VPS em uso real. Site na VPS roda com chaves Stripe de TESTE (sk_test_/pk_test_) — trocar para live antes de cobrar de verdade (acesso a conta Stripe travado em 2FA por app autenticador sem posse confirmada; resolver isso antes da troca). Desde 2026-10-05 a raiz do dominio e uma landing estatica (`site/`, servida pelo Nginx de `/var/www/achadin`) e o Streamlit mora em `/app/` (`APP_URL=https://achadinleiloes.tech/app`, drop-in `STREAMLIT_SERVER_BASE_URL_PATH=app`; `www` e HTTP redirecionam para o dominio principal) — ver docs/contexto/setup/CUTOVER_LANDING.md. Ver docs/contexto/setup/SETUP_HOSTINGER_VPS.md e o bullet "Migracao de deploy para a VPS Hostinger" no STATUS.
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em docs/contexto/setup/SETUP_GITHUB_ACTIONS.md.

STATUS (atualizado 2026-09-25; podado em 2026-09-28 — detalhe completo de
cada item foi movido pros docs de contexto linkados, ver
[ORGANIZACAO_PROJETO_2026-09-28.md](docs/contexto/ORGANIZACAO_PROJETO_2026-09-28.md)):
- MJ Leiloes corrigido (2026-09-25): lote saia 2x (URL com/sem `#lances`) e
  titulo/categoria quebravam pra veiculos pesados. 16 lotes unicos, 0 sem
  marca/modelo. Testes: 189/189. Ver
  docs/contexto/fontes/incidentes/MJ_LEILOES_DUPLICADO_2026-09.md.
- Leilo corrigido + dedup com o Pacto (2026-09-25): site refeito (mesmo
  redesign do Pacto); parser reescrito pra ler o JSON embutido da pagina.
  Pacto e Leilo sao a MESMA plataforma — dedup por uuid entre os dois, Pacto
  como canonico. Testes: 169/169. Favoritos por uuid
  resolvido em 2026-09-29 (`favorites._normalizar_url`). Ver
  docs/contexto/fontes/incidentes/LEILO_REDESIGN_2026-09.md.
- Receita SLE corrigida (2026-09-24): 0 lotes desde 21/09 era o filtro de
  situacao do edital desatualizado (so aceitava `situacao 2`, precisava
  tambem `3`). 287 lotes CE restaurados. Testes: 136/136. Ver
  docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md.
- Grupo Lance corrigido (2026-09-24): site reestruturou URLs de
  listagem/lote e o filtro de categoria descartava tudo em silencio;
  corrigido + observabilidade nova (200 sem cards vira falha logada). 9
  lotes CE, 127/127 testes. Pendente: confirmar no proximo run do Actions.
  Ver docs/contexto/fontes/ativas/GRUPO_LANCE_ADICIONADO.md.
- Pacto migrado para requests (2026-09-25): `_raspar_pacto` reescrita sem
  Playwright, reaproveitando o parser da plataforma Leilo (JSON
  `elastic.lotes`). 176/176 testes; validado 69 lotes ao vivo. Favoritos
  por uuid resolvido em 2026-09-29. Ver
  docs/contexto/fontes/incidentes/PACTO_REGRESSAO_2026-09.md.
- Regressao do Pacto corrigida (2026-09-24): site refeito quebrou lance,
  foto, marca e FIPE desde 21/09; `_raspar_pacto` reescrita com funcoes
  puras, 120/120 testes. Atencao: URL do lote mudou pra `/lote/<uuid>/`
  (favoritos antigos de lote Pacto nao casam mais). Ver
  docs/contexto/fontes/incidentes/PACTO_REGRESSAO_2026-09.md.
- Health check de campos zerados em massa (2026-09-24): `scraper_health.py`
  passou a vigiar tambem `lance_atual>0` e `foto` por fonte, nao so a
  contagem de lotes — a regressao do Pacto acima passou batida por dias
  porque so a contagem era checada. Ver docs/contexto/SCRAPER_HEALTH.md.
- Bug de foto faltando no Pacto corrigido (2026-09-18): investigacao
  confirmou que so o Pacto tinha bug real (foto carregada de forma
  assincrona no site, lida cedo demais pelo scraper); corrigido com
  wait_for_load_state + retry. Demais fontes sem foto batiam com ausencia
  real no site original. Ver
  docs/contexto/fontes/incidentes/PACTO_FOTO_ASSINCRONA_2026-09-18.md.
- Pereira Leiloes adicionada como fonte (2026-09-18): reaproveita
  `_raspar_soleon` (mesmo backend do Construbem/Daniel Garcia), sem bloqueio
  de Cloudflare no IP do Actions. Leiloeiro cearense de bens publicos,
  leiloes esporadicos (`FONTES_ESPERADAS_ZERO`). Ver
  docs/contexto/fontes/ativas/PEREIRA_LEILOES_ADICIONADO.md.
- Dedup entre fontes implementado (2026-09-16):
  `_remover_duplicatas_entre_fontes` remove lote repetido entre agregador e
  leiloeiro direto quando ha identificador de alta confianca (CNJ/matricula)
  no texto — sem heuristica de titulo/endereco. 99/99 testes. Ver
  docs/contexto/fontes/incidentes/DEDUP_ENTRE_FONTES.md.
- Spy Leiloes adicionada como fonte (2026-09-16): agregador nacional de
  imoveis, 604 imoveis CE confirmados. Ver
  docs/contexto/fontes/ativas/SPY_LEILOES_ADICIONADO.md.
- Maria Fixer Leiloes adicionada como fonte (2026-09-16): mesma plataforma
  "vlance" do Francisco Freitas, 77 lotes CE. Ver
  docs/contexto/fontes/ativas/MARIA_FIXER_ADICIONADO.md.
- Bug critico no Leilo corrigido (2026-09-16): categoria errada e vazamento
  de lotes de OUTROS ESTADOS rotulados como CE; parser reescrito com
  validacao de UF por lote. Ver
  docs/contexto/fontes/incidentes/LEILO_REESCRITO_2026-09.md.
- Grupo Lance adicionada como fonte (2026-09-15): 9 lotes de imovel
  confirmados no CE, requests direto (sem Cloudflare). Ver
  docs/contexto/fontes/ativas/GRUPO_LANCE_ADICIONADO.md.
- Testes: tests/test_scraper.py cobre as funcoes puras de scraper.py
  (pytest, ~0,4s). conftest.py stuba Playwright/anthropic/dotenv pra import
  nao exigir browser nem ANTHROPIC_API_KEY. CI (.github/workflows/tests.yml)
  roda em push/PR; scraper.yml roda pytest como gate antes de raspar. Rodar
  local: `python -m pytest -q`. teste_alerta.py e script manual separado
  (dispara WhatsApp real, nao e parte da suite).
- Scraping: Leilo, Mega, Pacto, MGL, Montenegro, Construbem, Daniel Garcia,
  MJ Leiloes, Receita Federal (SLE) e Francisco Freitas Leiloes
  implementados. Celso Cunha DORMENTE (ver abaixo). HastaPublica removida
  (2026-09-11, decisao do dono).
- Celso Cunha DORMENTE (2026-09-08): site reconstruido, sem leilao ativo
  desde 28/08. Ver docs/contexto/fontes/pausadas/CELSO_CUNHA_DORMENTE.md.
- Health check do scraper (2026-09-08): scraper_health.py mantem placar por
  fonte; 3 runs seguidos com 0 lote numa fonte de FONTES_ATIVAS aciona
  WhatsApp pro dono. Ver docs/contexto/SCRAPER_HEALTH.md.
- Higiene (2026-09-08): debug.py removido; PLANO-DO-PROJETO.md atualizado.
  Decisoes FORA DE ESCOPO: relatorios/exportacao, notificacao de lote novo
  por filtro salvo, migrar WhatsApp p/ Cloud API oficial da Meta.
- Migracao de deploy para a VPS Hostinger CONCLUIDA (2026-09-15): detalhe e
  pendencias atuais no bullet "Deploy" da secao CONTEXTO DO PROJETO acima.
  Checklist completo em docs/contexto/setup/DEPLOY_CHECKLIST.md e guia em
  docs/contexto/setup/SETUP_HOSTINGER_VPS.md.
- Eletronicos (2026-09-08): Receita SLE tambem traz eletronicos (categoria
  `eletronicos`, icone 📱) — decisao do dono de trazer tudo, sem piso de
  valor. Ver docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md, secao
  "Eletronicos".
- Francisco Freitas adicionada (2026-09-04): maior fonte ja integrada (77
  lotes CE mantidos apos filtro), API JSON com dado estruturado. Receita
  Federal adicionada (2026-09-03): leilao de mercadoria apreendida, filtro
  CE por lote. MGL reescrito (2026-09-02, API JSON) mas bloqueado por
  Cloudflare no IP do Actions ate ser destravado via Zenrows Scraping
  Browser em 2026-09-04 — ainda nao validado em run real do Actions. Sodre
  Santoro descartado (2026-08-31, sem estoque no CE). Ver
  docs/contexto/fontes/ativas/FRANCISCO_FREITAS_ADICIONADO.md,
  docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md,
  docs/contexto/fontes/pausadas/MGL_SCRAPER_PENDENTE.md e
  docs/contexto/fontes/pausadas/SODRE_SANTORO_DESCARTADO.md.
- IA (Anthropic): creditos esgotados nos runs de 2026-09-02 — circuit
  breaker desliga a analise e usa fallback "Nao informado" em todos os
  lotes.
- Favoritos: pronto, sincronizando com Supabase (upsert por
  user_id,lote_url).
- Log de falha de WhatsApp (2026-09-08): falha de envio agora e gravada na
  tabela `whatsapp_send_log` (antes era engolida silenciosamente). Ver
  docs/contexto/WHATSAPP_SEND_LOG.md.
- Backup do Postgres (2026-09-09): pg_dump diario via GitHub Actions
  (Supabase Free nao tem backup nativo). Pendente: configurar secret
  `SUPABASE_DB_URL`, testar 1 restauracao. Ver
  docs/contexto/setup/SETUP_BACKUP_DB.md.
- Cadastro/login: pronto, Supabase Auth (fluxo PKCE) + trigger
  handle_new_user.
- Planos pagos (Stripe): enforcement ligado — dashboard.py bloqueia quem
  nao tem assinatura ativa. Portal de cobranca e webhook funcionando.
- stripe-webhook + migration de colunas de cobranca (2026-09-03): fallback
  de emergencia do updateProfile (puxa phone/name de auth.users) e colunas
  de cobranca (subscription_status etc.) deployados e aplicados. Ver
  docs/contexto/STRIPE_WEBHOOK_FALLBACK.md.
- Favoritos por uuid (2026-09-29): `favorites._normalizar_url` mapeia URLs
  `/lote/<uuid>/` do Pacto/Leilo para a forma canonica do Pacto; remocao apaga
  todas as formas antigas. Favoritos Pacto no formato antigo (`ano.NNNN`)
  continuam sem casar. Testes: tests/test_favorites.py.

BACKLOG:
- FEITO (2026-10-05): landing estatica em `/` + Streamlit em `/app/` (plano B do redesenho do front, PRs #20 e
  #21): `site/` (landing), `design_tokens.py` + `site/css/tokens.css` (tokens `--lce-*` compartilhados entre
  landing e app), `deploy/` (Nginx, drop-in do systemd, `cutover-landing.sh` com rollback), `.streamlit/config.toml`
  (primaryColor azul). Estilo do app mantido (mockup de 10/09 descartado), sem analytics. Executado e validado
  ponta a ponta; detalhes e rollback em docs/contexto/setup/CUTOVER_LANDING.md.
- PENDENTE (registrado 2026-10-05): CI `pytest` vermelho desde 02/10 (`tests/test_favorites.py` importa
  `streamlit`, ausente de `requirements-dev.txt`); VPS com reinicio pendente por atualizacao de kernel (fazer em
  janela tranquila); opcionais da landing: imagem OG para compartilhamento e fonte Inter hospedada localmente.
- FEITO (2026-10-05): `_CONTROLADOR` em `legal.py` preenchido com nome e CNPJ do dono
  (57.445.137/0001-77). Resta revisar o texto das paginas legais (idealmente com
  advogado) antes de cobrar de verdade. Ver docs/contexto/PENDENCIAS_2026-10-02.md.
- Lista consolidada de pendencias (2026-10-02): docs/contexto/PENDENCIAS_2026-10-02.md.
- Proximos passos sugeridos (2026-09-29): paginas legais, backup do Postgres,
  monitoramento da VPS, credito da IA, novas fontes, funil.
  Lista completa e priorizada em
  docs/contexto/PROXIMOS_PASSOS_2026-09-29.md.
- FEITO (2026-10-02): migracao para `achadinleiloes.tech` conferida fora do repo
  — `APP_URL` na VPS corrigido (estava no sslip.io), Supabase Auth ajustado,
  webhook do Stripe independe do dominio. Checklist na secao G de
  docs/contexto/setup/DEPLOY_CHECKLIST.md.
- Nova rodada de investigação de fontes (2026-09-14): Grupo Lance FEITO
  (2026-09-15, ver STATUS e docs/contexto/fontes/ativas/GRUPO_LANCE_ADICIONADO.md).
  Restam para implementar, por prioridade: Spy Leilões (agregador, 195
  lotes em Fortaleza, exige dedup entre fontes), Nasar Leilões (leiloeiro
  próprio de Fortaleza, reaproveitar Zenrows do MGL para driblar
  Cloudflare). Leilão Imóvel (agregador) fica de reserva, menor prioridade.
  Descartados: cearaleiloes.com.br (= Francisco Freitas), Silvio Cesar
  Maraschi (= HastaPública, já removida), Alfa/Italo/Átrio Leilões (sem
  volume CE confirmado ou risco reputacional). Ver
  docs/contexto/INVESTIGACAO_NOVAS_FONTES_2026-09-14.md.
- Achar outro leiloeiro/fonte que de fato opere no CE: FEITO — Receita
  Federal (SLE, edital Fortaleza) e Francisco Freitas
  Leilões (91 lotes CE, maior fonte) implementadas. Ver STATUS,
  docs/contexto/fontes/ativas/RECEITA_SLE_ADICIONADO.md e
  docs/contexto/fontes/ativas/FRANCISCO_FREITAS_ADICIONADO.md. Candidatos avaliados e descartados por
  ora: Nasar Leilões (Fortaleza, muito imóvel no CE, mas precisa de proxy —
  Cloudflare), Lopes Leilões (site sem Cloudflare mas dormente, zero lotes),
  Copart (login obrigatório + anti-bot agressivo), VIP Leilões (venda
  direta, não leilão), freitasleiloeiro.com.br de Santo André/SP (não
  confundir com o Francisco Freitas — quase zero CE).
- MGL: FEITO (2026-09-04) — `_raspar_mgl` roteado pela Zenrows Scraping
  Browser (`connect_over_cdp`), não pelo padrão de proxy de URL do
  _raspar_soleon (esse não bastava pro MGL, que precisa da navegação
  inteira passando pelo proxy, não só o fetch). Falta validar num run real
  do GitHub Actions. Ver STATUS e docs/contexto/fontes/pausadas/MGL_SCRAPER_PENDENTE.md.
- Recarregar crédito Anthropic (destrava a análise de IA). Zenrows/ScraperAPI
  já em uso nos planos de entrada (dono do projeto confirmou em 2026-09-04
  que preço não é uma preocupação aqui).
- stripe-webhook: endurecimento do fallback (phone/name), migration das
  colunas de cobrança, deploy da Edge Function e aplicação da migration
  CONCLUÍDOS em 2026-09-03 (ver STATUS). Nada pendente aqui.
- dashboard.py: CSS de sidebar consolidado (painel em "SIDEBAR (bloco
  unico)"; moldura header/toolbar/colapso em "HEADER/TOOLBAR E BOTÃO DE
  COLAPSO DA SIDEBAR (bloco unico)"). Sem duplicatas pendentes.

CONVENÇÕES:
- Mensagens em português, código em inglês (variáveis, funções)
- Sem emojis dentro de código Python, apenas no UI do Streamlit
- Antes de mudanças grandes, sempre apresente um plano para eu aprovar
- Nunca dar `git push` direto na `main` nem `git push --force` em branch
  compartilhada. Push de branch de trabalho (para abrir/atualizar PR) faz
  parte do fluxo abaixo e está autorizado.

## Fluxo de trabalho: branches, commits, PRs e merge

Toda mudança no repo (código, config, workflow, docs) segue este fluxo. A
única exceção é o commit automático do scraper (`chore: atualiza leiloes.json
[auto ...]`), que o GitHub Actions faz direto na `main`.

### 1. Branch

- Sempre partir da `main` atualizada: `git switch main && git pull --ff-only`
  (o bot do scraper commita na `main` 2x/dia, então ela anda sozinha).
- Nome: `<tipo>/<descricao-curta-em-kebab-case>`, com o mesmo `<tipo>` dos
  commits. Ex.: `feat/fonte-nasar`, `fix/pacto-foto-vazia`,
  `docs/padrao-markdown`, `ci/cache-pip`.
- Uma branch = um assunto = um PR. Não misturar correção de fonte com ajuste
  de UI no mesmo PR.
- Nunca incluir arquivos não rastreados que não fazem parte da mudança
  (conferir `git status` antes de cada commit; usar `git add <arquivo>`, não
  `git add -A`).

### 2. Commits (Conventional Commits, em português)

Formato:

```
<tipo>(<escopo>): <resumo no presente, minúsculo, sem ponto final>

<corpo opcional: o PORQUÊ da mudança e o que não é óbvio no diff,
quebrado em ~72 colunas>

<rodapé opcional: Refs #12 / Closes #12 / BREAKING CHANGE: ...>
```

- Resumo com no máximo ~72 caracteres, verbo na 3ª pessoa do presente
  ("corrige", "adiciona", "remove", "atualiza"), sem acento obrigatório.
  Ex.: `fix(scraper): corrige lote duplicado do MJ Leiloes`.
- Tipos permitidos:
  - `feat`: funcionalidade nova para o usuário (nova fonte, novo filtro)
  - `fix`: correção de bug
  - `refactor`: mudança de código sem mudar comportamento
  - `perf`: melhoria de desempenho
  - `test`: só testes
  - `docs`: só documentação (inclui este CLAUDE.md)
  - `ci`: workflows do GitHub Actions
  - `build`: dependências e requirements
  - `chore`: manutenção que não se encaixa acima (dados, limpeza)
  - `style`: só formatação/CSS sem mudança de comportamento
  - `revert`: reverte commit anterior (`revert: <resumo original>`)
- Escopos (opcional, mas preferível): `scraper`, `fonte-<nome>` (ex.:
  `fonte-pacto`), `health`, `dashboard`, `auth`, `favoritos`, `alertas`,
  `billing` (Stripe), `legal`, `site` (landing), `deploy`, `db`
  (Supabase/migrations), `ci`, `deps`, `docs`.
- Mudança que quebra compatibilidade (ex.: formato do `leiloes.json`, URL de
  favorito, schema do banco): `!` após o escopo e rodapé
  `BREAKING CHANGE: <o que quebra e como migrar>`.
- Todo commit feito pelo Claude termina com a linha de co-autoria
  `Co-Authored-By:` indicada pelo ambiente.

Critérios de granularidade (quando fazer um commit):

- Um commit por mudança lógica completa: dá pra descrever em uma linha sem
  usar "e". Se precisar de "e", provavelmente são dois commits.
- Cada commit deixa a suíte passando (`python -m pytest -q`). Teste vai no
  mesmo commit do código que ele cobre.
- Refactor separado de mudança de comportamento: primeiro o `refactor`, depois
  o `fix`/`feat` em cima.
- Dependência nova (`requirements*.txt`) vai no commit que passa a usá-la.
- Doc que descreve a mudança vai no mesmo commit da mudança; atualização do
  STATUS/BACKLOG deste arquivo pode ser um `docs:` separado no fim do PR.
- Commitar ao concluir cada passo do plano, não acumular tudo pro final. Nada
  de commit "wip"/"ajustes" na branch final; se acontecer, reorganizar antes
  de abrir o PR.

### 3. Pull Request

- Push da branch: `git push -u origin <branch>`.
- Abrir com `gh pr create --base main`. Título no mesmo formato de commit
  (`fix(fonte-pacto): ...`), porque vira o resumo no histórico.
- Corpo do PR (em português):

  ```
  ## Resumo
  <1-3 frases: o que muda e por quê>

  ## Mudanças
  - <item por arquivo/área relevante>

  ## Como foi testado
  - `python -m pytest -q`: N/N
  - <validação manual/ao vivo, se houve>

  ## Impacto em produção
  <o que muda no deploy da VPS / banco / Stripe / secrets; "nenhum" se nada>

  Closes #<issue>   (se houver)
  ```

- Terminar o corpo com a linha de atribuição do Claude Code indicada pelo
  ambiente.

### 4. Merge (feito pelo próprio Claude)

O repositório não usa auto-merge do GitHub; o Claude faz o merge depois do
CI, sem precisar pedir confirmação:

1. Esperar o CI: `gh pr checks <n> --watch`.
2. CI verde e sem conflito: `gh pr merge <n> --merge --delete-branch`
   (merge commit, preservando os commits atômicos da branch).
3. Voltar pra main local: `git switch main && git pull --ff-only`.
4. Apagar a branch do PR no remoto e no local (obrigatório após todo merge).
   O `--delete-branch` já tenta as duas coisas; conferir e completar o que
   faltar:
   - remoto: `git ls-remote --heads origin <branch>` deve vir vazio; se não,
     `git push origin --delete <branch>`;
   - local: `git branch --list <branch>` deve vir vazio; se não,
     `git branch -d <branch>` (`-D` só se o PR constar como MERGED);
   - `git fetch --prune` para limpar a referência `origin/<branch>`.
5. CI vermelho: corrigir na mesma branch (novo commit `fix`/`test`), push e
   repetir. Nunca fazer merge com CI vermelho nem pular o CI.
6. Conflito com a `main`: `git merge origin/main` na branch, resolver, rodar
   os testes, push e repetir.

Lembrete: merge na `main` dispara o `deploy.yml` (deploy na VPS). Conferir a
seção "Impacto em produção" do PR antes de mergear; se a mudança exigir passo
manual fora do repo (secret novo, migration no Supabase, config no Stripe),
avisar o dono no fim do turno.

## Documentação em Markdown

Doc novo é exceção, não regra. A maior parte do registro já fica no commit,
no PR e nas issues.

### Quando NÃO criar um `.md` novo

- Correção pequena, ajuste de UI, refactor, bump de dependência: o
  commit + a descrição do PR bastam.
- Status de andamento: uma linha no STATUS deste `CLAUDE.md` (com data e link
  pro doc, se houver).
- Pendência, ideia, próximo passo: abrir GitHub Issue (ver "Issue tracker"
  abaixo), não criar `PENDENCIAS_*.md`/`PROXIMOS_PASSOS_*.md` novos.
- Assunto que já tem doc: atualizar o doc existente (nova seção datada), não
  criar outro ao lado.

### Quando criar

- Fonte nova integrada ao scraper → `docs/contexto/fontes/ativas/`.
- Fonte pausada/descartada → mover/criar em `docs/contexto/fontes/pausadas/`.
- Incidente com investigação não trivial (causa raiz que não cabe no PR) →
  `docs/contexto/fontes/incidentes/` (fontes) ou `docs/contexto/` (resto).
- Guia operacional que alguém vai seguir passo a passo (setup, deploy,
  rollback) → `docs/contexto/setup/`.
- Decisão de arquitetura com alternativas descartadas → ADR em `docs/adr/`
  (formato em `docs/agents/domain.md`).

### Padrão dos arquivos

- Nome: `MAIUSCULO_COM_UNDERSCORE.md`, sem acento. Sufixo de data
  (`_AAAA-MM` ou `_AAAA-MM-DD`) só em docs de um momento (incidente,
  investigação, pesquisa); guias vivos não levam data.
- Estrutura mínima:

  ```
  # <Título> (<status curto>, AAAA-MM-DD)

  > Resumo: 2-3 linhas com o essencial. Quem só ler isto tem que entender.

  ## Contexto
  ## <Corpo: Causa raiz / Implementação / Passo a passo, conforme o tipo>
  ## Pendências   (se houver; preferir linkar issues)
  ## Referências  (PRs, issues, arquivos de código)
  ```

- Português, Markdown simples (títulos `#`/`##`, listas, blocos de código com
  linguagem), sem emojis, links relativos para outros docs/arquivos do repo.
- Todo doc novo é linkado de algum lugar (STATUS deste arquivo ou outro doc);
  doc órfão não existe.

## Agent skills

### Issue tracker

Issues rastreadas como GitHub Issues (mounjour/leilao-ce, via CLI `gh`). Ver `docs/agents/issue-tracker.md`.

### Triage labels

Labels padrão (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). Ver `docs/agents/triage-labels.md`.

### Domain docs

Layout single-context (CONTEXT.md + docs/adr/ na raiz). Ver `docs/agents/domain.md`.
