# Pesquisa de hospedagem — alternativas à VPS Hostinger KVM 1 (2026-11)

> Pesquisa feita em **2026-11-13**. Preços de nuvem mudam com frequência (houve reajustes em
> Hetzner, Contabo, Fly.io e Oracle ao longo de 2026): **confira o checkout antes de contratar.**
> Só pesquisa, nada foi alterado no deploy.

## TL;DR

| | Opção | Custo real/mês | Por quê |
|---|---|---|---|
| ✅ **Recomendação** | **Hostinger KVM 1 recontratada na promoção de 24 meses** (datacenter Brasil) | **R$ 29,99** (R$ 719,76 à vista) | Mesmo produto, mesmo setup (`deploy/` e guias valem sem mudança), datacenter no Brasil, ~45% mais barato que os ~R$ 54 atuais. Como a VPS atual parece ter expirado, é contratar uma nova, não "migrar". |
| ✅ variação | **Hostinger KVM 2** (2 vCPU/8 GB) na promoção de 24 meses | **R$ 42,99** | Se quiser juntar a **Evolution API** na mesma máquina e desligar a VPS separada dela. Duas VPS viram uma. |
| 🅱️ **Plano B** | **Oracle Cloud Always Free (Ampere A1, região São Paulo/Vinhedo)** | **R$ 0** | 2 OCPU/12 GB grátis, cabe site + Evolution. Riscos reais (falta de capacidade, recuperação de instância ociosa, sem suporte), então só como B ou para teste. |
| ⚠️ barato, mas longe | Contabo Cloud VPS 4 (4 vCPU/8 GB, EUA/Europa) | ~R$ 31–37 | Muita máquina pelo preço, mas sem datacenter no Brasil: latência ~3× maior para o WebSocket do Streamlit. |

**Nada de PaaS** (Fly, Railway, Render, Koyeb, Cloud Run) sai mais barato *e* tão bom para um
Streamlit sempre ligado com WebSocket: ou dorme, ou tem 512 MB, ou fica fora da América do Sul, ou
custa mais. A landing pode ir para **Cloudflare Pages** de graça, mas na VPS ela já sai de graça
(é Nginx servindo arquivo), então mover só faz sentido se o app sair da VPS.

---

## 1. O que precisa rodar (requisitos)

Do repo (`deploy/nginx/leilao-ce.conf`, `deploy/systemd/leilao-ce-baseurl.conf`,
[`SETUP_HOSTINGER_VPS.md`](setup/SETUP_HOSTINGER_VPS.md), [`SETUP_EVOLUTION.md`](setup/SETUP_EVOLUTION.md)):

1. **Streamlit** (`dashboard.py`, deps de `requirements-web.txt`: streamlit, supabase, stripe,
   requests, dotenv), processo único **sempre ligado** em `127.0.0.1:8501`, servido em `/app/` com
   **WebSocket** (`Upgrade`/`Connection` no Nginx). Medido em 2026-09: catálogo ~6 MB em memória;
   o que pesa é sessão por usuário conectado. **1 GB de RAM com swap roda; 2 GB é confortável.**
2. **Landing estática** (`site/`) na raiz, mais o `map` que manda links antigos (`?code=`,
   `?payment=`…) para `/app/`.
3. **Nginx + HTTPS** (Let's Encrypt) para `achadinleiloes.tech` e o redirecionamento do `www`.
4. **Opcional: Evolution API** (Docker: API + Postgres + Redis, atrás do Caddy), que hoje fica em
   VPS separada. Soma ~1–1,5 GB de RAM. **Para juntar tudo numa máquina, 4 GB no mínimo, 8 GB com
   folga.**
5. Deploy por SSH a partir do GitHub Actions (`.github/workflows/deploy.yml`): precisa de VM com
   SSH ou de um PaaS com deploy por git.

Scraper, backup e banco ficam como estão (GitHub Actions + Supabase).

## 2. Premissas de câmbio e impostos

- **Câmbio** (fechamento de 09/11/2026): USD ≈ **R$ 5,51**; EUR ≈ **R$ 6,18**.
- **IOF de 3,5%** em compra internacional com cartão (Decreto 12.499/2025), mais **~4% de spread**
  típico de cartão. Fator efetivo usado na tabela: **USD × R$ 5,93** e **EUR × R$ 6,65**.
  Cartões com IOF zero (ex.: BTG, Nubank Ultravioleta) baixam isso ~3,5%.
- Cliente fora da UE **não paga IVA europeu**: Hetzner e Contabo cobram o preço "excl. VAT".
- Os preços em R$ (Hostinger, Magalu, Locaweb) já vêm com imposto.

## 3. Tabela comparativa

Latência = ida e volta **estimada** a partir de Fortaleza (rotas típicas: SP ~40–50 ms; costa
leste dos EUA ~110–130 ms; Europa via cabo EllaLink/Portugal ~120–170 ms). Não medi daqui. Cada
interação no Streamlit (clicar filtro, paginar) faz pelo menos uma ida e volta pelo WebSocket, então
ela se sente na hora de usar.

### 3.1 VPS (mantém o setup atual: Nginx + systemd + deploy por SSH)

| Provedor / plano | vCPU / RAM / disco | Preço de tabela | **R$/mês real** | Datacenter / latência | Observações e riscos |
|---|---|---|---|---|---|
| **Hostinger KVM 1, renovação (hoje)** | 1 / 4 GB / 50 GB NVMe | R$ 59,99 na renovação de 24m (dono relata ~R$ 54) | **~R$ 54–60** | Brasil (SP) · ~40–50 ms | Situação atual. A VPS está fora do ar desde ~15/10, provavelmente por falta de renovação. |
| **Hostinger KVM 1, contrato novo 24m** | 1 / 4 GB / 50 GB NVMe | R$ 29,99/mês (R$ 719,76 à vista) | **R$ 29,99** | Brasil (SP) · ~40–50 ms | Renova a **R$ 59,99**. Pagamento adiantado. Esforço de migração ≈ zero (mesmo guia). |
| **Hostinger KVM 2, contrato novo 24m** | 2 / 8 GB / 100 GB NVMe | R$ 42,99/mês (R$ 1.031,76 à vista) | **R$ 42,99** | Brasil (SP) | Cabe site + Evolution. Renova a R$ 77,99. |
| **Oracle Always Free, Ampere A1** | até 2 OCPU / 12 GB (ARM) / 200 GB de bloco | grátis | **R$ 0** | SP ou Vinhedo · ~40–50 ms | Cota cortada de 4/24 para **2 OCPU/12 GB** em 2026. A1 vive com "out of host capacity". Instância **ociosa pode ser recuperada** (7 dias com CPU p95, rede **e** memória < 20%). Passar a conta para Pay-As-You-Go evita isso e segue grátis dentro da cota, mas pede verificação no cartão. Sem suporte humano no plano grátis. Instância só na região "home". |
| Oracle Always Free, AMD Micro | 1/8 OCPU / 1 GB | grátis | R$ 0 | idem | Fraca demais para Streamlit com usuários. |
| **Contabo Cloud VPS 4** | 4 / 8 GB / 100 GB SSD | €5,50 com IVA (24m), ≈ €4,62 sem IVA | **~R$ 31** (24m) a ~R$ 37 (mensal, + taxa de setup) | EUA ou Europa · ~120–170 ms | Muito recurso pelo preço, mas tem fama de *overselling* (CPU/disco variáveis) e suporte lento. Não achei região Brasil. |
| Hetzner CPX02 (Helsinque) | 1 / 1 GB / 20 GB | €5,49 | **~R$ 36,5** | Europa · ~150–170 ms | Hetzner reajustou forte em 2026. A linha barata (CX23 2/4 GB a €5,99, CAX11 ARM a €6,49) aparece **"currently unavailable"**. O CX22 de €4,35 citado em `SETUP_EVOLUTION.md` não existe mais. |
| Hetzner CPX12 (Helsinque) | 1 / 2 GB / 40 GB | €9,99 | ~R$ 66 | Europa | Mais caro que a Hostinger e mais longe. |
| **Magalu Cloud BV1-2-20** | 1 / 2 GB / 20 GB | R$ 54,99 (impostos inclusos) | **R$ 54,99** | **Fortaleza (NE1)** ou SP · ~5 ms | Datacenter **em Fortaleza**, cobra em R$ por hora, IPv4 grátis "por enquanto". Mesmo preço de hoje com metade da RAM. BV1-1-20 (1 GB) sai R$ 44,99. |
| Locaweb Cloud Linux Small | 1 / 2 GB / 60 GB | R$ 40 + R$ 5 de IP público | **R$ 45** | Brasil | Micro (1 GB) sai R$ 25 com IP, mas é apertado. Página não informa o datacenter. |
| Akamai/Linode Nanode (SP) | 1 / 1 GB / 25 GB | US$ 7 | ~R$ 41,5 | SP · ~40–50 ms | São Paulo custa US$ 2 a mais que a tabela global. 1 GB é apertado. |
| Vultr Cloud Compute (SP) | 1 / 1 GB / 25 GB | US$ 7,50 | ~R$ 44,5 | SP | Idem: 1 GB. |
| DigitalOcean Basic | 1 / 1 GB / 25 GB | US$ 6 (2 GB: US$ 12) | ~R$ 35,6 (2 GB: ~R$ 71) | Sem região na América do Sul; NY ~120 ms | — |

### 3.2 PaaS (sem servidor para administrar)

Todos exigiriam trocar Nginx/systemd por Dockerfile ou buildpack, e a landing + o `map` dos links
antigos iriam para outro lugar (Cloudflare) ou para dentro do container.

| Plataforma | Config viável | Preço | **R$/mês real** | Região / latência | WebSocket / sempre ligado | Riscos |
|---|---|---|---|---|---|---|
| **Fly.io** | 1 GB em `gru` (São Paulo) | US$ 8,78 em Ashburn × 1,615 (multiplicador de `gru`) ≈ US$ 14,18; 512 MB ≈ US$ 7,09 | **~R$ 84** (512 MB: ~R$ 42) | **SP** ✓ | Sim / sim (máquina parada não cobra) | Tabela nova desde 01/10/2026. Teve incidente de falta de capacidade em `gru` em 10/2026. IPv4 compartilhado grátis, TLS do domínio grátis. |
| **Railway** Hobby | ~0,5 GB, CPU baixa | US$ 5/mês com US$ 5 de uso incluso; RAM ~US$ 10/GB·mês, CPU ~US$ 20/vCPU·mês | **~R$ 30–50** (varia com uso) | Não achei região na América do Sul · ~120 ms+ | Sim / sim | Conta é por uso: pico de usuários vira conta maior. |
| **Render** Starter | 512 MB / 0,5 CPU | US$ 7 | **~R$ 41,5** | EUA/Europa/Singapura · ~120 ms+ | Sim / sim no pago; o **grátis dorme após 15 min** (30–60 s para acordar) | 512 MB é o limite de baixo para Streamlit. |
| **Koyeb** | — | Pro US$ 29/mês + compute | **> R$ 170** | Sem SP | — | Não há mais plano de entrada barato para serviço sempre ligado. Descartado. |
| **Google Cloud Run** (`southamerica-east1`, min-instances=1, CPU sempre alocada) | 1 vCPU / 1 GiB | Tier 2: US$ 0,0000216/vCPU·s + US$ 0,0000024/GiB·s, menos a cota grátis | **~R$ 340** (≈ US$ 58) | SP ✓ | Sim, mas com timeout máximo de 60 min por conexão | Caro para processo 24/7. Descartado. |
| **Streamlit Community Cloud** (já no ar como rollback) | — | grátis | **R$ 0** | EUA | Sim / **dorme após 12 h sem tráfego** | Não aceita domínio próprio (pelo que achei). Não é "tão bom quanto": serve só como contingência. |

### 3.3 Landing estática

| Opção | Custo | Observações |
|---|---|---|
| **Cloudflare Pages** | R$ 0 | 500 builds/mês, 20.000 arquivos, 100 domínios por projeto, CDN global. Para servir o app em `/app/` no mesmo domínio, precisa de um Worker/regra de proxy, **ou** mover o app para `app.achadinleiloes.tech`, o que mexe em `APP_URL`, nas Redirect URLs do Supabase e nos links antigos do `map`. |
| GitHub Pages | R$ 0 | Mesmo problema de roteamento. Sem regras de redirect por query string. |
| **Nginx na própria VPS (hoje)** | R$ 0 a mais | Continua sendo a opção mais simples enquanto o app ficar numa VPS. |

## 4. Análise

- **O que mais pesa na qualidade é o datacenter.** Para Streamlit, latência é UX: cada clique é
  uma ida e volta pelo WebSocket. Brasil (Hostinger SP, Oracle SP/Vinhedo, Magalu Fortaleza,
  Linode/Vultr SP, Fly `gru`) fica bem à frente de EUA/Europa (Contabo, Hetzner, DO, Render,
  Railway).
- **Entre as opções no Brasil com ≥ 2 GB de RAM, a Hostinger na promoção é imbatível**: R$ 29,99
  por 4 GB contra R$ 54,99 por 2 GB no Magalu e R$ 45 no Locaweb. A pegadinha é a renovação: no
  fim dos 24 meses volta a ~R$ 60. Dá para planejar desde já: lembrete 1 mês antes e recontratar em
  promoção ou migrar.
- **Juntar a Evolution API** na mesma máquina elimina a segunda VPS. KVM 2 (R$ 42,99) com 8 GB
  sobra para os dois. Na KVM 1 (4 GB) também cabe, com swap, se o tráfego continuar pequeno.
- **Oracle Always Free** é a única opção realmente grátis e de boa qualidade técnica (ARM, 12 GB,
  SP). Mas o histórico de mudanças unilaterais (cota cortada pela metade em 06/2026, critério de
  ociosidade subindo de 10% para 20%) e a falta de suporte fazem dela um risco para um SaaS que
  cobra assinatura. Bom plano B, ou para hospedar só a Evolution.
- **PaaS** só compensaria se o dono quisesse deixar de administrar servidor. O mais próximo de
  "tão bom quanto" é o Fly.io em `gru`, que custa ~R$ 84 por 1 GB, mais caro que hoje.

## 5. Recomendação

**Principal:** contratar uma **Hostinger KVM 1 nova no plano de 24 meses** (R$ 29,99/mês,
R$ 719,76 à vista), **datacenter Brasil**, Ubuntu 24.04, e refazer o setup pelos guias existentes.
Economia de ~R$ 24/mês contra hoje (~R$ 580 em 2 anos).
→ Se o dono quiser trazer a Evolution junto e desligar a outra VPS: **KVM 2** a R$ 42,99.

**Plano B:** **Oracle Cloud Always Free, A1 Flex**, região home **São Paulo** (ou Vinhedo), shape
1–2 OCPU / 6–12 GB, Ubuntu 24.04 ARM. Converter a conta para Pay-As-You-Go para não ter a instância
recuperada (segue R$ 0 dentro da cota). Se o A1 der "out of host capacity" por dias, partir para o
plano C.

**Plano C (sem Brasil, mais recurso):** Contabo Cloud VPS 4 (~R$ 31–37) em região dos EUA, aceitando
a latência maior.

**Antes de decidir:** abrir o painel da Hostinger e ver por que a VPS caiu. Se foi só vencimento e
o contrato ainda está no período de carência, renovar por 1 mês pode trazer o site de volta na hora
enquanto o novo contrato é montado. Confirmar também se a promo de 24 meses vale para quem já é
cliente (a Hostinger costuma aplicar promoção a compra nova).

## 6. Passos de migração (alto nível)

Valem para qualquer VPS (Hostinger nova, Oracle, Contabo). O repo já tem tudo, menos os segredos.

1. **Juntar os segredos** do `.env` da VPS antiga (pode ter sido apagada): chaves do Supabase
   (URL, anon, service role), Stripe (`sk_test_`/`pk_test_`, price IDs), `APP_URL`, credenciais da
   Evolution. Recuperar pelos painéis Supabase/Stripe se o disco antigo não voltar.
2. **Provisionar** a VPS (Ubuntu 24.04; na Oracle, imagem **ARM/aarch64**: as deps do
   `requirements-web.txt` têm wheel ARM). Criar usuário `deploy`, chave SSH, firewall (22/80/443).
   Na Oracle, abrir 80/443 **também** na Security List da VCN, não só no `ufw`/iptables.
3. **App:** seguir `SETUP_HOSTINGER_VPS.md` (venv, `pip install -r requirements-web.txt`, unit do
   systemd) e copiar `deploy/systemd/leilao-ce-baseurl.conf` (baseUrlPath=app).
4. **Nginx + landing:** copiar `deploy/nginx/leilao-ce.conf` e `site/` para `/var/www/achadin`.
   Emitir o certificado com `certbot --nginx -d achadinleiloes.tech -d www.achadinleiloes.tech`
   (depois do passo 5, ou com `--webroot`).
5. **DNS:** apontar os registros A de `achadinleiloes.tech` e `www` para o IP novo (TTL baixo antes,
   se der). Supabase e Stripe **não mudam**, porque o domínio é o mesmo.
6. **Deploy automático:** atualizar os secrets `VPS_HOST`/`VPS_USER`/`VPS_SSH_KEY` no GitHub e
   dar um push de teste (ou rodar o workflow manualmente).
7. **Evolution (opcional, se for consolidar):** seguir `SETUP_EVOLUTION.md` na mesma máquina, com o
   Caddy num subdomínio (ex.: `wa.achadinleiloes.tech`) **ou** atrás do Nginx existente (o Caddy
   brigaria pela porta 443). Atualizar a URL da Evolution nos secrets do Actions e desligar a VPS
   antiga dela.
8. **Validar ponta a ponta:** `/app/_stcore/health`, cadastro, login, paywall, Stripe Checkout,
   portal, favoritar, links antigos (`/?code=…` → `/app/`), alerta de WhatsApp.
9. **Atualizar a documentação** (`CLAUDE.md` no bullet Deploy, `SETUP_HOSTINGER_VPS.md`) e criar um
   **lembrete de renovação** com 30 dias de antecedência, para a queda de 15/10 não se repetir.
10. Manter o Streamlit Community Cloud de rollback por alguns dias, como da última vez.

## 7. Fontes (consultadas em 2026-11-13)

- Hostinger Brasil, VPS (preços KVM 1/KVM 2, promoção de 24m e renovação, datacenter Brasil): <https://www.hostinger.com/br/servidor-vps>
- Hetzner Cloud, Regular Performance (CPX): <https://www.hetzner.com/cloud/regular-performance/>
- Hetzner Cloud, Cost-Optimized (CX/CAX, "currently unavailable"): <https://www.hetzner.com/cloud/cost-optimized/>
- Contabo VPS (Cloud VPS 4–18, taxa de setup, regiões): <https://contabo.com/en/vps/>
- Contabo, reajuste de 2026 (rastreador de terceiros): <https://pricingsaas.com/companies/contabo.main/diffs/2026Q2>
- Magalu Cloud, preços de VM (BV, SE1/NE1, IPv4, impostos): <https://docs.magalu.cloud/docs/computing/virtual-machine/instance-types-and-pricing/pricing>
- Magalu Cloud com datacenter em Fortaleza (O Povo, 2023): <https://www.opovo.com.br/noticias/economia/2023/12/13/amp/com-data-center-em-fortaleza-magazine-luiza-lanca-servico-de-nuvem.html>
- Locaweb Cloud, preços: <https://www.locaweb.com.br/locaweb-cloud/precos/>
- Oracle Always Free Resources (cota A1 2 OCPU/12 GB, critério de ociosidade, região home): <https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm>
- Corte da cota Oracle em 2026 (terceiro): <https://braindetox.kr/en/posts/oracle_always_free_tier_reduced_2026.html>
- Oracle: upgrade para PAYG evita recuperação de instância ociosa (relatos): <https://51sec.org/2023/02/24/oracle-cloud-cleaning-up-idle-compute-instances-how-to-keep-it>
- Akamai/Linode, preços de São Paulo: <https://www.akamai.com/es/cloud/pricing/sao-paulo> (via resultado de busca)
- Vultr São Paulo (agregador, verificado em 12/11/2026): <https://valebyte.com/en/vps/brazil/?city=Sao+Paulo>
- DigitalOcean Droplets: <https://www.digitalocean.com/pricing/droplets>
- Fly.io, preços (tabela vigente e multiplicador 1,615 de `gru`): <https://fly.io/pricing.md>, <https://fly.io/pricing-update/>, <https://docs.fly.io/about/pricing>
- Fly.io, incidente de capacidade em `gru` (10/2026): <https://isdown.app/status/fly-io/incidents/672950-capacity-issues-in-gru-region>
- Railway, preços: <https://railway.com/pricing>
- Render, Starter de US$ 7 e free com sleep de 15 min (terceiros): <https://temps.sh/blog/render-pricing-2026>, <https://www.activepieces.com/blog/render-pricing-2026-free-tier-workers-total-cost.md>
- Koyeb, preços: <https://www.koyeb.com/pricing>
- Google Cloud Run, preços (Tier 2, instance-based): <https://cloud.google.com/run/pricing>
- Streamlit Community Cloud, sleep de 12 h: <https://docs.streamlit.io/streamlit-community-cloud/manage-your-app>
- Cloudflare Pages, limites: <https://developers.cloudflare.com/pages/platform/limits/>
- IOF de 3,5% (Decreto 12.499/2025): <https://arqfinance.com/articles/aliquota-iof-compras-exterior-cartao>
- Câmbio (09/11/2026): <https://brasil61.com/n/dolar-hoje-fecha-em-leve-alta-a-r-5-51-apos-oscilar-entre-queda-e-valorizacao-bras2617447>, <https://diariodonordeste.verdesmares.com.br/negocios/1.3709586>

**Limitações:** as latências são estimativas, não medições. Preços de Vultr, Linode SP e Render vêm
de agregadores ou trechos de busca, não do checkout oficial (a página da Vultr bloqueou a consulta).
Não confirmei se a promo de 24m da Hostinger vale para cliente existente.
