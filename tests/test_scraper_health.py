"""Testes do health check do scraper (scraper_health.py).

Só funções puras + I/O em arquivo temporário. Sem rede: com OWNER_WHATSAPP
ausente, processar() nem importa `alertas`.
"""
import json

import pytest

import scraper_health as sh


@pytest.fixture(autouse=True)
def _sem_owner_whatsapp(monkeypatch):
    monkeypatch.delenv("OWNER_WHATSAPP", raising=False)


def _lotes(**por_fonte):
    saida = []
    for fonte, n in por_fonte.items():
        saida += [{"fonte": fonte, "url": f"http://x/{fonte}/{i}"} for i in range(n)]
    return saida


# ─── aplicar_run ────────────────────────────────────────────────────────────

def test_streak_sobe_quando_fonte_some_e_zera_quando_volta():
    estado = {"fontes": {}}
    sh.aplicar_run(estado, {"leilo": 10}, agora="2026-01-01T00:00Z")
    assert estado["fontes"]["leilo"]["zero_streak"] == 0
    assert estado["fontes"]["leilo"]["ultimo_nonzero"] == "2026-01-01T00:00Z"

    for _ in range(3):
        sh.aplicar_run(estado, {}, agora="2026-01-02T00:00Z")
    assert estado["fontes"]["leilo"]["zero_streak"] == 3
    assert estado["fontes"]["leilo"]["ultima_contagem"] == 0

    sh.aplicar_run(estado, {"leilo": 5}, agora="2026-01-03T00:00Z")
    assert estado["fontes"]["leilo"]["zero_streak"] == 0
    assert estado["fontes"]["leilo"]["ultimo_nonzero"] == "2026-01-03T00:00Z"


def test_fontes_ativas_rastreadas_desde_o_cold_start():
    estado = {"fontes": {}}
    sh.aplicar_run(estado, {"leilo": 1}, agora="2026-01-01T00:00Z")
    # toda FONTE_ATIVA entra no placar mesmo sem ter rendido lote
    for fonte in sh.FONTES_ATIVAS:
        assert fonte in estado["fontes"]
    assert estado["fontes"]["hastapublica"]["zero_streak"] == 1


def test_recuperacao_zera_alertado_streak():
    estado = {"fontes": {"mj": {"zero_streak": 9, "alertado_streak": 3,
                                "ultima_contagem": 0, "ultimo_nonzero": None}}}
    sh.aplicar_run(estado, {"mj": 2}, agora="2026-01-01T00:00Z")
    assert estado["fontes"]["mj"]["alertado_streak"] == 0
    assert estado["fontes"]["mj"]["zero_streak"] == 0


# ─── alvos_de_alerta ───────────────────────────────────────────────────────

def test_nao_alerta_abaixo_do_limite():
    estado = {"fontes": {"leilo": {"zero_streak": sh._LIMITE_STREAK - 1,
                                   "alertado_streak": 0}}}
    assert sh.alvos_de_alerta(estado) == []


def test_alerta_ao_cruzar_o_limite_e_nao_repete():
    estado = {"fontes": {"leilo": {"zero_streak": sh._LIMITE_STREAK,
                                   "alertado_streak": 0}}}
    assert sh.alvos_de_alerta(estado) == [("leilo", sh._LIMITE_STREAK)]
    # depois de marcado, não reaparece até a re-notificação periódica
    estado["fontes"]["leilo"]["alertado_streak"] = sh._LIMITE_STREAK
    assert sh.alvos_de_alerta(estado) == []


def test_renotifica_apos_intervalo():
    s = sh._LIMITE_STREAK + sh._RENOTIFICAR_A_CADA
    estado = {"fontes": {"leilo": {"zero_streak": s,
                                   "alertado_streak": sh._LIMITE_STREAK}}}
    assert sh.alvos_de_alerta(estado) == [("leilo", s)]


def test_fontes_esperadas_zero_nunca_alertam():
    estado = {"fontes": {f: {"zero_streak": 999, "alertado_streak": 0}
                         for f in sh.FONTES_ESPERADAS_ZERO}}
    assert sh.alvos_de_alerta(estado) == []


# ─── processar (end-to-end, arquivo temporário) ────────────────────────────

def test_processar_cria_arquivo_e_so_alerta_no_terceiro_run(tmp_path):
    arq = str(tmp_path / "scraper_health.json")
    ativas_ok = {f: 3 for f in sh.FONTES_ATIVAS if f != "mj"}  # 'mj' quebrada

    assert sh.processar(_lotes(**ativas_ok), arquivo=arq) == 0
    assert sh.processar(_lotes(**ativas_ok), arquivo=arq) == 0
    assert sh.processar(_lotes(**ativas_ok), arquivo=arq) == 1  # mj: streak 3

    dados = json.loads((tmp_path / "scraper_health.json").read_text(encoding="utf-8"))
    assert dados["fontes"]["mj"]["zero_streak"] == 3
    assert dados["fontes"]["mj"]["alertado_streak"] == 3
    # não repete no run seguinte
    assert sh.processar(_lotes(**ativas_ok), arquivo=arq) == 0


def test_processar_nao_levanta_sem_owner_e_com_lotes_vazios(tmp_path):
    arq = str(tmp_path / "h.json")
    assert sh.processar([], arquivo=arq) == 0
    assert sh.processar("lixo não iterável de dict", arquivo=arq) == 0


def test_carregar_estado_tolera_arquivo_ausente_ou_corrompido(tmp_path):
    assert sh.carregar_estado(str(tmp_path / "nao_existe.json")) == {"fontes": {}}
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{ isso não é json", encoding="utf-8")
    assert sh.carregar_estado(str(ruim)) == {"fontes": {}}
