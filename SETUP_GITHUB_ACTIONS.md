# Setup do GitHub Actions — LeilãoCE

Este projeto roda o scraper automaticamente via GitHub Actions, duas vezes por dia,
e faz commit do `leiloes.json` atualizado de volta no repositório.
O Streamlit Cloud detecta o novo commit e o dashboard mostra os dados frescos.

## Passos para ativar

### 1. Cadastrar a ANTHROPIC_API_KEY como Secret

1. Abra o repositório no GitHub: <https://github.com/mounjour/leilao-ce>
2. Vá em **Settings** → **Secrets and variables** → **Actions**
3. Clique em **New repository secret**
4. **Name:** `ANTHROPIC_API_KEY`
5. **Secret:** cole a sua chave (a mesma que está no `.env` local)
6. Clique em **Add secret**

> A chave nunca aparece em logs nem fica visível no código — é injetada como variável
> de ambiente apenas durante a execução do workflow.

### 2. Garantir permissão de escrita para o GITHUB_TOKEN

1. No repositório, vá em **Settings** → **Actions** → **General**
2. Role até **Workflow permissions** (no rodapé)
3. Marque **Read and write permissions**
4. Marque também **Allow GitHub Actions to create and approve pull requests** (opcional)
5. Clique em **Save**

> Isso permite que o workflow faça `git push` do `leiloes.json` atualizado.

### 3. Fazer o primeiro commit/push dos arquivos novos

No PowerShell, dentro da pasta do projeto:

```powershell
# Remover o arquivo lixo (não consegui pelo sandbox)
Remove-Item "new-item dashboard.py"

# Conferir o que mudou
git status

# Commitar tudo
git add .gitignore requirements.txt .github/workflows/scraper.yml SETUP_GITHUB_ACTIONS.md
git commit -m "chore: add GitHub Actions workflow + housekeeping (gitignore, requirements UTF-8)"
git push
```

### 4. Testar o workflow manualmente

1. Vá em <https://github.com/mounjour/leilao-ce/actions>
2. No menu lateral, clique em **Scraper LeilãoCE**
3. Clique em **Run workflow** → **Run workflow** (deixa o branch `main`)
4. Aguarde ~5–15 minutos (Playwright + Chromium + scraping de todas as cidades)
5. Se passar, você verá um novo commit `chore: atualiza leiloes.json [auto ...]`

## Como ajustar a frequência

No arquivo `.github/workflows/scraper.yml`, linha `cron`:

| Frequência         | Cron                  | Observação                          |
|--------------------|-----------------------|-------------------------------------|
| 2x ao dia (atual)  | `0 6,18 * * *`        | 03h e 15h Fortaleza (UTC-3)         |
| 4x ao dia          | `0 0,6,12,18 * * *`   | A cada 6 horas                      |
| 1x ao dia          | `0 9 * * *`           | 06h Fortaleza                       |
| A cada 3 horas     | `0 */3 * * *`         | Cuidado com limite de minutos       |
| Só dias úteis 8h   | `0 11 * * 1-5`        | 08h Fortaleza, seg–sex              |

> GitHub Actions roda em UTC. Fortaleza é UTC-3 (sem horário de verão).

## Limites do plano gratuito do GitHub Actions

- **Repos públicos:** ilimitado (gratuito)
- **Repos privados:** 2.000 minutos/mês
- Cada rodada do scraper consome **~5 a 15 minutos**. Com 2 rodadas/dia = ~600 min/mês.

## Troubleshooting

### O workflow falha no passo "Rodar scraper"
- Confira nos logs se a `ANTHROPIC_API_KEY` foi reconhecida (não aparece o valor, mas
  você verá se as chamadas à API estão funcionando).
- Pode ser que a Leilo tenha mudado o HTML — rode `debug.py` localmente para investigar.

### O workflow não faz push
- Confira o passo 2 acima — permissão de escrita do `GITHUB_TOKEN`.
- Confira se o branch padrão é `main` (se for `master`, ajuste no workflow).

### O Streamlit não atualiza
- Streamlit Cloud rebuilda em cada push. Aguarde ~1–2 minutos após o commit do bot.
- Se persistir, no painel do Streamlit Cloud clique em **Reboot app**.
