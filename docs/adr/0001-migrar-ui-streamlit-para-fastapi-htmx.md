# ADR 0001: Migrar a interface do Streamlit para FastAPI + HTMX (aceita, 2026-11-13)

> Resumo: a interface do app (`dashboard.py` + `auth.py`) sai do Streamlit e passa
> para **FastAPI + Jinja2 + HTMX + Alpine.js**, servida no mesmo `/app/` e com o
> mesmo design system da landing (`site/css/tokens.css`). A migração **só começa
> depois** que o site voltar ao ar no Streamlit na hospedagem nova (issue #28), e é
> feita em fases, com o app novo rodando ao lado do atual até a troca de rota.

## Contexto

O Streamlit foi uma boa escolha para validar o produto, mas virou o limite do
visual e da manutenção:

- **Metade do esforço de UI é contornar o framework.** Cerca de 760 das 1.681
  linhas de `dashboard.py` são CSS que sobrescreve o Streamlit, com 106 seletores
  presos à estrutura interna dele (`data-testid`, `.stApp`). Por isso a versão
  fica travada em `streamlit==1.62.0`: subir de versão pode quebrar o visual.
  Dos 113 commits em `dashboard.py`/`auth.py` até 2026-11-13, 56 são de CSS,
  sidebar, tema escuro, mobile ou scroll.
- **Gambiarras em JavaScript.** A sessão é guardada num cookie gravado por
  `components.html` com `<script>` (`auth._cookie_js`), porque o Streamlit não
  emite cookie. O refresh token do Supabase fica num cookie legível por JS (sem
  `HttpOnly`). A volta ao topo depois de paginar também é um script injetado.
- **Sem URL por tela.** Cada clique roda o script inteiro de novo
  (`st.rerun()`), e as "páginas" são `st.session_state["pagina"]`. Não existe
  link de lote para compartilhar no WhatsApp nem página indexável, o que pesa
  no funil (#37).
- **O Streamlit encarece a hospedagem.** O WebSocket sempre aberto e o estado
  por sessão em memória são o motivo de a pesquisa de hospedagem
  ([PESQUISA_HOSPEDAGEM_2026-11.md](../contexto/PESQUISA_HOSPEDAGEM_2026-11.md))
  ter descartado os PaaS e exigido datacenter no Brasil.

O que torna a migração viável:

- O catálogo é pequeno (363 lotes, ~420 KB de `leiloes.json` em 2026-11-13).
- O webhook do Stripe já roda fora do app (`supabase/functions/stripe-webhook`).
- Os tokens visuais já são compartilhados com a landing (`site/css/tokens.css`,
  `design_tokens.py`).
- As regras de negócio (`favorites.py`, `_normalizar_url`, checkout e portal do
  Stripe, chamadas ao Supabase em `auth.py`) são Python e têm testes.

## Decisão

Reescrever a camada de apresentação em **FastAPI + Jinja2 + HTMX**, com
**Alpine.js** para interações locais (filtros instantâneos, menus), mantendo:

- **Python** no servidor, reaproveitando `favorites.py` e a parte de
  Supabase/Stripe de `auth.py`, separada do código de UI.
- **O mesmo caminho `/app/`**, para não mexer em `APP_URL`, nas Redirect URLs do
  Supabase, nas URLs de retorno do Stripe nem no `map` de links antigos do Nginx.
- **Sessão em cookie `HttpOnly` + `Secure` + `SameSite=Lax`** emitido pelo
  servidor, com refresh do token do Supabase no backend. Sai o cookie gravado
  por JavaScript.
- **URLs reais** para cada tela: `/app/`, `/app/lote/<id>`, `/app/favoritos`,
  filtros na query string.
- **Um só design system**: templates usando `site/css/tokens.css`, sem o CSS de
  correção do Streamlit.
- **Paywall no servidor**, como hoje: só quem tem assinatura ativa recebe o
  catálogo completo.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Continuar no Streamlit e caprichar no CSS (`st.html`, componente próprio para o grid) | Não resolve recarregar a cada clique, falta de URL nem cookie. O CSS continua preso à estrutura interna e trava a versão. Serve só como ponte até a fase 3. |
| Reflex / NiceGUI | Mais personalizáveis, mas mantêm WebSocket e estado no servidor (o mesmo problema de hospedagem). O Reflex ainda exige build em Node e tem API instável. |
| Dash | Feito para painel analítico, não para produto SaaS com login e paywall. |
| Next.js / SvelteKit / Astro + Supabase JS (frontend estático, paywall por RLS) | Teto visual mais alto e o site poderia sair da VPS (Cloudflare Pages grátis). Mas é reescrita em TypeScript (~15 a 25 dias contra ~8 a 12), troca de stack para um dev só, e exige levar o catálogo para uma tabela com RLS. Fica como evolução possível depois, se o produto pedir. |
| Migrar a UI junto com a troca de hospedagem | O site está fora do ar desde ~15/10. Subir o Streamlit pelos guias atuais leva horas; reescrever antes adiaria a volta em semanas e misturaria dois riscos. |

## Consequências

Positivas:

- Visual igual ao da landing e sem quebrar a cada versão do framework.
- Cookie de sessão mais seguro (`HttpOnly`) e sem script injetado.
- Links de lote compartilháveis e páginas públicas indexáveis.
- App sem estado por sessão: 1 GB de RAM sobra, latência pesa menos (uma
  requisição HTTP por ação, não um WebSocket aberto). A Hostinger KVM 1
  provavelmente comporta também a Evolution API, sem precisar da KVM 2.
- Deploy quase igual: Nginx + systemd, com `uvicorn` no lugar do `streamlit` e
  sem os cabeçalhos de WebSocket.

Negativas e riscos:

- Fluxo de login (PKCE, `?code=`, confirmação de e-mail, troca de senha) precisa
  de teste ponta a ponta igual ao da migração de 2026-09-15.
- O Streamlit Community Cloud deixa de servir de reserva (#31), porque só roda
  Streamlit.
- O painel de tokens da IA (`render_painel_tokens`) usa componentes prontos do
  Streamlit; vira uma página simples de admin.
- Durante as fases 2 e 3 há dois apps no ar, e mudança de regra de negócio tem de
  ir para os dois (ou ficar congelada).

## Plano em fases

1. **Volta do site (fora deste ADR, issue #28).** VPS nova com o Streamlit
   atual, pelos guias existentes, sem mudar a interface.
2. **Separar regra de negócio da UI.** Tirar de `auth.py` o que é Supabase/Stripe
   (login, cadastro, sessão, checkout, portal) para um módulo sem `streamlit`,
   com testes. O Streamlit continua usando o módulo novo (`refactor`, sem mudança
   de comportamento).
3. **App novo em `/app2/`**, atrás do mesmo Nginx, na ordem:
   1. catálogo público de amostra e página do lote;
   2. cadastro, login, PKCE, troca de senha e logout;
   3. paywall, checkout, portal e catálogo completo com filtros, abas e paginação;
   4. favoritos, páginas de conteúdo (`sobre`, `como comprar`, `informações`),
      páginas legais e menu do usuário;
   5. página de admin com o painel de tokens.
4. **Troca de rota.** O Nginx passa a mandar `/app/` para o FastAPI; o Streamlit
   fica alguns dias em `/app-legado/` como reserva. Validar: cadastro, login,
   paywall, Stripe Checkout, portal, favoritar, links antigos (`/?code=…`).
5. **Limpeza.** Remover `streamlit` de `requirements-web.txt`, o drop-in do
   `baseUrlPath` em `deploy/systemd/`, o `.streamlit/` e o CSS de correção;
   desligar o Streamlit Community Cloud (#31); atualizar
   [SETUP_HOSTINGER_VPS.md](../contexto/setup/SETUP_HOSTINGER_VPS.md),
   [CUTOVER_LANDING.md](../contexto/setup/CUTOVER_LANDING.md) e o `CLAUDE.md`.

Estimativa das fases 2 a 5: ~8 a 12 dias de trabalho focado.

## Pendências

- Abrir uma issue por fase quando a #28 for resolvida.
- Decidir se a amostra pública de lotes (fase 3.1) mostra preço/FIPE ou só
  título e foto, para não esvaziar o paywall.

## Referências

- `dashboard.py`, `auth.py` (`_cookie_js`, `_restore_session_from_cookie`),
  `favorites.py`, `design_tokens.py`, `site/css/tokens.css`
- `deploy/nginx/leilao-ce.conf`, `deploy/systemd/leilao-ce-baseurl.conf`
- [PESQUISA_HOSPEDAGEM_2026-11.md](../contexto/PESQUISA_HOSPEDAGEM_2026-11.md)
- Issues #28 (hospedagem), #31 (Streamlit Community Cloud), #37 (funil)
