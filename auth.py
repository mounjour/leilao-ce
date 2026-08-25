from __future__ import annotations

import os

import streamlit as st
import stripe
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions


load_dotenv()


def _secret(key: str, default: str = "") -> str:
    try:
        value = st.secrets[key]
    except Exception:
        value = os.getenv(key, default)
    return str(value).strip() if value is not None else default


_SUPABASE_URL = _secret("SUPABASE_URL")
_SUPABASE_KEY = _secret("SUPABASE_ANON_KEY")
_PRICE_ID = _secret("STRIPE_PRICE_ID")
_PUBLISHABLE = _secret("STRIPE_PUBLISHABLE_KEY")
_APP_URL = _secret("APP_URL", "https://leilaoce.streamlit.app").rstrip("/")

stripe.api_key = _secret("STRIPE_SECRET_KEY")


def _validate_supabase_config() -> None:
    missing = []
    if not _SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not _SUPABASE_KEY:
        missing.append("SUPABASE_ANON_KEY")
    if missing:
        raise RuntimeError(f"Configuração ausente: {', '.join(missing)}")


def _sb() -> Client:
    """Retorna um cliente por sessão do Streamlit.

    Reutilizar o cliente é importante porque o fluxo PKCE guarda temporariamente
    o verificador usado para trocar o código do link por uma sessão.
    """
    _validate_supabase_config()
    if "_supabase_client" not in st.session_state:
        options = ClientOptions(flow_type="pkce")
        st.session_state["_supabase_client"] = create_client(
            _SUPABASE_URL,
            _SUPABASE_KEY,
            options=options,
        )
    return st.session_state["_supabase_client"]


def get_supabase_client() -> Client:
    """Expõe o cliente da sessão para módulos autenticados, como favoritos."""
    return _sb()


# ── Session helpers ──────────────────────────────────────────────────────────

def get_user():
    return st.session_state.get("user")


def get_profile():
    return st.session_state.get("profile")


def is_subscribed() -> bool:
    profile = get_profile()
    return bool(profile and profile.get("subscription_status") == "active")


def _save_auth(auth_response) -> bool:
    user = getattr(auth_response, "user", None)
    session = getattr(auth_response, "session", None)
    if not user or not session:
        return False

    usuario_anterior = st.session_state.get("_auth_user_id")
    if usuario_anterior and usuario_anterior != user.id:
        st.session_state.pop("favorites", None)
        st.session_state.pop("_favorites_owner", None)

    st.session_state["user"] = user
    st.session_state["session"] = session
    st.session_state["_auth_user_id"] = user.id
    _load_profile(user.id, session)
    return True


def _load_profile(user_id: str, session=None) -> None:
    try:
        sb = _sb()
        if session:
            sb.auth.set_session(session.access_token, session.refresh_token)
        response = (
            sb.table("profiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        st.session_state["profile"] = response.data
    except Exception:
        st.session_state["profile"] = None


def _clear_local_auth() -> None:
    for key in (
        "user",
        "session",
        "profile",
        "_password_recovery",
        "_auth_callback_processed",
        "_show_forgot",
        "_auth_user_id",
        "_favorites_owner",
        "_favorites_error",
        "favorites",
        "_supabase_client",
    ):
        st.session_state.pop(key, None)


# ── Auth actions ─────────────────────────────────────────────────────────────

def login(email: str, password: str) -> tuple[bool, str]:
    try:
        response = _sb().auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
        if not _save_auth(response):
            return False, "Não foi possível criar a sessão de acesso."
        return True, ""
    except Exception as exc:
        return False, str(exc)


def signup(email: str, password: str, phone: str = "") -> tuple[bool, str]:
    try:
        credentials = {
            "email": email.strip(),
            "password": password,
            "options": {
                "email_redirect_to": f"{_APP_URL}/?mode=confirmed",
                "data": {"phone": phone.strip()},
            },
        }
        response = _sb().auth.sign_up(credentials)

        if not response.user:
            return False, "Erro ao criar conta."

        # Com confirmação de e-mail habilitada, o Supabase retorna usuário,
        # mas não retorna sessão. Nesse caso, não liberamos o aplicativo.
        if not response.session:
            return True, "CONFIRM_EMAIL"

        if not _save_auth(response):
            return False, "Conta criada, mas não foi possível iniciar a sessão."
        return True, "SIGNED_IN"
    except Exception as exc:
        return False, str(exc)


def logout() -> None:
    try:
        _sb().auth.sign_out()
    except Exception:
        pass
    _clear_local_auth()


def reset_password(email: str) -> tuple[bool, str]:
    try:
        _sb().auth.reset_password_for_email(
            email.strip(),
            {"redirect_to": f"{_APP_URL}/?mode=recovery"},
        )
        return True, ""
    except Exception as exc:
        return False, str(exc)


def update_password(new_password: str) -> tuple[bool, str]:
    try:
        response = _sb().auth.update_user({"password": new_password})
        if not getattr(response, "user", None):
            return False, "Não foi possível atualizar a senha."
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _process_auth_callback() -> tuple[bool, str]:
    """Troca o código PKCE recebido do Supabase por uma sessão autenticada."""
    code = st.query_params.get("code")
    mode = st.query_params.get("mode", "")

    if not code or st.session_state.get("_auth_callback_processed") == code:
        return True, ""

    try:
        response = _sb().auth.exchange_code_for_session({"auth_code": code})
        if not _save_auth(response):
            return False, "O link não gerou uma sessão válida."

        st.session_state["_auth_callback_processed"] = code
        if mode == "recovery":
            st.session_state["_password_recovery"] = True

        st.query_params.clear()
        return True, ""
    except Exception as exc:
        return False, str(exc)


# ── Stripe checkout ──────────────────────────────────────────────────────────

def create_checkout_url(user_email: str) -> str:
    missing = []
    if not stripe.api_key:
        missing.append("STRIPE_SECRET_KEY")
    if not _PRICE_ID:
        missing.append("STRIPE_PRICE_ID")
    if missing:
        raise RuntimeError(f"Configuração ausente: {', '.join(missing)}")

    checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": _PRICE_ID, "quantity": 1}],
        success_url=f"{_APP_URL}/?payment=success",
        cancel_url=f"{_APP_URL}/?payment=cancel",
        metadata={"supabase_user_email": user_email},
    )
    return checkout.url


# ── Rendered pages ───────────────────────────────────────────────────────────

_AUTH_CSS = """
<style>
[data-testid="stAppViewContainer"] { background: #ffffff !important; }
[data-testid="stHeader"], [data-testid="stToolbar"],
#stDecoration, footer { display: none !important; }

.stTextInput label {
    color: #374151 !important; font-size: .85rem !important;
    font-weight: 500 !important;
}
.stTextInput input {
    background: #f9fafb !important; color: #111827 !important;
    border: 1.5px solid #e5e7eb !important; border-radius: 8px !important;
    font-size: .95rem !important;
}
.stTextInput input::placeholder { color: #9ca3af !important; }
.stTextInput input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,.1) !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1.5px solid #e5e7eb !important;
}
.stTabs [data-baseweb="tab"] {
    color: #9ca3af !important; font-size: .9rem !important;
    font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    color: #111827 !important; font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-border"] {
    background: #2563eb !important; height: 2px !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.5rem !important; }
.stFormSubmitButton button {
    background: #2563eb !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: .95rem !important;
    height: 44px !important;
}
.stFormSubmitButton button:hover { background: #1d4ed8 !important; }
div[data-testid="stButton"] button {
    background: transparent !important; color: #2563eb !important;
    border: none !important; padding: 0 !important;
    font-size: .83rem !important; font-weight: 500 !important;
    box-shadow: none !important;
}
div[data-testid="stButton"] button:hover { color: #1d4ed8 !important; }
hr { border-color: #f3f4f6 !important; }
</style>
"""


def _render_brand() -> None:
    st.markdown(
        """
        <div style="text-align:center;padding:2.5rem 0 1.5rem;">
          <div style="font-size:2rem;font-weight:800;color:#111827;margin-bottom:.25rem;">
            🚗 LeilãoCE
          </div>
          <div style="color:#6b7280;font-size:.9rem;">
            Monitoramento inteligente de leilões no Ceará
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_password_update() -> None:
    st.markdown("### Definir nova senha")
    st.caption("Digite e confirme a nova senha da sua conta.")

    with st.form("update_password_form"):
        password = st.text_input(
            "Nova senha", type="password", placeholder="Mínimo 6 caracteres"
        )
        confirmation = st.text_input(
            "Confirmar nova senha", type="password", placeholder="Repita a senha"
        )
        submitted = st.form_submit_button(
            "Atualizar senha", use_container_width=True, type="primary"
        )

    if submitted:
        if len(password) < 6:
            st.error("A senha deve ter pelo menos 6 caracteres.")
        elif password != confirmation:
            st.error("As senhas não conferem.")
        else:
            ok, error = update_password(password)
            if ok:
                st.success("Senha atualizada. Entre novamente com a nova senha.")
                logout()
                st.session_state["_password_updated"] = True
                st.rerun()
            else:
                st.error(f"Não foi possível atualizar a senha: {error}")


def render_auth_page() -> None:
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)

    callback_ok, callback_error = _process_auth_callback()
    _, column, _ = st.columns([1, 1.2, 1])

    with column:
        _render_brand()

        if not callback_ok:
            st.error(
                "O link de autenticação é inválido, expirou ou já foi utilizado. "
                f"Detalhes: {callback_error}"
            )
            if st.button("Voltar ao login", use_container_width=True):
                st.query_params.clear()
                st.session_state.pop("_password_recovery", None)
                st.rerun()
            return

        if st.session_state.get("_password_recovery"):
            _render_password_update()
            return

        if st.session_state.pop("_password_updated", False):
            st.success("Senha atualizada. Faça login com a nova senha.")

        if st.query_params.get("mode") == "confirmed":
            st.success("E-mail confirmado. Você já pode entrar.")
            st.query_params.clear()

        forgot = st.session_state.get("_show_forgot", False)

        if forgot:
            st.markdown("### Recuperar senha")
            st.caption("Enviaremos um link para você definir uma nova senha.")
            with st.form("forgot_form"):
                email = st.text_input(
                    "E-mail", placeholder="seu@email.com", key="forgot_email"
                )
                submitted = st.form_submit_button(
                    "Enviar link", use_container_width=True, type="primary"
                )

            if submitted:
                if not email.strip():
                    st.error("Digite seu e-mail.")
                else:
                    ok, error = reset_password(email)
                    if ok:
                        st.success("Link enviado. Verifique também a pasta de spam.")
                    else:
                        st.error(f"Não foi possível enviar o link: {error}")

            if st.button("← Voltar ao login"):
                st.session_state["_show_forgot"] = False
                st.rerun()
            return

        tab_login, tab_signup = st.tabs(["Entrar", "Criar conta"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="seu@email.com")
                password = st.text_input(
                    "Senha", type="password", placeholder="••••••••"
                )
                submitted = st.form_submit_button(
                    "Entrar", use_container_width=True, type="primary"
                )

            if submitted:
                if not email.strip() or not password:
                    st.error("Preencha todos os campos.")
                else:
                    with st.spinner("Autenticando…"):
                        ok, error = login(email, password)
                    if ok:
                        st.rerun()
                    elif "Invalid login credentials" in error:
                        st.error("E-mail ou senha incorretos.")
                    elif "Email not confirmed" in error:
                        st.warning("Confirme seu e-mail antes de entrar.")
                    else:
                        st.error(f"Erro ao entrar: {error}")

            if st.button(
                "Esqueci minha senha",
                key="btn_forgot",
                use_container_width=True,
            ):
                st.session_state["_show_forgot"] = True
                st.rerun()

        with tab_signup:
            with st.form("signup_form"):
                email = st.text_input(
                    "Email", placeholder="seu@email.com", key="signup_email"
                )
                phone = st.text_input(
                    "WhatsApp", placeholder="(85) 99999-9999", key="signup_phone"
                )
                password = st.text_input(
                    "Senha",
                    type="password",
                    placeholder="Mínimo 6 caracteres",
                    key="signup_password",
                )
                confirmation = st.text_input(
                    "Confirmar senha",
                    type="password",
                    placeholder="Repita a senha",
                    key="signup_confirmation",
                )
                submitted = st.form_submit_button(
                    "Criar conta", use_container_width=True, type="primary"
                )

            if submitted:
                if not email.strip() or not password or not confirmation:
                    st.error("Preencha todos os campos obrigatórios.")
                elif password != confirmation:
                    st.error("As senhas não conferem.")
                elif len(password) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                else:
                    with st.spinner("Criando conta…"):
                        ok, status = signup(email, password, phone)

                    if ok and status == "CONFIRM_EMAIL":
                        st.success(
                            "Conta criada. Confirme o e-mail antes de entrar. "
                            "Verifique também a pasta de spam."
                        )
                    elif ok:
                        st.rerun()
                    elif "already registered" in status.lower():
                        st.error("Este e-mail já está cadastrado.")
                    else:
                        st.error(f"Erro ao criar conta: {status}")


def render_paywall() -> None:
    _, column, _ = st.columns([1, 1.8, 1])
    with column:
        st.markdown(
            """
            <style>
            .paywall-box {
                background:#1a1d27; border:1px solid #2d3149;
                border-radius:12px; padding:2rem; text-align:center;
                margin-top:2rem;
            }
            .paywall-price { font-size:2.5rem; font-weight:800; color:#4ade80; }
            .paywall-period { color:#888; font-size:.9rem; }
            .paywall-feature {
                display:flex; align-items:center; gap:.5rem;
                color:#ccc; margin:.4rem 0;
            }
            </style>
            <div class="paywall-box">
              <p style="font-size:1.2rem;font-weight:700;color:#fff;margin-bottom:.5rem">
                Acesso completo ao LeilãoCE
              </p>
              <div class="paywall-price">R$&nbsp;47</div>
              <div class="paywall-period">por mês · cancele quando quiser</div>
              <hr style="border-color:#2d3149;margin:1.25rem 0">
              <div class="paywall-feature">✅ Todos os leilões do Ceará em tempo real</div>
              <div class="paywall-feature">✅ Análise de oportunidade com IA</div>
              <div class="paywall-feature">✅ Comparação com tabela FIPE</div>
              <div class="paywall-feature">✅ Filtros por cidade, categoria e preço</div>
              <div class="paywall-feature">✅ Atualizado 2× por dia automaticamente</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        user = get_user()
        if user:
            try:
                checkout_url = create_checkout_url(user.email)
                st.link_button(
                    "Assinar agora — R$47/mês",
                    checkout_url,
                    use_container_width=True,
                    type="primary",
                )
            except Exception as exc:
                st.error(f"Erro ao gerar link de pagamento: {exc}")

        if st.button("Sair", use_container_width=True):
            logout()
            st.rerun()

