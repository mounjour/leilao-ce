CONTEXTO DO PROJETO:
- SaaS de monitoramento de leilões no Ceará
- Deploy: leilaoce.streamlit.app (Streamlit Community Cloud, atualiza no push do main)
- Repo: github.com/mounjour/leilao-ce
- Hoje configuramos GitHub Actions (.github/workflows/scraper.yml) que roda o scraper 2x/dia (03h e 15h Fortaleza) e commita leiloes.json atualizado automaticamente. Documentação em SETUP_GITHUB_ACTIONS.md.

PRÓXIMOS PASSOS (roadmap):
1. Adicionar mais sites de scraping (Mega Leilões, Sodré Santoro)
2. Sistema de favoritos (botão coração + página "Meus favoritos" + SQLite)
3. Cadastro/login (streamlit-authenticator ou Supabase Auth)
4. Planos pagos (Stripe)

CONVENÇÕES:
- Mensagens em português, código em inglês (variáveis, funções)
- Sem emojis dentro de código Python, apenas no UI do Streamlit
- Antes de mudanças grandes, sempre apresente um plano para eu aprovar
- Não rode "git push" sem me perguntar primeiro
