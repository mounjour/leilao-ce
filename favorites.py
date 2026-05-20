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


def toggle_favorite(user_id: str, access_token: str, lote: dict) -> bool:
    url = lote.get("url", "")
    if not url:
        return False
    favs = st.session_state.setdefault("favorites", {})
    try:
        sb = _sb()
        sb.postgrest.auth(access_token)
        if url in favs:
            sb.table("favorites").delete()\
              .eq("user_id", user_id).eq("lote_url", url).execute()
            del favs[url]
            return False
        else:
            sb.table("favorites").insert({
                "user_id": user_id,
                "lote_url": url,
                "lote_data": lote,
            }).execute()
            favs[url] = lote
            return True
    except Exception:
        return url in favs
