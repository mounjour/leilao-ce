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


def _load_profile(user_id: str, access_token: str = None):
    try:
        sb = _sb()
        if access_token:
            sb.postgrest.auth(access_token)
        res = sb.table("profiles").select("*").eq("id", user_id).single().execute()
        st.session_state["profile"] = res.data
    except Exception:
        st.session_state["profile"] = None


# ── auth actions ──────────────────────────────────────────────────────────────

def login(email: str, password: str) -> tuple[bool, str]:
    try:
        res = _sb().auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["user"] = res.user
        st.session_state["session"] = res.session
        _load_profile(res.user.id, res.session.access_token)
        return True, ""
    except Exception as e:
        return False, str(e)


def signup(email: str, password: str) -> tuple[bool, str]:
    try:
        res = _sb().auth.sign_up({"email": email, "password": password})
        if res.user:
            st.session_state["user"] = res.user
            st.session_state["session"] = res.session
            token = res.session.access_token if res.session else None
            _load_profile(res.user.id, token)
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


def reset_password(email: str) -> tuple[bool, str]:
    try:
        _sb().auth.reset_password_email(
            email,
            options={"redirect_to": "https://leilaoce.streamlit.app"}
        )
        return True, ""
    except Exception as e:
        return False, str(e)


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

_AUTH_CSS = """
<style>
[data-testid="stAppViewContainer"] { background: #0b0f1a !important; }
[data-testid="stHeader"] { background: transparent !important; }

/* inputs */
.stTextInput label { color: #94a3b8 !important; font-size: .85rem !important;
                     font-weight: 500 !important; margin-bottom: 2px !important; }
.stTextInput input {
    background: #131929 !important; color: #f1f5f9 !important;
    border: 1px solid #1e2d45 !important; border-radius: 8px !important;
    padding: 10px 14px !important; font-size: .95rem !important;
}
.stTextInput input::placeholder { color: #3d5068 !important; }
.stTextInput input:focus { border-color: #3b82f6 !important;
                           box-shadow: 0 0 0 3px rgba(59,130,246,.15) !important; }

/* tabs */
.stTabs [data-baseweb="tab-list"] { background: transparent !important;
                                     border-bottom: 1px solid #1e2d45 !important;
                                     gap: 0 !important; }
.stTabs [data-baseweb="tab"] { color: #64748b !important; font-size: .9rem !important;
                                font-weight: 500 !important; padding: 10px 20px !important; }
.stTabs [aria-selected="true"] { color: #fff !important; }
.stTabs [data-baseweb="tab-border"] { background: #3b82f6 !important; height: 2px !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.25rem !important; }

/* primary button */
.stFormSubmitButton button, div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: #fff !important; border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: .95rem !important;
    padding: 10px !important; transition: opacity .2s !important;
}
.stFormSubmitButton button:hover { opacity: .88 !important; }

/* link button (forgot password) */
div[data-testid="stButton"] > button[kind="secondary"] {
    background: transparent !important; color: #3b82f6 !important;
    border: none !important; padding: 0 !important; font-size: .82rem !important;
    text-decoration: underline !important; cursor: pointer !important;
}

/* benefit items */
.benefit { display:flex; align-items:flex-start; gap:.6rem;
           margin-bottom:.8rem; }
.benefit-icon { font-size:1.1rem; margin-top:1px; flex-shrink:0; }
.benefit-text { color:#cbd5e1; font-size:.9rem; line-height:1.4; }
.benefit-text strong { color:#fff; }

hr { border-color: #1e2d45 !important; }

/* responsive: empilha no mobile */
@media (max-width: 768px) {
    .auth-brand-col { display: none; }
}
</style>
"""

def render_auth_page():
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)

    col_brand, col_sep, col_form = st.columns([1.1, 0.05, 1])

    with col_brand:
        st.markdown("""
        <div style="padding: 2.5rem 1rem 2rem; height:100%;">
          <div style="font-size:2.2rem; font-weight:800; color:#fff; margin-bottom:.4rem;">
            🚗 LeilãoCE
          </div>
          <div style="color:#64748b; font-size:1rem; margin-bottom:2rem;">
            Monitoramento inteligente de leilões no Ceará
          </div>

          <div class="benefit">
            <span class="benefit-icon">🔍</span>
            <span class="benefit-text"><strong>Todos os leilões do Ceará</strong><br>
            Carros, motos, imóveis e equipamentos em um só lugar</span>
          </div>
          <div class="benefit">
            <span class="benefit-icon">🤖</span>
            <span class="benefit-text"><strong>Análise com inteligência artificial</strong><br>
            Avaliação automática de cada lote com recomendação de compra</span>
          </div>
          <div class="benefit">
            <span class="benefit-icon">📊</span>
            <span class="benefit-text"><strong>Comparação com tabela FIPE</strong><br>
            Saiba exatamente quanto está economizando antes de dar o lance</span>
          </div>
          <div class="benefit">
            <span class="benefit-icon">🔔</span>
            <span class="benefit-text"><strong>Alertas de favoritos</strong><br>
            Salve lotes e receba atualizações diretamente no WhatsApp</span>
          </div>
          <div class="benefit">
            <span class="benefit-icon">⚡</span>
            <span class="benefit-text"><strong>Atualizado 2× por dia</strong><br>
            Dados frescos todas as manhãs e tardes automaticamente</span>
          </div>

          <div style="margin-top:2.5rem; padding:1rem; background:#0f1929;
                      border-radius:10px; border:1px solid #1e2d45;">
            <div style="color:#64748b; font-size:.78rem; margin-bottom:.3rem;">PLANO PRO</div>
            <div style="font-size:1.8rem; font-weight:800; color:#4ade80;">R$ 47
              <span style="font-size:.9rem; color:#64748b; font-weight:400;">/mês</span>
            </div>
            <div style="color:#94a3b8; font-size:.82rem; margin-top:.2rem;">
              Cancele quando quiser
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_sep:
        st.markdown("""
        <div style="width:1px; background:#1e2d45; min-height:500px; margin: 2rem auto;"></div>
        """, unsafe_allow_html=True)

    with col_form:
        st.markdown("<div style='padding: 2.5rem 1rem 2rem;'>", unsafe_allow_html=True)

        forgot = st.session_state.get("_show_forgot", False)

        if forgot:
            st.markdown("### Recuperar senha")
            st.markdown("<div style='color:#94a3b8;font-size:.9rem;margin-bottom:1rem;'>"
                        "Digite seu e-mail e enviaremos um link para redefinir sua senha.</div>",
                        unsafe_allow_html=True)
            with st.form("forgot_form"):
                f_email = st.text_input("E-mail", placeholder="seu@email.com", key="forgot_email")
                sent = st.form_submit_button("Enviar link", use_container_width=True, type="primary")
            if sent:
                if not f_email:
                    st.error("Digite seu e-mail")
                else:
                    ok, _ = reset_password(f_email)
                    if ok:
                        st.success("Link enviado! Verifique sua caixa de entrada.")
                        st.session_state["_show_forgot"] = False
                    else:
                        st.error("Não foi possível enviar. Verifique o e-mail digitado.")
            if st.button("← Voltar ao login"):
                st.session_state["_show_forgot"] = False
                st.rerun()

        else:
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
                                st.warning("Confirme seu e-mail antes de entrar")
                            else:
                                st.error(f"Erro: {err}")

                if st.button("Esqueci minha senha", key="btn_forgot"):
                    st.session_state["_show_forgot"] = True
                    st.rerun()

            with tab_up:
                with st.form("signup_form"):
                    s_email   = st.text_input("E-mail", placeholder="seu@email.com", key="su_email")
                    s_pass    = st.text_input("Senha", type="password",
                                              placeholder="Mínimo 6 caracteres", key="su_pass")
                    s_confirm = st.text_input("Confirmar senha", type="password",
                                              placeholder="Repita a senha", key="su_conf")
                    submitted2 = st.form_submit_button("Criar conta grátis", use_container_width=True, type="primary")

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
                            st.rerun()
                        else:
                            if "already registered" in err:
                                st.error("Este e-mail já está cadastrado")
                            else:
                                st.error(f"Erro: {err}")

        st.markdown("</div>", unsafe_allow_html=True)


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
