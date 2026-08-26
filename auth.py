from __future__ import annotations

import os
import time

import streamlit as st
import stripe
from dotenv import load_dotenv
from supabase import Client, create_client

try:
    # Caminho documentado nas versões atuais do supabase-py.
    from supabase.client import ClientOptions
except ImportError:
    ClientOptions = None


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
_PLAN_PRICE_LABEL = _secret("STRIPE_PLAN_PRICE_LABEL", "R$ 47")
_SESSION_MAX_HOURS = float(_secret("SESSION_MAX_HOURS", "8") or 8)
_SESSION_IDLE_MINUTES = float(_secret("SESSION_IDLE_MINUTES", "60") or 60)
_SESSION_VERIFY_SECONDS = int(_secret("SESSION_VERIFY_SECONDS", "300") or 300)

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
        try:
            if ClientOptions is None:
                raise AttributeError("ClientOptions indisponível")
            options = ClientOptions(flow_type="pkce")
            st.session_state["_supabase_client"] = create_client(
                _SUPABASE_URL,
                _SUPABASE_KEY,
                options=options,
            )
        except (AttributeError, TypeError):
            # Compatibilidade com versões como 2.22/2.24, nas quais
            # ClientOptions pode gerar "object has no attribute storage".
            st.session_state["_supabase_client"] = create_client(
                _SUPABASE_URL,
                _SUPABASE_KEY,
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


def get_display_name() -> str:
    """Nome público da conta, com fallback seguro para usuários antigos."""
    user = get_user()
    profile = get_profile() or {}
    metadata = getattr(user, "user_metadata", None) or {} if user else {}

    for value in (
        profile.get("name"),
        profile.get("full_name"),
        metadata.get("name"),
        metadata.get("full_name"),
    ):
        if str(value or "").strip():
            return str(value).strip()

    email = str(getattr(user, "email", "") or "")
    return email.split("@", 1)[0].replace(".", " ").replace("_", " ").title() or "Usuário"


def is_subscribed() -> bool:
    profile = get_profile()
    if bool((profile or {}).get("billing_exempt")):
        return True
    status = str((profile or {}).get("subscription_status", "")).lower()
    return status in {"active", "trialing"}


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
    agora = time.time()
    st.session_state["_session_started_at"] = agora
    st.session_state["_session_last_activity"] = agora
    st.session_state["_session_last_verified"] = agora
    _load_profile(user.id, session)
    return True


def _load_profile(user_id: str, session=None) -> bool:
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
        return bool(response.data)
    except Exception:
        st.session_state.setdefault("profile", None)
        return False


def refresh_profile() -> bool:
    """Recarrega o plano diretamente do Supabase usando a sessão autenticada."""
    user = get_user()
    session = st.session_state.get("session")
    if not user or not session:
        return False
    return _load_profile(user.id, session)


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
        "_session_started_at",
        "_session_last_activity",
        "_session_last_verified",
        "_checkout_url",
        "_checkout_url_created_at",
        "_billing_portal_url",
        "_billing_portal_created_at",
    ):
        st.session_state.pop(key, None)


def ensure_valid_session() -> tuple[bool, str]:
    """Renova o JWT e aplica limites locais no plano gratuito."""
    user = get_user()
    session = st.session_state.get("session")
    if not user or not session:
        return False, ""

    agora = time.time()
    st.session_state.setdefault("_session_started_at", agora)
    st.session_state.setdefault("_session_last_activity", agora)
    st.session_state.setdefault("_session_last_verified", 0)

    inicio = float(st.session_state["_session_started_at"])
    ultima_atividade = float(st.session_state["_session_last_activity"])

    if _SESSION_MAX_HOURS > 0 and agora - inicio >= _SESSION_MAX_HOURS * 3600:
        logout()
        mensagem = "Sua sessão atingiu o limite de tempo. Entre novamente."
        st.session_state["_auth_notice"] = mensagem
        return False, mensagem

    if _SESSION_IDLE_MINUTES > 0 and agora - ultima_atividade >= _SESSION_IDLE_MINUTES * 60:
        logout()
        mensagem = "Sua sessão expirou por inatividade. Entre novamente."
        st.session_state["_auth_notice"] = mensagem
        return False, mensagem

    try:
        sb = _sb()
        sessao_atual = sb.auth.get_session()

        if not sessao_atual:
            resposta = sb.auth.set_session(
                session.access_token,
                session.refresh_token,
            )
            sessao_atual = getattr(resposta, "session", None)

        if not sessao_atual:
            raise RuntimeError("O Supabase não retornou uma sessão válida.")

        st.session_state["session"] = sessao_atual

        ultima_verificacao = float(st.session_state["_session_last_verified"])
        if agora - ultima_verificacao >= _SESSION_VERIFY_SECONDS:
            resposta_usuario = sb.auth.get_user(sessao_atual.access_token)
            usuario_validado = getattr(resposta_usuario, "user", None)
            if not usuario_validado:
                raise RuntimeError("Usuário não reconhecido pelo Supabase.")
            st.session_state["user"] = usuario_validado
            st.session_state["_session_last_verified"] = agora
            _load_profile(usuario_validado.id, sessao_atual)

        st.session_state["_session_last_activity"] = agora
        return True, ""
    except Exception:
        logout()
        mensagem = "Sua sessão não pôde ser renovada. Entre novamente."
        st.session_state["_auth_notice"] = mensagem
        return False, mensagem


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


def signup(
    email: str,
    password: str,
    phone: str = "",
    name: str = "",
) -> tuple[bool, str]:
    try:
        credentials = {
            "email": email.strip(),
            "password": password,
            "options": {
                "email_redirect_to": f"{_APP_URL}/?mode=confirmed",
                "data": {
                    "phone": phone.strip(),
                    "name": name.strip(),
                    "full_name": name.strip(),
                },
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


# ── Stripe checkout e portal de cobrança ────────────────────────────────────

def _validate_stripe_config(require_price: bool = False) -> None:
    missing = []
    if not stripe.api_key:
        missing.append("STRIPE_SECRET_KEY")
    if require_price and not _PRICE_ID:
        missing.append("STRIPE_PRICE_ID")
    if missing:
        raise RuntimeError(f"Configuração ausente: {', '.join(missing)}")


class ExistingSubscriptionError(RuntimeError):
    """Impede que o mesmo cliente crie uma segunda assinatura."""


def create_checkout_url() -> str:
    """Cria um Checkout vinculado ao ID imutável do usuário do Supabase."""
    _validate_stripe_config(require_price=True)
    user = get_user()
    if not user:
        raise RuntimeError("Entre na sua conta antes de assinar.")

    # Evita criar várias sessões Stripe a cada rerun do Streamlit.
    now = time.time()
    cached_url = st.session_state.get("_checkout_url")
    cached_at = float(st.session_state.get("_checkout_url_created_at", 0))
    if cached_url and now - cached_at < 15 * 60:
        return str(cached_url)

    profile = get_profile() or {}
    customer_id = str(profile.get("stripe_customer_id") or "").strip()
    if customer_id:
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="all",
            limit=20,
        )
        blocking_statuses = {
            "active", "trialing", "past_due", "unpaid", "incomplete", "paused"
        }
        existing = next(
            (
                subscription
                for subscription in subscriptions.data
                if subscription.status in blocking_statuses
            ),
            None,
        )
        if existing:
            profile["subscription_status"] = existing.status
            profile["stripe_subscription_id"] = existing.id
            st.session_state["profile"] = profile
            raise ExistingSubscriptionError(
                "Já existe uma assinatura para esta conta. "
                "Use o portal de cobrança para regularizar ou gerenciar o plano."
            )

    customer_args = (
        {"customer": customer_id}
        if customer_id
        else {"customer_email": str(getattr(user, "email", "") or "")}
    )
    user_id = str(user.id)
    user_email = str(getattr(user, "email", "") or "")

    checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        **customer_args,
        line_items=[{"price": _PRICE_ID, "quantity": 1}],
        client_reference_id=user_id,
        success_url=(
            f"{_APP_URL}/?payment=success"
            "&session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{_APP_URL}/?payment=cancel",
        metadata={
            "supabase_user_id": user_id,
            "supabase_user_email": user_email,
        },
        subscription_data={"metadata": {"supabase_user_id": user_id}},
        locale="pt-BR",
        idempotency_key=f"checkout:{user_id}:{int(now // 900)}",
    )
    st.session_state["_checkout_url"] = checkout.url
    st.session_state["_checkout_url_created_at"] = now
    return str(checkout.url)


def create_billing_portal_url() -> str:
    """Gera uma URL curta do portal Stripe para a conta autenticada."""
    _validate_stripe_config()
    profile = get_profile() or {}
    customer_id = str(profile.get("stripe_customer_id") or "").strip()
    if not customer_id:
        raise RuntimeError("Cliente de cobrança ainda não sincronizado.")

    now = time.time()
    cached_url = st.session_state.get("_billing_portal_url")
    cached_at = float(st.session_state.get("_billing_portal_created_at", 0))
    if cached_url and now - cached_at < 5 * 60:
        return str(cached_url)

    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=_APP_URL,
        locale="pt-BR",
    )
    st.session_state["_billing_portal_url"] = portal.url
    st.session_state["_billing_portal_created_at"] = now
    return str(portal.url)


# ── Rendered pages ───────────────────────────────────────────────────────────

_AUTH_CSS = """
<style>
/* Antes disso forçava background:#ffffff, mas dashboard.py já aplica seu
   próprio tema (--lce-*, claro/escuro) na página inteira antes do gate de
   login rodar — o fundo fixo branco brigava com esse tema e deixava título,
   labels e placeholders (pensados pra fundo branco) ilegíveis no dark mode.
   Usar as mesmas variáveis do resto do app resolve os dois lados. */
[data-testid="stAppViewContainer"] { background: var(--lce-bg, #ffffff) !important; }
[data-testid="stHeader"], [data-testid="stToolbar"],
#stDecoration, footer { display: none !important; }

.stTextInput label {
    color: var(--lce-muted, #374151) !important; font-size: .85rem !important;
    font-weight: 500 !important;
}
.stTextInput input {
    background: var(--lce-surface, #f9fafb) !important; color: var(--lce-text, #111827) !important;
    border: 1.5px solid var(--lce-border, #e5e7eb) !important; border-radius: 8px !important;
    font-size: .95rem !important;
}
.stTextInput input::placeholder { color: var(--lce-muted, #9ca3af) !important; }
.stTextInput input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,.1) !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1.5px solid var(--lce-border, #e5e7eb) !important;
}
.stTabs [data-baseweb="tab"] {
    color: var(--lce-muted, #9ca3af) !important; font-size: .9rem !important;
    font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    color: var(--lce-text, #111827) !important; font-weight: 600 !important;
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
hr { border-color: var(--lce-border, #f3f4f6) !important; }

/* Abaixo de ~tablet, o painel de marca ao lado do form vira peso morto
   (empurra o form pra baixo sem espaço pra respirar) — some, e o form
   volta a ocupar a coluna inteira, como era antes desse painel existir. */
@media (max-width: 1024px) {
    div[data-testid="stColumn"]:has(div[class*="st-key-auth_brand_panel"]) {
        display: none !important;
    }
}
</style>
"""


def _render_brand_panel() -> None:
    """Painel de marca/valor ao lado do form, só em telas largas (ver media query acima).

    Preenche o espaço vazio que sobrava nos dois lados do form em telas wide —
    o texto reaproveita os mesmos 3 pontos usados em pagina_sobre()/dashboard.py,
    sem inventar promessa nova.
    """
    itens = [
        ("📡", "Leilões de vários sites, num só lugar",
         "Veículos, imóveis e equipamentos monitorados automaticamente todos os dias."),
        ("🤖", "Análise de cada lote por IA",
         "Estado, riscos e oportunidade antes de você decidir dar um lance."),
        ("🔔", "Alertas no WhatsApp",
         "Avisamos assim que o lance de um lote favoritado mudar."),
    ]
    linhas_itens = "".join(
        f"""
        <div style="display:flex;gap:.9rem;align-items:flex-start;margin-bottom:1.4rem;">
          <div style="font-size:1.4rem;line-height:1.4;">{icone}</div>
          <div>
            <div style="font-weight:700;color:var(--lce-text, #111827);font-size:.95rem;">{titulo}</div>
            <div style="color:var(--lce-muted, #6b7280);font-size:.85rem;margin-top:.15rem;">{desc}</div>
          </div>
        </div>"""
        for icone, titulo, desc in itens
    )
    st.markdown(
        f"""
        <div style="background:var(--lce-surface, #f9fafb);border:1px solid var(--lce-border, #e5e7eb);
                    border-radius:var(--lce-radius, 12px);padding:2.75rem 2.25rem;">
          <div style="font-size:2.1rem;font-weight:800;color:var(--lce-text, #111827);
                      margin-bottom:.4rem;line-height:1.2;">
            🚗 Achados & Leilões
          </div>
          <div style="color:var(--lce-muted, #6b7280);font-size:1rem;margin-bottom:2.25rem;">
            Monitoramento inteligente de leilões no Ceará
          </div>
          {linhas_itens}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_brand() -> None:
    st.markdown(
        """
        <div style="text-align:center;padding:2.5rem 0 1.5rem;">
          <div style="font-size:2rem;font-weight:800;color:var(--lce-text, #111827);margin-bottom:.25rem;">
            🚗 Achados & Leilões
          </div>
          <div style="color:var(--lce-muted, #6b7280);font-size:.9rem;">
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
    col_brand, column = st.columns([1.1, 1], gap="large")

    with col_brand:
        with st.container(key="auth_brand_panel"):
            _render_brand_panel()

    with column:
        _render_brand()

        aviso_sessao = st.session_state.pop("_auth_notice", "")
        if aviso_sessao:
            st.warning(aviso_sessao)

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
                name = st.text_input(
                    "Nome", placeholder="Como você quer ser chamado", key="signup_name"
                )
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
                if not name.strip() or not email.strip() or not password or not confirmation:
                    st.error("Preencha todos os campos obrigatórios.")
                elif password != confirmation:
                    st.error("As senhas não conferem.")
                elif len(password) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                else:
                    with st.spinner("Criando conta…"):
                        ok, status = signup(email, password, phone, name)

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
            f"""
            <style>
            .paywall-box {{
                background:var(--secondary-background-color);
                color:var(--text-color);
                border:1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
                border-radius:12px; padding:2rem; text-align:center;
                margin-top:2rem;
            }}
            .paywall-price {{ font-size:2.5rem; font-weight:800; color:#16a34a; }}
            .paywall-period {{ opacity:.72; font-size:.9rem; }}
            .paywall-feature {{
                display:flex; align-items:center; gap:.5rem;
                color:var(--text-color); margin:.4rem 0; text-align:left;
            }}
            </style>
            <div class="paywall-box">
              <p style="font-size:1.2rem;font-weight:700;color:var(--text-color);margin-bottom:.5rem">
                Acesso completo ao Achados & Leilões
              </p>
              <div class="paywall-price">{_PLAN_PRICE_LABEL}</div>
              <div class="paywall-period">por mês · cancele quando quiser</div>
              <hr style="opacity:.2;margin:1.25rem 0">
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
                checkout_url = create_checkout_url()
                st.link_button(
                    f"Assinar agora — {_PLAN_PRICE_LABEL}/mês",
                    checkout_url,
                    use_container_width=True,
                    type="primary",
                )
            except ExistingSubscriptionError as exc:
                if is_subscribed():
                    st.rerun()
                st.warning(str(exc))
                try:
                    st.link_button(
                        "Abrir portal de cobrança",
                        create_billing_portal_url(),
                        use_container_width=True,
                    )
                except Exception:
                    pass
            except Exception as exc:
                st.error(f"Erro ao gerar link de pagamento: {exc}")

        payment_state = str(st.query_params.get("payment", ""))
        if payment_state == "success":
            st.info(
                "Pagamento recebido. A confirmação pode levar alguns segundos. "
                "Use o botão abaixo para atualizar seu acesso."
            )
            if st.button("Atualizar acesso", use_container_width=True, type="primary"):
                refresh_profile()
                if is_subscribed():
                    st.query_params.clear()
                    st.rerun()
                st.warning("A confirmação ainda está sendo processada. Tente novamente em instantes.")
        elif payment_state == "cancel":
            st.warning("Pagamento cancelado. Nenhuma cobrança foi concluída.")

        if st.button("Sair", use_container_width=True):
            logout()
            st.rerun()
