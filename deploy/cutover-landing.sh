#!/usr/bin/env bash
# Cutover da landing: / vira o site estatico e o Streamlit passa a /app/.
# Roda NA VPS, dentro do clone do repo (ex.: ~/leilao-ce), como root ou como um
# usuario com sudo. Guia completo: docs/contexto/setup/CUTOVER_LANDING.md
#
#   ./deploy/cutover-landing.sh aplicar [--yes]   faz o cutover (com rollback automatico se algo falhar)
#   ./deploy/cutover-landing.sh rollback          volta ao estado anterior (ultimo backup)
#   ./deploy/cutover-landing.sh status            mostra o estado atual
# -E: o trap de ERR (rollback automatico) tambem vale dentro das funcoes.
set -Eeuo pipefail

# Caminhos sobrescrevíveis por variavel de ambiente (usado so nos testes de simulacao).
DOMINIO="${DOMINIO:-achadinleiloes.tech}"
WEBROOT="${WEBROOT:-/var/www/achadin}"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/sites-available/leilao-ce}"
NGINX_ENABLED="${NGINX_ENABLED:-/etc/nginx/sites-enabled/leilao-ce}"
LETSENCRYPT="${LETSENCRYPT:-/etc/letsencrypt}"
DROPIN_DIR="${DROPIN_DIR:-/etc/systemd/system/leilao-ce.service.d}"
DROPIN="$DROPIN_DIR/baseurl.conf"
SERVICO="${SERVICO:-leilao-ce}"
APP_URL_NOVA="https://$DOMINIO/app"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO/.env"
DONO="$(stat -c %U "$REPO")"
BACKUP_RAIZ="${BACKUP_RAIZ:-$(getent passwd "$DONO" | cut -d: -f6)/backup-cutover}"

if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

# Comandos que mexem no repo rodam como dono do clone (evita arquivos de root
# no repo, que quebrariam o `git reset` do deploy automatico).
como_dono() {
    if [ "$(id -u)" -eq 0 ] && [ "$DONO" != "root" ]; then runuser -u "$DONO" -- "$@"; else "$@"; fi
}

log()  { printf '\n==> %s\n' "$*"; }
erro() { printf 'ERRO: %s\n' "$*" >&2; }

checar() {  # checar "descricao" comando...
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then printf '  ok   %s\n' "$desc"; else printf '  FALHOU %s\n' "$desc"; return 1; fi
}

# ── verificacoes pos-cutover (usadas por `aplicar` e `status`) ─────────────
verificar_novo() {
    local falhas=0 resp
    log "Verificando o estado novo"
    [ "$(curl -fsS -m 10 "https://$DOMINIO/app/_stcore/health" || true)" = "ok" ] \
        && echo "  ok   /app/_stcore/health = ok" || { echo "  FALHOU /app/_stcore/health"; falhas=1; }
    resp="$(curl -fsS --http1.1 -m 10 "https://$DOMINIO/" || true)"
    grep -q 'id="conteudo"' <<<"$resp" \
        && echo "  ok   / serve a landing" || { echo "  FALHOU / nao e a landing"; falhas=1; }
    resp="$(curl -s -m 10 -o /dev/null -w '%{http_code} %{redirect_url}' "https://$DOMINIO/?mode=confirmed" || true)"
    [ "$resp" = "302 https://$DOMINIO/app/?mode=confirmed" ] \
        && echo "  ok   /?mode=confirmed -> /app/?mode=confirmed" || { echo "  FALHOU redirect de legado (veio: $resp)"; falhas=1; }
    [ "$(curl -s -m 10 -o /dev/null -w '%{http_code}' "https://$DOMINIO/app/")" = "200" ] \
        && echo "  ok   /app/ = 200" || { echo "  FALHOU /app/"; falhas=1; }
    resp="$(curl -fsS --http1.1 -m 10 "https://$DOMINIO/robots.txt" || true)"
    grep -q 'Disallow: /app/' <<<"$resp" \
        && echo "  ok   robots.txt" || { echo "  FALHOU robots.txt"; falhas=1; }
    # WebSocket do Streamlit atravessa o proxy? (espera 101 Switching Protocols)
    resp="$(curl -s --http1.1 -m 4 -i -N -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
        -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
        -H "Origin: https://$DOMINIO" "https://$DOMINIO/app/_stcore/stream" 2>/dev/null | head -1 || true)"
    case "$resp" in *101*) echo "  ok   WebSocket (101)";; *) echo "  FALHOU WebSocket (veio: ${resp:-vazio})"; falhas=1;; esac
    return $falhas
}

verificar_antigo() {
    log "Verificando o estado antigo"
    [ "$(curl -fsS -m 10 "https://$DOMINIO/_stcore/health" || true)" = "ok" ] \
        && echo "  ok   /_stcore/health = ok" || { echo "  FALHOU /_stcore/health"; return 1; }
}

setar_app_url() {
    local url="$1"
    if grep -q '^APP_URL=' "$ENV_FILE"; then
        como_dono sed -i "s#^APP_URL=.*#APP_URL=$url#" "$ENV_FILE"
    else
        echo "APP_URL=$url" | como_dono tee -a "$ENV_FILE" >/dev/null
    fi
}

# ── rollback ───────────────────────────────────────────────────────────────
rollback() {
    local ts="${1:-}"
    [ -z "$ts" ] && ts="$(cat "$BACKUP_RAIZ/ULTIMO" 2>/dev/null || true)"
    [ -n "$ts" ] && [ -d "$BACKUP_RAIZ/$ts" ] || { erro "sem backup para restaurar em $BACKUP_RAIZ"; exit 1; }
    local b="$BACKUP_RAIZ/$ts"
    log "Rollback a partir de $b"
    $SUDO cp -a "$b/leilao-ce.nginx" "$NGINX_CONF"
    $SUDO rm -f "$DROPIN"
    $SUDO rmdir "$DROPIN_DIR" 2>/dev/null || true
    como_dono cp -a "$b/.env" "$ENV_FILE"
    $SUDO systemctl daemon-reload
    $SUDO nginx -t
    $SUDO systemctl reload nginx
    $SUDO systemctl restart "$SERVICO"
    sleep 6
    verificar_antigo && echo "Rollback concluido." || { erro "rollback aplicado, mas o health antigo nao respondeu: veja journalctl -u $SERVICO"; exit 1; }
}

# ── aplicar ────────────────────────────────────────────────────────────────
aplicar() {
    local sim="${1:-}"
    log "Pre-requisitos"
    local ok=0
    checar "site/index.html no repo"            test -f "$REPO/site/index.html" || ok=1
    checar "deploy/nginx/leilao-ce.conf no repo" test -f "$REPO/deploy/nginx/leilao-ce.conf" || ok=1
    checar "Nginx instalado"                     command -v nginx || ok=1
    checar "arquivo do Nginx existe ($NGINX_CONF)" $SUDO test -f "$NGINX_CONF" || ok=1
    checar "Nginx ativa o arquivo (sites-enabled)" $SUDO test -e "$NGINX_ENABLED" || ok=1
    checar "certificado de $DOMINIO"             $SUDO test -f "$LETSENCRYPT/live/$DOMINIO/fullchain.pem" || ok=1
    checar "options-ssl-nginx.conf do Certbot"   $SUDO test -f "$LETSENCRYPT/options-ssl-nginx.conf" || ok=1
    checar "ssl-dhparams.pem do Certbot"         $SUDO test -f "$LETSENCRYPT/ssl-dhparams.pem" || ok=1
    checar ".venv do repo"                       test -x "$REPO/.venv/bin/python" || ok=1
    checar ".env do repo"                        test -f "$ENV_FILE" || ok=1
    checar "curl e rsync"                        bash -c 'command -v curl && command -v rsync' || ok=1
    [ "$ok" -eq 0 ] || { erro "pre-requisitos nao atendidos; nada foi alterado."; exit 1; }
    if [ -f "$DROPIN" ]; then erro "cutover ja aplicado ($DROPIN existe). Use 'status' ou 'rollback'."; exit 1; fi

    log "server_name no arquivo atual do Nginx (o novo so atende $DOMINIO)"
    $SUDO grep -n 'server_name' "$NGINX_CONF" || true

    log "Diff do Nginx (atual -> novo)"
    $SUDO diff -u "$NGINX_CONF" "$REPO/deploy/nginx/leilao-ce.conf" || true
    echo
    echo "APP_URL atual: $(grep '^APP_URL=' "$ENV_FILE" || echo '(ausente)')  ->  APP_URL=$APP_URL_NOVA"
    if [ "$sim" != "--yes" ]; then
        echo
        echo "ANTES de continuar: o Supabase (Authentication > URL Configuration) ja tem"
        echo "  https://$DOMINIO/app  e  https://$DOMINIO/app/**  nos Redirect URLs?"
        read -r -p "Digite 'sim' para aplicar: " resp
        [ "$resp" = "sim" ] || { echo "Cancelado."; exit 1; }
    fi

    local ts; ts="$(date +%Y%m%d-%H%M%S)"
    log "Backup em $BACKUP_RAIZ/$ts"
    como_dono mkdir -p "$BACKUP_RAIZ/$ts"
    $SUDO cp -a "$NGINX_CONF" "$BACKUP_RAIZ/$ts/leilao-ce.nginx"
    como_dono cp -a "$ENV_FILE" "$BACKUP_RAIZ/$ts/.env"
    echo "$ts" | como_dono tee "$BACKUP_RAIZ/ULTIMO" >/dev/null

    # Daqui pra frente, qualquer falha dispara o rollback.
    trap 'erro "falha durante o cutover — revertendo"; trap - ERR; rollback "'"$ts"'"; exit 1' ERR

    log "Publicando o site em $WEBROOT"
    $SUDO mkdir -p "$WEBROOT"
    $SUDO chown "$DONO:" "$WEBROOT"
    ( cd "$REPO" && como_dono .venv/bin/python scripts/gerar_stats_site.py )
    como_dono rsync -a --delete --chmod=D755,F644 "$REPO/site/" "$WEBROOT/"

    log "Instalando Nginx e drop-in do systemd"
    $SUDO install -m 644 "$REPO/deploy/nginx/leilao-ce.conf" "$NGINX_CONF"
    $SUDO nginx -t
    $SUDO mkdir -p "$DROPIN_DIR"
    $SUDO install -m 644 "$REPO/deploy/systemd/leilao-ce-baseurl.conf" "$DROPIN"
    setar_app_url "$APP_URL_NOVA"
    $SUDO systemctl daemon-reload

    log "Recarregando Nginx e reiniciando o Streamlit"
    $SUDO systemctl reload nginx
    $SUDO systemctl restart "$SERVICO"
    local i
    for i in $(seq 1 30); do
        [ "$(curl -fsS -m 3 http://127.0.0.1:8501/app/_stcore/health 2>/dev/null || true)" = "ok" ] && break
        sleep 1
    done

    verificar_novo
    trap - ERR
    log "Cutover concluido. Backup: $BACKUP_RAIZ/$ts (rollback: $0 rollback)"
    echo "Falta (manual): Supabase Site URL -> https://$DOMINIO/app e o teste ponta a ponta do guia."
}

status() {
    echo "Drop-in /app:   $($SUDO test -f "$DROPIN" && echo presente || echo ausente)"
    echo "APP_URL:        $(grep '^APP_URL=' "$ENV_FILE" || echo '(ausente)')"
    echo "Webroot:        $(test -f "$WEBROOT/index.html" && echo publicado || echo vazio)"
    echo "Ultimo backup:  $(cat "$BACKUP_RAIZ/ULTIMO" 2>/dev/null || echo nenhum)"
    if $SUDO test -f "$DROPIN"; then verificar_novo; else verificar_antigo; fi
}

case "${1:-}" in
    aplicar)  aplicar "${2:-}" ;;
    rollback) rollback "${2:-}" ;;
    status)   status ;;
    *) echo "uso: $0 {aplicar [--yes] | rollback [timestamp] | status}"; exit 2 ;;
esac
