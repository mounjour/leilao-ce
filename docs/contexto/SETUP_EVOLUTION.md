# Setup da Evolution API — VPS dedicada (WhatsApp)

Sobe a Evolution API (WhatsApp não-oficial, via Baileys) numa VPS pequena e
separada do site. Usada por: `favorites.py` (WhatsApp ao favoritar um lote) e
`alertas.py` (aviso de mudança de lance + health check do scraper).

**Antes de gastar qualquer coisa aqui:** rode o workflow `teste_alerta.yml`
manualmente (GitHub → Actions → o workflow → **Run workflow**). Os secrets
`EVOLUTION_*` já existem no repo — se o WhatsApp chegar, uma instância já está
viva em algum lugar e talvez você só precise recuperar os 3 valores de quem
configurou, sem gastar nada novo.

Este guia é pra quando isso **não** funcionar e for preciso subir uma do zero.

---

## Arquitetura

Uma VPS pequena roda, via Docker, três programas juntos: a Evolution API, o
Postgres dela e o Redis dela. Na frente, o **Caddy** faz HTTPS automático —
usando um truque (`sslip.io`) que dá um endereço público de verdade **sem
comprar domínio**.

| Peça | Onde |
|---|---|
| Evolution API + Postgres + Redis | VPS (Docker Compose) |
| HTTPS / proxy reverso | Caddy, na mesma VPS |
| Painel de administração (Manager) | mesma VPS, só acessível por túnel SSH |
| WhatsApp pareado | um chip pré-pago dedicado, num celular à parte |

O site (Render) e o scraper (GitHub Actions) só fazem uma chamada HTTPS comum
pra essa VPS — como fariam pra qualquer API externa. Não precisa de rede
especial nem de os dois "se conhecerem".

---

## Checklist

- [ ] VPS contratada (Hostinger, KVM 1, Ubuntu 24.04)
- [ ] Servidor travado (chave SSH, `ufw`, `fail2ban`, updates automáticos)
- [ ] Docker + Docker Compose instalados
- [ ] Arquivos oficiais da Evolution baixados e ajustados (imagem travada em `v2.3.7`, sem Dokploy, painel só em localhost)
- [ ] `.env` preenchido (API key, banco, redis, URL pública)
- [ ] Caddy instalado e servindo HTTPS via `sslip.io`
- [ ] `docker compose up -d` rodando, `api` e `frontend` saudáveis
- [ ] Instância criada e WhatsApp pareado (QR escaneado com o chip)
- [ ] Os 3 valores colados no **Render** (Environment) e no **GitHub** (Secrets)
- [ ] Teste: favoritar um lote no site dispara WhatsApp; `teste_alerta.yml` roda ok

---

## 1. Contratar a VPS

**Hetzner Cloud**, plano **CX22** (2 vCPU, 4 GB RAM, 40 GB NVMe, ~€4,35/mês)
— mais barata e com specs melhores que qualquer plano de 2 GB do mercado (a
Hetzner reestruturou as linhas de preço em 2026 e o CX22 ficou mais barato
que o próprio plano de 2 GB deles). Essa VPS só roda a Evolution.

1. Crie a conta em <https://console.hetzner.cloud> (precisa de cartão —
   pode pedir verificação manual na 1ª compra, às vezes leva algumas horas).
2. **New Project** → dá um nome (ex.: `achadin-evolution`).
3. Dentro do projeto, **Add Server**.
4. **Location**: qualquer uma (Ashburn/EUA costuma ser a de menor latência
   pro Brasil entre as opções da Hetzner) — não importa muito, ninguém acessa
   essa VPS diretamente, é só a API respondendo chamadas.
5. **Image**: **Ubuntu 24.04**.
6. **Type**: aba **Shared vCPU** → **CX22**.
7. **SSH Key**: se já tiver uma chave pública sua, cole aqui (evita ter que
   trocar de senha pra chave depois, no [passo 2](#2-travar-o-servidor)). Se
   não tiver, pode pular e criar no passo 2.
8. **Volumes / Firewalls / Backups**: deixe tudo desmarcado — configuramos
   firewall por `ufw` na mão, e backup fica como melhoria futura.
9. **Create & Buy now**.

## 2. Travar o servidor

Igual ao que já fizemos para a outra VPS, mudando só as portas liberadas
(aqui não precisa de 8501/8000 — só SSH, HTTP e HTTPS).

Conecte `ssh root@IP_DA_VPS` e rode:

```bash
adduser deploy
usermod -aG sudo deploy

# no SEU PC, não na VPS — leva sua chave pública:
#   ssh-copy-id deploy@IP_DA_VPS

apt update && apt install -y ufw fail2ban unattended-upgrades
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

dpkg-reconfigure -f noninteractive unattended-upgrades
```

> Teste uma **nova** sessão SSH com a chave antes de fechar a atual.

Dali em diante, entre como `ssh deploy@IP_DA_VPS` (não mais root).

## 3. Instalar o Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
```

Saia e entre de novo no SSH pra o grupo `docker` valer. Confirme:

```bash
docker compose version
```

## 4. Baixar e ajustar os arquivos da Evolution

```bash
mkdir -p ~/evolution && cd ~/evolution
curl -fsSL -o docker-compose.yaml https://raw.githubusercontent.com/evolution-foundation/evolution-api/2.3.7/docker-compose.yaml
curl -fsSL -o .env https://raw.githubusercontent.com/evolution-foundation/evolution-api/2.3.7/.env.example
```

Esses são os arquivos **oficiais da versão 2.3.7**, direto do repositório —
não são inventados. Precisam de 3 ajustes antes de subir:

### 4.1 Travar a imagem em `v2.3.7`

O `docker-compose.yaml` oficial vem com `image: evoapicloud/evolution-api:latest`
— e o `:latest` de hoje já é a versão com a trava de licença (seção
"Boa notícia" do `render.yaml`... ver conversa anterior). Corrija:

```bash
sed -i 's|evoapicloud/evolution-api:latest|evoapicloud/evolution-api:v2.3.7|' docker-compose.yaml
```

### 4.2 Tirar as referências ao Dokploy

O compose foi feito pra um ambiente com Dokploy (outro PaaS self-hosted, que
a gente não está usando). Sem isso, o `docker compose up` falha procurando
uma rede que não existe:

```bash
sed -i '/dokploy-network/d' docker-compose.yaml
```

### 4.3 Painel (Manager) só em localhost

O `frontend` (painel de administração) vem exposto pra internet toda. Não
precisa — você só usa ele por túnel SSH:

```bash
sed -i 's|"3000:80"|"127.0.0.1:3000:80"|' docker-compose.yaml
```

### 4.4 Preencher o `.env`

Abra com `nano .env` (ou `vi`) e ajuste estas linhas (as outras ficam no
padrão do arquivo):

```bash
# gere uma senha forte pra API key e outra pro banco:
openssl rand -hex 24   # rode 2x, uma pra AUTHENTICATION_API_KEY, outra pra senha do banco
```

| Variável | Valor |
|---|---|
| `SERVER_URL` | `https://evolution.SEU-IP-COM-TRACOS.sslip.io` (monta no [passo 5](#5-caddy-https-sem-domínio)) |
| `AUTHENTICATION_API_KEY` | a 1ª senha gerada acima |
| `DATABASE_PROVIDER` | `postgresql` (já vem assim) |
| `DATABASE_CONNECTION_URI` | `postgresql://evolution:SENHA-DO-BANCO@evolution-postgres:5432/evolution?schema=evolution_api` |
| `CACHE_REDIS_ENABLED` | `true` (já vem assim) |
| `CACHE_REDIS_URI` | `redis://evolution-redis:6379/6` |

E **adicione no fim do arquivo** (não vêm no `.env.example`, mas o
`docker-compose.yaml` os usa pro Postgres):

```
POSTGRES_DATABASE=evolution
POSTGRES_USERNAME=evolution
POSTGRES_PASSWORD=SENHA-DO-BANCO
```

> Use a **mesma** senha em `POSTGRES_PASSWORD` e dentro do
> `DATABASE_CONNECTION_URI`.

## 5. Caddy (HTTPS sem domínio)

`sslip.io` é um serviço público que transforma um IP em um nome de DNS de
verdade — `evolution.123-45-67-89.sslip.io` resolve sozinho para o IP
`123.45.67.89`. Isso permite o Caddy emitir um certificado HTTPS real (Let's
Encrypt) **sem você comprar domínio nenhum**.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

Substitua `SEU-IP` pelo IP real da VPS com pontos trocados por traços (ex.:
`123.45.67.89` → `123-45-67-89`) e edite `/etc/caddy/Caddyfile`:

```
evolution.SEU-IP-COM-TRACOS.sslip.io {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
sudo systemctl reload caddy
```

Volte no `.env` (passo 4.4) e confirme que `SERVER_URL` usa **esse mesmo**
endereço `https://evolution.SEU-IP-COM-TRACOS.sslip.io`.

## 6. Subir tudo

```bash
cd ~/evolution
docker compose up -d
docker compose ps
```

Os três serviços (`api`, `evolution-postgres`, `redis`) devem ficar `Up`.
Confira de fora:

```bash
curl https://evolution.SEU-IP-COM-TRACOS.sslip.io
```

Deve responder um JSON com o status da Evolution (não um erro de TLS/504).

## 7. Parear o WhatsApp

Abra um túnel SSH pro painel (ele só escuta em localhost, de propósito):

```bash
ssh -L 3000:localhost:3000 deploy@IP_DA_VPS
```

Com o túnel aberto, no navegador **do seu PC**: `http://localhost:3000`.
Entre com a `AUTHENTICATION_API_KEY` como API key global. **New Instance** →
dê um nome (ex.: `achadin`) → ele mostra um **QR code**.

No celular com o **chip pré-pago dedicado**: WhatsApp → Aparelhos conectados
→ Conectar um aparelho → escaneia o QR. Pronto, a instância fica com o
WhatsApp pareado e ativa 24h — o celular não precisa ficar com a tela
acesa, só **online pelo menos 1x a cada ~14 dias** (WhatsApp multi-device
derruba a sessão se passar disso).

## 8. Pegar os 3 valores e colar nos dois lugares

| Valor | É... |
|---|---|
| `EVOLUTION_API_URL` | `https://evolution.SEU-IP-COM-TRACOS.sslip.io` |
| `EVOLUTION_API_KEY` | a `AUTHENTICATION_API_KEY` que você gerou |
| `EVOLUTION_INSTANCE` | o nome que você deu à instância (ex.: `achadin`) |

Cole nos dois lugares que o código lê:

1. **Render** → `leilao-ce` → **Environment** → substitui os 3 campos que
   estavam em branco.
2. **GitHub** → repo `mounjour/leilao-ce` → **Settings** → **Secrets and
   variables** → **Actions** → edita/cria `EVOLUTION_API_URL`,
   `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE` (os que já existem, sobrescreve).

## 9. Testar

- No site (Render): favorita um lote → deve chegar WhatsApp.
- GitHub → **Actions** → `teste_alerta.yml` → **Run workflow** → confere se
  chega a mensagem de teste.
- `scraper.yml` no próximo run (2×/dia) volta a mandar alerta de mudança de
  lance e aviso de fonte parada.

---

## Operação

**Reinício automático:** todos os serviços do compose têm `restart: always` —
sobrevivem a reboot da VPS sozinhos (o Docker já fica habilitado no boot pela
instalação padrão).

**Logs:** `docker compose logs -f api` (na pasta `~/evolution`).

**Reconexão do WhatsApp:** o celular do chip precisa ficar online pelo menos
1x a cada ~14 dias, senão a sessão cai e é preciso reparear (novo QR).

**Risco de banimento:** número não-oficial pode ser banido pela Meta em
2–8 semanas, sem aviso e sem recurso (risco já registrado no
`PLANO-DO-PROJETO.md`). Tenha 2–3 chips reserva.

**Atualizar a Evolution no futuro:** troque a tag da imagem (`sed` do
[passo 4.1](#41-travar-a-imagem-em-v237)) só depois de ler o changelog da
versão nova e confirmar que não trouxe de volta a exigência de licença.
Nunca use `:latest`.

**Backup:** o que importa de verdade é o volume `evolution_instances` (tem a
sessão do WhatsApp — sem ele, reparea do zero). O Postgres guarda histórico
de mensagens, não crítico pra função de alertas. Backup formal fica como
melhoria futura, não bloqueante.

---

## Troubleshooting

**`docker compose up` reclama de rede não encontrada.** Esqueceu o
[passo 4.2](#42-tirar-as-referências-ao-dokploy) (remover `dokploy-network`).

**`curl` na URL do Caddy dá erro de certificado.** DNS do `sslip.io` não
precisa de propagação (resolve na hora), mas confira se `ufw` liberou
80/tcp e 443/tcp, e se o IP no `Caddyfile` está exatamente igual ao IP da VPS.

**API responde 401 em tudo.** Confirme que está mandando o header
`apikey: SUA_AUTHENTICATION_API_KEY` nas chamadas, e que é o mesmo valor do
`.env`.

**Instância desconecta sozinha depois de duas semanas.** É o limite do
WhatsApp multi-device sem o celular pareado ficar online — reconecta o
celular à internet, ou reparea escaneando o QR de novo.

**Erro de conexão com o banco (`ECONNREFUSED` / Prisma).** Confira se
`DATABASE_CONNECTION_URI` usa o host `evolution-postgres` (nome do serviço no
compose, não `localhost`) e se a senha bate com `POSTGRES_PASSWORD`.
