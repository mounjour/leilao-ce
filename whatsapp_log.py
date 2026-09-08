"""Registro persistente de falha no envio de WhatsApp.

As duas rotas de envio (favorites._whatsapp_favorito e alertas.send_whatsapp)
chamam registrar_falha() quando o POST para a Evolution API nao completa. A
linha vai para a tabela public.whatsapp_send_log no Supabase -- o unico sink
de fato persistente nesse contexto (o stdout do Streamlit Cloud / do job do
GitHub Actions some).

Quem chama passa o cliente Supabase que ja tem em maos:
  - favorites.py: o cliente com o JWT do usuario (RLS exige user_id = auth.uid())
  - alertas.py: o cliente com a service role (ignora RLS)

Este modulo NAO cria conexao e NAO importa streamlit/dotenv de proposito --
fica leve e testavel de forma isolada.
"""
from __future__ import annotations

_TABELA = "whatsapp_send_log"


def _mascarar(telefone: str) -> str:
    telefone = str(telefone or "")
    return (telefone[:4] + "***") if telefone else "?"


def registrar_falha(
    sb,
    *,
    origem: str,
    telefone: str = "",
    lote_url: str = "",
    erro: str = "",
    http_status: int | None = None,
    user_id: str | None = None,
    corpo: str = "",
) -> None:
    """Grava uma linha de falha de envio. Nunca levanta.

    Se o insert falhar (RLS, rede, tabela ausente), cai num print e segue --
    o log de falha nao pode derrubar o fluxo que ele observa (um favorito ja
    salvo, o loop de alertas).
    """
    linha = {
        "origem": str(origem)[:40],
        "telefone": str(telefone)[:32],
        "lote_url": str(lote_url)[:500],
        "erro": str(erro)[:1000],
        "http_status": int(http_status) if http_status is not None else None,
        "corpo": str(corpo)[:500],
    }
    if user_id:
        linha["user_id"] = str(user_id)

    try:
        sb.table(_TABELA).insert(linha).execute()
    except Exception as exc:
        print(
            f"[whatsapp_log] falha ao gravar log "
            f"({origem}, {_mascarar(telefone)}): {exc}"
        )
