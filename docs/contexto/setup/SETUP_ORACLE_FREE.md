# Setup na Oracle Cloud Always Free (Ampere A1) — Achadin Leilões

Guia das **diferenças** em relação a [`SETUP_HOSTINGER_VPS.md`](SETUP_HOSTINGER_VPS.md) para rodar o
site (Streamlit em `/app/` + landing estática na raiz) numa VM **Always Free** da Oracle Cloud.
Tudo que não aparece aqui (venv, `.env`, unit do systemd, sudoers do deploy, secrets do GitHub)
segue o guia da Hostinger e os arquivos versionados em [`deploy/`](../../../deploy/).

> Escrito em 2026-11-13, antes da migração. Contexto da escolha e comparação de preços em
> [`PESQUISA_HOSPEDAGEM_2026-11.md`](PESQUISA_HOSPEDAGEM_2026-11.md) (seção 5, plano B).
> A Oracle muda regras do Always Free sem aviso (a cota do A1 caiu de 4 OCPU/24 GB para
> 2 OCPU/12 GB em 2026): confira a página oficial de [Always Free Resources][free] antes.

## Riscos (ler antes de começar)

| Risco | O que acontece | Mitigação |
|---|---|---|
| **Recuperação de instância ociosa** | Em conta só "Free Tier", a Oracle recupera a VM se, por 7 dias, CPU, rede **e** memória ficarem abaixo de 20% (p95). O Achadin parado fica abaixo disso. | Converter a conta para **Pay-As-You-Go** (passo 1.2). Continua R$ 0 dentro da cota. |
| **Cobrança no PAYG** | Qualquer recurso fora da cota Always Free passa a ser cobrado no cartão (com IOF). | **Budget com alerta** (passo 1.3). Só usar shape `VM.Standard.A1.Flex` dentro de 2 OCPU/12 GB, até 200 GB de disco em bloco no total, até 5 backups de volume. Não criar load balancer, banco gerenciado nem outro shape. |
| **"Out of host capacity"** | A criação do A1 falha por falta de máquina na região. São Paulo tem um único Availability Domain, então não há para onde desviar. | Tentar 1 OCPU/6 GB, outros horários, ou já com a conta em PAYG. Se passar de ~3 dias, plano C (Contabo) da pesquisa. |
| **Região home é definitiva** | O Always Free só vale na região home, escolhida no cadastro. | Escolher **Brazil East (São Paulo)** ou **Brazil Southeast (Vinhedo)**. |
| **Sem suporte humano / conta encerrada** | O plano grátis não tem suporte, e há relatos de contas grátis encerradas sem aviso. | O app é quase sem estado (código e `leiloes.json` no git, dados no Supabase): reconstruir em outra VPS leva ~1 h. Ver [Plano de saída](#plano-de-saída). |

## 1. Conta (dono do projeto)

1. Cadastro em <https://signup.cloud.oracle.com>. **Região home: São Paulo** (ou Vinhedo). Exige
   cartão de crédito; há uma verificação de ~US$ 1 que é estornada. Débito e cartão virtual
   costumam ser recusados.
2. **Converter para Pay-As-You-Go:** Console → menu do perfil → *Billing* → *Upgrade and Manage
   Payment* → *Upgrade to Pay As You Go*. Pode aparecer uma pré-autorização temporária no cartão.
3. **Budget:** *Billing & Cost Management* → *Budgets* → *Create Budget*, escopo no compartimento
   raiz (tenancy), valor US$ 1/mês, alerta em 1% do valor **real** (*actual*), mandando e-mail
   para o dono. Qualquer centavo cobrado vira e-mail.

## 2. Instância

*Compute* → *Instances* → *Create instance*:

- **Image:** Canonical Ubuntu 24.04 (a variante **aarch64**, que aparece ao escolher o shape A1).
- **Shape:** *Ampere* → `VM.Standard.A1.Flex`, **2 OCPU / 12 GB** (ou 1/6 se faltar capacidade).
  O rótulo "Always Free-eligible" tem que aparecer.
- **Networking:** criar uma VCN nova com sub-rede **pública**, *Assign a public IPv4 address* ligado.
- **SSH:** colar a chave **pública** pessoal do dono (a do deploy é gerada depois, ver o passo 6
  do guia da Hostinger).
- **Boot volume:** 50 GB basta (o padrão de ~47 GB também serve).

Usuário inicial da imagem Ubuntu: **`ubuntu`** (não `root`): `ssh ubuntu@IP`. O usuário
`leilao` do guia da Hostinger é criado em seguida, como `ubuntu` com `sudo`.

### IP público

O IP **efêmero** sobrevive a reboot e a stop/start, mas se perde se a instância for terminada.
Melhor reservar: *Networking* → *IP Management* → *Reserved Public IPs* → reservar e associar à
VNIC da instância (trocando o efêmero). A cota grátis de IP reservado não está bem documentada
(relatos falam em 1 por conta). Se der erro de limite, seguir com o efêmero.

## 3. Firewall: duas camadas

Na Oracle o tráfego passa por **duas** barreiras, e as duas precisam liberar 80 e 443.

### 3.1 Security List da VCN (no console)

*Networking* → *Virtual Cloud Networks* → a VCN → *Security Lists* → *Default Security List* →
*Add Ingress Rules*: origem `0.0.0.0/0`, TCP, porta de destino `80`; repetir para `443`. A 22 já
vem liberada.

### 3.2 iptables da imagem (na VM)

A imagem Ubuntu da Oracle vem com regras de iptables que **rejeitam tudo menos a 22**. **Não usar
`ufw`** (conflita com essas regras; o passo de `ufw` do guia da Hostinger não se aplica aqui).

```bash
sudo iptables -L INPUT --line-numbers
```

Achar o número `N` da linha `REJECT ... reject-with icmp-host-prohibited` e inserir as regras
**nessa posição** (ficam antes do REJECT):

```bash
sudo iptables -I INPUT N -p tcp --dport 80 -m state --state NEW -j ACCEPT
```

```bash
sudo iptables -I INPUT N -p tcp --dport 443 -m state --state NEW -j ACCEPT
```

```bash
sudo netfilter-persistent save
```

Conferir de fora (do seu computador), já com o Nginx no ar: `curl -I http://IP`.

## 4. Dependências e app

Seguir o passo 2 do guia da Hostinger **sem a parte de `ufw`** (e criando o usuário `leilao` a
partir do `ubuntu`, copiando `/home/ubuntu/.ssh/authorized_keys`). O Python 3.11 vem do PPA
deadsnakes, que tem pacote arm64. Depois, passos 3, 4 e o drop-in
[`deploy/systemd/leilao-ce-baseurl.conf`](../../../deploy/systemd/leilao-ce-baseurl.conf) em
`/etc/systemd/system/leilao-ce.service.d/baseurl.conf`.

ARM: todas as dependências de `requirements-web.txt` (streamlit e pyarrow, supabase e
pydantic-core, stripe) têm wheel `aarch64`. O `pip install` roda na própria VM, então não há nada
a fazer além de instalar normalmente.

```bash
curl 127.0.0.1:8501/app/_stcore/health   # deve responder ok
```

Landing: `sudo mkdir -p /var/www/achadin && sudo rsync -a --chmod=D755,F644 ~/leilao-ce/site/ /var/www/achadin/`.
Com a pasta criada, o `deploy.yml` passa a publicar a landing a cada deploy.

## 5. DNS e HTTPS

1. No registrador do `achadinleiloes.tech`, apontar os registros **A** do domínio e do `www` para
   o IP da instância.
2. Nginx em duas etapas, porque [`deploy/nginx/leilao-ce.conf`](../../../deploy/nginx/leilao-ce.conf)
   já referencia os certificados em `/etc/letsencrypt`:
   - primeiro um bloco HTTP simples (`listen 80; server_name achadinleiloes.tech www.achadinleiloes.tech;`)
     em `/etc/nginx/sites-available/leilao-ce`, com symlink em `sites-enabled` e sem o `default`;
   - emitir o certificado (exige a porta 80 aberta nas **duas** camadas da seção 3):

     ```bash
     sudo certbot --nginx -d achadinleiloes.tech -d www.achadinleiloes.tech
     ```

   - trocar pelo arquivo versionado e recarregar:

     ```bash
     sudo cp ~/leilao-ce/deploy/nginx/leilao-ce.conf /etc/nginx/sites-available/leilao-ce
     ```

     ```bash
     sudo nginx -t && sudo systemctl reload nginx
     ```

3. Renovação: `systemctl list-timers | grep certbot`.

Supabase e Stripe **não mudam**: o domínio é o mesmo (`APP_URL=https://achadinleiloes.tech/app`).

## 6. Deploy automático

Igual ao passo 6 do guia da Hostinger: chave dedicada, sudoers, secrets `VPS_HOST` (IP novo),
`VPS_USER` (`leilao`) e `VPS_SSH_KEY`. O [`deploy.yml`](../../../.github/workflows/deploy.yml)
roda em push no `main`, no fim de cada run bem-sucedido do scraper (`workflow_run`) e manualmente.

Validação: rodar o deploy pela aba Actions; depois rodar o scraper manualmente e confirmar que o
deploy dispara sozinho em seguida.

## 7. Backup

- **O que importa de verdade:** o `.env` do site guardado no gerenciador de senhas do dono. O
  resto se reconstrói pelo repo.
- **Backup do boot volume:** *Block Storage* → *Boot Volumes* → o volume → *Create Boot Volume
  Backup*. Depois, uma *backup policy* semanal. A cota grátis inclui **5 backups** no total:
  conferir que a política não guarda mais que isso (o excedente é cobrado no PAYG).

## Plano de saída

O que mora só na VM: `.env`, `/etc/nginx/sites-available/leilao-ce` (versionado em `deploy/`),
certificados (reemitíveis), unit e drop-in do systemd. Para sair da Oracle:

1. Contratar outra VPS (Hostinger ou Contabo, ver a pesquisa) e seguir o guia da Hostinger.
2. Trocar o registro A, reemitir o certificado e atualizar os secrets `VPS_*`.
3. Enquanto isso, o Streamlit Community Cloud (`leilaoce.streamlit.app`) segue como rollback.

[free]: https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm
