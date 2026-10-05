"""Testes das funcoes puras de favorites.py (chave de favorito por uuid)."""
import sys
from unittest.mock import MagicMock

# favorites.py importa streamlit e auth (que puxa supabase/stripe) no topo; o CI so instala
# pytest/requests (requirements-dev.txt) e os testes so usam funcoes puras de URL.
for _mod in ("auth", "streamlit"):
    sys.modules.setdefault(_mod, MagicMock())

from favorites import _normalizar_url, _urls_equivalentes  # noqa: E402

_UUID = "9a874398-fcf9-44f6-aee6-035b8052904a"
_CANON = f"https://www.pactoleiloes.com.br/lote/{_UUID}"


class TestNormalizarUrlPlataforma:
    def test_pacto_e_leilo_dao_a_mesma_chave(self):
        assert _normalizar_url(f"https://www.pactoleiloes.com.br/lote/{_UUID}/") == _CANON
        assert _normalizar_url(f"https://leilo.com.br/lote/{_UUID}/") == _CANON

    def test_ignora_query_fragmento_e_caixa(self):
        assert _normalizar_url(f"https://Leilo.com.br/lote/{_UUID.upper()}/?utm=x#lances") == _CANON

    def test_outro_dominio_com_uuid_nao_e_unificado(self):
        url = f"https://outroleilao.com.br/lote/{_UUID}/"
        assert _normalizar_url(url) == f"https://outroleilao.com.br/lote/{_UUID}"

    def test_url_comum_segue_a_regra_antiga(self):
        assert _normalizar_url("https://Site.com/lote/1/?a=b#x") == "https://site.com/lote/1"


class TestUrlsEquivalentes:
    def test_plataforma_cobre_formas_antigas_e_canonica(self):
        urls = _urls_equivalentes(f"https://leilo.com.br/lote/{_UUID}/")
        assert _CANON in urls
        assert f"https://leilo.com.br/lote/{_UUID}" in urls

    def test_url_comum_devolve_so_a_normalizada(self):
        assert _urls_equivalentes("https://site.com/lote/1/") == ["https://site.com/lote/1"]
