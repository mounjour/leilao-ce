"""Testes de whatsapp_log.registrar_falha (sem Supabase real).

O modulo nao importa nada pesado, entao o stub de conftest.py nem entra aqui;
so precisamos de um cliente `sb` falso que grave a linha recebida.
"""
from unittest.mock import MagicMock

import whatsapp_log


class _FakeSB:
    """Imita sb.table(nome).insert(linha).execute() e guarda o que recebeu."""

    def __init__(self, erro_no_insert=None):
        self._erro = erro_no_insert
        self.tabela = None
        self.linha = None

    def table(self, nome):
        self.tabela = nome
        return self

    def insert(self, linha):
        self.linha = linha
        return self

    def execute(self):
        if self._erro is not None:
            raise self._erro
        return MagicMock(data=[self.linha])


def test_grava_na_tabela_certa_com_os_campos():
    sb = _FakeSB()
    whatsapp_log.registrar_falha(
        sb,
        origem="favorito",
        telefone="5585999998888",
        lote_url="https://exemplo.com/lote/1",
        erro="ConnectionError",
        http_status=400,
        user_id="user-123",
        corpo="detalhe do erro",
    )
    assert sb.tabela == "whatsapp_send_log"
    assert sb.linha == {
        "origem": "favorito",
        "telefone": "5585999998888",
        "lote_url": "https://exemplo.com/lote/1",
        "erro": "ConnectionError",
        "http_status": 400,
        "corpo": "detalhe do erro",
        "user_id": "user-123",
    }


def test_trunca_campos_longos():
    sb = _FakeSB()
    whatsapp_log.registrar_falha(
        sb,
        origem="x" * 100,
        telefone="9" * 100,
        lote_url="u" * 1000,
        erro="e" * 5000,
        corpo="c" * 5000,
    )
    assert len(sb.linha["origem"]) == 40
    assert len(sb.linha["telefone"]) == 32
    assert len(sb.linha["lote_url"]) == 500
    assert len(sb.linha["erro"]) == 1000
    assert len(sb.linha["corpo"]) == 500


def test_http_status_none_fica_none_e_int_e_coagido():
    sb = _FakeSB()
    whatsapp_log.registrar_falha(sb, origem="alerta_lance")
    assert sb.linha["http_status"] is None

    sb2 = _FakeSB()
    whatsapp_log.registrar_falha(sb2, origem="alerta_lance", http_status="503")
    assert sb2.linha["http_status"] == 503


def test_user_id_ausente_quando_vazio():
    sb = _FakeSB()
    whatsapp_log.registrar_falha(sb, origem="teste", user_id="")
    assert "user_id" not in sb.linha

    sb2 = _FakeSB()
    whatsapp_log.registrar_falha(sb2, origem="teste", user_id=None)
    assert "user_id" not in sb2.linha


def test_nao_propaga_erro_do_insert(capsys):
    sb = _FakeSB(erro_no_insert=RuntimeError("RLS: permission denied"))
    # Nao deve levantar.
    whatsapp_log.registrar_falha(
        sb, origem="favorito", telefone="5585999998888"
    )
    saida = capsys.readouterr().out
    assert "[whatsapp_log]" in saida
    assert "5585***" in saida  # telefone mascarado no fallback
