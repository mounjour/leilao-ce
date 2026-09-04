# Docs de domínio

Como os skills de engenharia devem consumir a documentação de domínio deste repo ao explorar o codebase.

## Antes de explorar, leia isto

- **`CONTEXT.md`** na raiz do repo.
- **`docs/adr/`**: leia as ADRs que tocam a área em que você vai trabalhar.

Se algum desses arquivos não existir, **prossiga em silêncio**. Não sinalize a ausência; não sugira criá-los de antemão. O skill `/domain-modeling` (acessado via `/grill-with-docs` ou `/improve-codebase-architecture`) os cria de forma preguiçosa quando termos ou decisões forem de fato resolvidos.

## Estrutura de arquivos

Repo single-context (este repo):

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-....md
│   └── 0002-....md
├── docs/agents/
└── dashboard.py, scraper.py, ...
```

## Use o vocabulário do glossário

Quando sua saída nomear um conceito de domínio (título de issue, proposta de refactor, hipótese, nome de teste), use o termo como definido em `CONTEXT.md`. Não escorregue pra sinônimos que o glossário evita explicitamente.

Se o conceito de que você precisa ainda não está no glossário, isso é um sinal: ou você está inventando linguagem que o projeto não usa (reconsidere) ou há uma lacuna real (anote pro `/domain-modeling`).

## Sinalize conflitos com ADRs

Se sua saída contradiz uma ADR existente, sinalize isso explicitamente em vez de sobrescrever silenciosamente:

> _Contradiz a ADR-0007 (nome da decisão), mas vale reabrir porque…_
