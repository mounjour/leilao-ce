from __future__ import annotations

import os
import re
from urllib.parse import urlsplit, urlunsplit

import requests
import streamlit as st

from auth import get_supabase_client
from whatsapp_log import registrar_falha


def _secret(key: str, default: str = "") -> str:
    try:
        value = st.secrets[key]
    except Exception:
        value = os.getenv(key, default)
    return str(value).strip() if value is not None else default


# Pacto e Leilo são a mesma plataforma e dão o mesmo uuid ao mesmo lote
# (ver scraper._uuid_lote_plataforma). O favorito é chaveado pelo uuid, na
# forma canônica do Pacto, para sobreviver a troca de domínio ou de formato.
_UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_LOTE_PLATAFORMA_RE = re.compile(
    rf"^https?://(?:www\.)?(?:pactoleiloes|leilo)\.com\.br/lote/({_UUID_RE})(?:[/?#]|$)",
    re.IGNORECASE,
)
_HOSTS_PLATAFORMA = (
    "www.pactoleiloes.com.br",
    "pactoleiloes.com.br",
    "leilo.com.br",
    "www.leilo.com.br",
)


def _uuid_plataforma(url: str) -> str | None:
    m = _LOTE_PLATAFORMA_RE.match(str(url or "").strip())
    return m.group(1).lower() if m else None


def _urls_equivalentes(url: str) -> list[str]:
    """Todas as chaves com que este lote pode estar gravado no banco.

    Favoritos antigos ficaram com a URL do Leilo (ou do Pacto sem o `www`); ao
    remover, todas precisam sair, senão o lote volta a aparecer no próximo login.
    """
    uuid = _uuid_plataforma(url)
    if not uuid:
        return [_normalizar_url(url)]
    return [f"https://{host}/lote/{uuid}" for host in _HOSTS_PLATAFORMA]


def _normalizar_url(url: str) -> str:
    """Evita duplicidade causada por parâmetros de rastreamento ou fragmentos.

    Lotes da plataforma Pacto/Leilo viram sempre a URL canônica do Pacto."""
    uuid = _uuid_plataforma(url)
    if uuid:
        return f"https://www.pactoleiloes.com.br/lote/{uuid}"
    try:
        partes = urlsplit(str(url or "").strip())
        caminho = partes.path.rstrip("/") or "/"
        return urlunsplit((partes.scheme.lower(), partes.netloc.lower(), caminho, "", ""))
    except Exception:
        return str(url or "").strip().rstrip("/")


def _cliente_autenticado(access_token: str):
    if not access_token:
        raise RuntimeError("Sessão expirada. Entre novamente.")
    sb = get_supabase_client()
    sb.postgrest.auth(access_token)
    return sb


def load_favorites(user_id: str, access_token: str) -> tuple[bool, str]:
    """Carrega apenas os favoritos que pertencem ao usuário autenticado."""
    try:
        sb = _cliente_autenticado(access_token)
        resposta = (
            sb.table("favorites")
            .select("lote_url,lote_data")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        favoritos = {}
        for row in resposta.data or []:
            dados = row.get("lote_data")
            url = _normalizar_url(row.get("lote_url", ""))
            if url and isinstance(dados, dict):
                favoritos[url] = dados

        st.session_state["favorites"] = favoritos
        st.session_state["_favorites_owner"] = user_id
        st.session_state.pop("_favorites_error", None)
        return True, ""
    except Exception as exc:
        st.session_state["favorites"] = {}
        st.session_state["_favorites_owner"] = user_id
        st.session_state["_favorites_error"] = str(exc)
        return False, "Não foi possível carregar seus favoritos."


def get_favorites() -> dict:
    return st.session_state.get("favorites", {})


def is_favorite(lote_url: str) -> bool:
    return _normalizar_url(lote_url) in get_favorites()


def _whatsapp_favorito(sb, user_id: str, phone: str, lote: dict) -> None:
    ev_url = _secret("EVOLUTION_API_URL").rstrip("/")
    ev_key = _secret("EVOLUTION_API_KEY")
    ev_inst = _secret("EVOLUTION_INSTANCE")
    if not (ev_url and ev_key and ev_inst and phone):
        return

    digits = "".join(c for c in phone if c.isdigit())
    if not digits.startswith("55"):
        digits = "55" + digits
    if len(digits) < 12:
        return

    marca = lote.get("marca", "")
    modelo = lote.get("modelo", "")
    ano = lote.get("ano", "")
    lance = float(lote.get("lance_atual", 0) or 0)
    url_lote = lote.get("url", "")
    msg = (
        "⭐ *Lote favoritado no Achadin Leilões!*\n\n"
        f"*{marca} {modelo} {ano}*\n"
        f"💰 Lance atual: R$ {lance:,.0f}\n\n"
        "Você receberá alertas quando o lance mudar.\n"
        f"🔗 {url_lote}"
    )

    resposta = None
    try:
        resposta = requests.post(
            f"{ev_url}/message/sendText/{ev_inst}",
            json={"number": digits, "text": msg},
            headers={"apikey": ev_key, "Content-Type": "application/json"},
            timeout=8,
        )
        resposta.raise_for_status()
    except Exception as exc:
        # O WhatsApp é opcional e não deve desfazer um favorito já salvo, mas
        # a falha precisa deixar rastro (antes era engolida com um pass).
        registrar_falha(
            sb,
            origem="favorito",
            telefone=digits,
            lote_url=url_lote,
            erro=str(exc),
            http_status=getattr(resposta, "status_code", None),
            user_id=user_id,
            corpo=(resposta.text if resposta is not None else ""),
        )


def toggle_favorite(
    user_id: str,
    access_token: str,
    lote: dict,
    phone: str = "",
) -> tuple[bool, bool, str]:
    """Salva/remove no banco antes de alterar a interface local.

    Retorna: (operacao_ok, esta_favorito, mensagem_de_erro).
    """
    url_original = str(lote.get("url", "")).strip()
    url = _normalizar_url(url_original)
    if not user_id or not url:
        return False, False, "Este lote não possui uma URL válida."

    favoritos = st.session_state.setdefault("favorites", {})
    removendo = url in favoritos

    try:
        sb = _cliente_autenticado(access_token)
        if removendo:
            (
                sb.table("favorites")
                .delete()
                .eq("user_id", user_id)
                .in_("lote_url", _urls_equivalentes(url_original))
                .execute()
            )
            favoritos.pop(url, None)
            return True, False, ""

        dados_lote = dict(lote)
        dados_lote["url"] = url_original
        (
            sb.table("favorites")
            .upsert(
                {
                    "user_id": user_id,
                    "lote_url": url,
                    "lote_data": dados_lote,
                },
                on_conflict="user_id,lote_url",
            )
            .execute()
        )
        favoritos[url] = dados_lote
        _whatsapp_favorito(sb, user_id, phone, dados_lote)
        return True, True, ""
    except Exception as exc:
        st.session_state["_favorites_error"] = str(exc)
        return False, removendo, "Não foi possível sincronizar o favorito com o Supabase."

