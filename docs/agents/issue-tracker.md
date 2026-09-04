# Issue tracker: GitHub

Issues e specs deste repo vivem como GitHub issues. Use a CLI `gh` para todas as operações.

Repo: `mounjour/leilao-ce`.

## Convenções

- **Criar uma issue**: `gh issue create --title "..." --body "..."`. Use heredoc para bodies multi-linha.
- **Ler uma issue**: `gh issue view <number> --comments`, filtrando comentários com `jq` e também buscando labels.
- **Listar issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` com `--label` e `--state` apropriados.
- **Comentar numa issue**: `gh issue comment <number> --body "..."`
- **Aplicar / remover labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Fechar**: `gh issue close <number> --comment "..."`

O repo é inferido de `git remote -v`; `gh` faz isso automaticamente quando rodado dentro do clone.

## Pull requests como superfície de triagem

**PRs como superfície de requisição: não.** _(Mude para `sim` se este repo trata PRs externos como feature requests; `/triage` lê essa flag.)_

Quando `sim`, PRs passam pelos mesmos labels e estados que issues, usando os equivalentes `gh pr`:

- **Ler um PR**: `gh pr view <number> --comments` e `gh pr diff <number>` para o diff.
- **Listar PRs externos para triagem**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`, mantendo só `authorAssociation` de `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` ou `NONE` (descartar `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comentar / rotular / fechar**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

O GitHub compartilha um espaço de números entre issues e PRs, então um `#42` isolado pode ser qualquer um dos dois: resolva com `gh pr view 42`, com fallback para `gh issue view 42`.

## Quando um skill diz "publicar no issue tracker"

Criar uma GitHub issue.

## Quando um skill diz "buscar o ticket relevante"

Rodar `gh issue view <number> --comments`.

## Operações de wayfinding

Usadas por `/wayfinder`. O **map** é uma única issue com issues **filhas** como tickets.

- **Map**: uma issue única rotulada `wayfinder:map`, guardando o corpo de Notes / Decisions-so-far / Fog. `gh issue create --label wayfinder:map`.
- **Ticket filho**: uma issue linkada ao map como GitHub sub-issue (`gh api` no endpoint de sub-issues). Onde sub-issues não estiverem habilitadas, adicionar o filho a uma task list no corpo do map e colocar `Part of #<map>` no topo do corpo do filho. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Uma vez reivindicado, o ticket é atribuído ao dev que está dirigindo.
- **Bloqueio**: **dependências nativas de issue** do GitHub, a representação canônica e visível na UI. Adicionar uma aresta com `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, onde `<blocker-db-id>` é o **database id** numérico do bloqueador (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _não_ o `#number` nem o `node_id`). O GitHub reporta `issue_dependencies_summary.blocked_by` (só bloqueadores abertos, o gate ao vivo). Onde dependências não estiverem disponíveis, usar uma linha `Blocked by: #<n>, #<n>` no topo do corpo do filho. Um ticket fica desbloqueado quando todo bloqueador está fechado.
- **Frontier query**: listar os filhos abertos do map (`gh issue list --state open`, restrito às sub-issues/task list do map), descartar qualquer um com bloqueador aberto (`issue_dependencies_summary.blocked_by > 0`, ou uma issue aberta na linha `Blocked by`) ou com assignee; o primeiro na ordem do map vence.
- **Claim**: `gh issue edit <n> --add-assignee @me`, a primeira escrita da sessão.
- **Resolve**: `gh issue comment <n> --body "<resposta>"`, depois `gh issue close <n>`, depois anexar um ponteiro de contexto (gist + link) ao Decisions-so-far do map.
