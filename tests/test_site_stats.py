"""Testes de scripts/gerar_stats_site.py (numeros agregados da landing)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from gerar_stats_site import gerar_stats  # noqa: E402


def test_conta_lotes_e_fontes_distintas():
    lotes = [
        {"fonte": "leilo", "scraped_at": "2026-10-02T11:00"},
        {"fonte": "leilo", "scraped_at": "2026-10-02T11:01"},
        {"fonte": "mega", "scraped_at": "2026-10-02T11:02"},
    ]
    stats = gerar_stats(lotes, "R$ 47")
    assert stats["lotes"] == 3
    assert stats["fontes"] == 2


def test_atualizado_em_e_a_coleta_mais_recente():
    lotes = [
        {"fonte": "a", "scraped_at": "2026-10-02T03:00"},
        {"fonte": "b", "scraped_at": "2026-10-02T15:00"},
    ]
    assert gerar_stats(lotes)["atualizado_em"] == "2026-10-02T15:00"


def test_lista_vazia_nao_quebra():
    stats = gerar_stats([])
    assert stats["lotes"] == 0
    assert stats["fontes"] == 0
    assert stats["atualizado_em"] is None


def test_ignora_lote_sem_fonte_e_nao_vaza_campos_de_lote():
    stats = gerar_stats([{"fonte": "", "url": "https://x", "lance_atual": 10}])
    assert stats["fontes"] == 0
    assert set(stats) == {"lotes", "fontes", "atualizado_em", "preco"}


def test_preco_e_repassado():
    assert gerar_stats([], "R$ 59")["preco"] == "R$ 59"
