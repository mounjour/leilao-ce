from supabase import create_client
import streamlit as st
import os


def _secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")


def _sb():
    return create_client(_secret("SUPABASE_URL"), _secret("SUPABASE_ANON_KEY"))


def load_favorites(user_id: str, access_token: str) -> None:
    try:
        sb = _sb()
        sb.postgrest.auth(access_token)
        res = sb.table("favorites").select("*").eq("user_id", user_id).execute()
        st.session_state["favorites"] = {
            row["lote_url"]: row["lote_data"]
            for row in (res.data or [])
        }
    except Exception:
        st.session_state.setdefault("favorites", {})


def get_favorites() -> dict:
    return st.session_state.get("favorites", {})


def is_favorite(lote_url: str) -> bool:
    return lote_url in st.session_state.get("favorites", {})


def _whatsapp_favorito(phone: str, lote: dict) -> None:
    import requests as _req
    import os as _os
    try:
        import streamlit as _st
        _secrets = _st.secrets
    except Exception:
        _secrets = {}
    def _s(k):
        try:
            return _secrets.get(k, "") or _os.getenv(k, "")
        except Exception:
            return _os.getenv(k, "")
    ev_url  = _s("EVOLUTION_API_URL").rstrip("/")
    ev_key  = _s("EVOLUTION_API_KEY")
    ev_inst = _s("EVOLUTION_INSTANCE")
    if not (ev_url and ev_key and ev_inst and phone):
        return
    digits = "".join(c for c in phone if c.isdigit())
    if not digits.startswith("55"):
        digits = "55" + digits
    if len(digits) < 12:
        return
    marca  = lote.get("marca", "")
    modelo = lote.get("modelo", "")
    ano    = lote.get("ano", "")
    lance  = float(lote.get("lance_atual", 0) or 0)
    url_lote = lote.get("url", "")
    msg = (
        f"⭐ *Lote favoritado no LeilãoCE!*\n\n"
        f"*{marca} {modelo} {ano}*\n"
        f"💰 Lance atual: R$ {lance:,.0f}\n\n"
        f"Você receberá alertas quando o lance mudar.\n"
        f"🔗 {url_lote}"
    )
    try:
        _req.post(
            f"{ev_url}/message/sendText/{ev_inst}",
            json={"number": digits, "text": msg},
            headers={"apikey": ev_key, "Content-Type": "application/json"},
            timeout=8,
        )
    except Exception:
        pass


def toggle_favorite(user_id: str, access_token: str, lote: dict, phone: str = "") -> bool:
    url = lote.get("url", "")
    if not url:
        return False
    favs = st.session_state.setdefault("favorites", {})
    removing = url in favs

    # Atualiza estado local imediatamente (não depende do Supabase)
    if removing:
        del favs[url]
    else:
        favs[url] = lote
        _whatsapp_favorito(phone, lote)

    # Sincroniza com Supabase em segundo plano (falha silenciosa)
    try:
        sb = _sb()
        sb.postgrest.auth(access_token)
        if removing:
            sb.table("favorites").delete()\
              .eq("user_id", user_id).eq("lote_url", url).execute()
        else:
            sb.table("favorites").insert({
                "user_id": user_id,
                "lote_url": url,
                "lote_data": lote,
            }).execute()
    except Exception:
        pass

    return not removing
