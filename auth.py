from supabase import create_client, Client
import streamlit as st
import os
import stripe
from dotenv import load_dotenv

load_dotenv()

def _secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")

stripe.api_key = _secret("STRIPE_SECRET_KEY")

_SUPABASE_URL  = _secret("SUPABASE_URL")
_SUPABASE_KEY  = _secret("SUPABASE_ANON_KEY")
_PRICE_ID      = _secret("STRIPE_PRICE_ID")
_PUBLISHABLE   = _secret("STRIPE_PUBLISHABLE_KEY")


def _sb() -> Client:
    return create_client(_SUPABASE_URL, _SUPABASE_KEY)


# ── session helpers ───────────────────────────────────────────────────────────

def get_user():
    return st.session_state.get("user")


def get_profile():
    return st.session_state.get("profile")


def is_subscribed() -> bool:
    profile = get_profile()
    return bool(profile and profile.get("subscription_status") == "active")


def _load_profile(user_id: str):
    try:
        res = _sb().table("profiles").select("*").eq("id", user_id).single().execute()
        st.session_state["profile"] = res.data
    except Exception:
        st.session_state["profile"] = None


# ── auth actions ──────────────────────────────────────────────────────────────

def login(email: str, password: str) -> tuple[bool, str]:
    try:
        res = _sb().auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["user"] = res.user
        st.session_state["session"] = res.session
        _load_profile(res.user.id)
        return True, ""
    except Exception as e:
        return False, str(e)


def signup(email: str, password: str) -> tuple[bool, str]:
    try:
        res = _sb().auth.sign_up({"email": email, "password": password})
        if res.user:
            st.session_state["user"] = res.user
            st.session_state["session"] = res.session
            _load_profile(res.user.id)
            return True, ""
        return False, "Erro ao criar conta"
    except Exception as e:
        return False, str(e)


def logout():
    try:
        _sb().auth.sign_out()
    except Exception:
        pass
    for k in ("user", "session", "profile"):
        st.session_state.pop(k, None)


# ── stripe checkout ───────────────────────────────────────────────────────────

def create_checkout_url(user_email: str) -> str:
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": _PRICE_ID, "quantity": 1}],
        success_url="https://leilaoce.streamlit.app/?payment=success",
        cancel_url="https://leilaoce.streamlit.app/?payment=cancel",
        metadata={"supabase_user_email": user_email},
    )
    return session.url


# ── rendered pages ────────────────────────────────────────────────────────────

def render_auth_page():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #0f1117; }
    .auth-logo { text-align:center; font-size:2rem; font-weight:800;
                 color:#fff; margin-bottom:.25rem; }
    .auth-sub  { text-align:center; color:#888; font-size:.95rem;
                 margin-bottom:1.5rem; }
    </style>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown('<div class="auth-logo">🚗 LeilãoCE</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-sub">Monitoramento inteligente de leilões no Ceará</div>',
                    unsafe_allow_html=True)
        st.divider()

        tab_in, tab_up = st.tabs(["Entrar", "Criar conta"])

        with tab_in:
            with st.form("login_form"):
                email    = st.text_input("E-mail", placeholder="seu@email.com")
                password = st.text_input("Senha", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")

            if submitted:
                if not email or not password:
                    st.error("Preencha todos os campos")
                else:
                    with st.spinner("Autenticando…"):
                        ok, err = login(email, password)
                    if ok:
                        st.rerun()
                    else:
                        if "Invalid login credentials" in err:
                            st.error("E-mail ou senha incorretos")
                        elif "Email not confirmed" in err:
                            st.warning("Confirme seu e-mail antes de entrar (verifique a caixa de entrada)")
                        else:
                            st.error(f"Erro: {err}")

        with tab_up:
            with st.form("signup_form"):
                s_email   = st.text_input("E-mail", placeholder="seu@email.com",  key="su_email")
                s_pass    = st.text_input("Senha", type="password",
                                          placeholder="Mínimo 6 caracteres", key="su_pass")
                s_confirm = st.text_input("Confirmar senha", type="password",
                                          placeholder="••••••••", key="su_conf")
                submitted2 = st.form_submit_button("Criar conta", use_container_width=True, type="primary")

            if submitted2:
                if not s_email or not s_pass or not s_confirm:
                    st.error("Preencha todos os campos")
                elif s_pass != s_confirm:
                    st.error("As senhas não conferem")
                elif len(s_pass) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres")
                else:
                    with st.spinner("Criando conta…"):
                        ok, err = signup(s_email, s_pass)
                    if ok:
                        st.success("Conta criada! Verifique seu e-mail para confirmar o cadastro.")
                        st.rerun()
                    else:
                        if "already registered" in err:
                            st.error("Este e-mail já está cadastrado")
                        else:
                            st.error(f"Erro: {err}")


def render_paywall():
    _, col, _ = st.columns([1, 1.8, 1])
    with col:
        st.markdown("""
        <style>
        .paywall-box { background:#1a1d27; border:1px solid #2d3149;
                       border-radius:12px; padding:2rem; text-align:center; margin-top:2rem; }
        .paywall-price { font-size:2.5rem; font-weight:800; color:#4ade80; }
        .paywall-period { color:#888; font-size:.9rem; }
        .paywall-feature { display:flex; align-items:center; gap:.5rem;
                           color:#ccc; margin:.4rem 0; }
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
        """, unsafe_allow_html=True)

        st.divider()

        user = get_user()
        if user:
            try:
                checkout_url = create_checkout_url(user.email)
                st.link_button("Assinar agora — R$47/mês",
                               checkout_url,
                               use_container_width=True,
                               type="primary")
            except Exception as e:
                st.error(f"Erro ao gerar link de pagamento: {e}")

        st.markdown("")
        if st.button("Sair", use_container_width=True):
            logout()
            st.rerun()
