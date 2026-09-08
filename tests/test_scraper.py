"""Testes das funcoes puras de scraper.py.

Cobrem as regras de negocio que hoje so eram verificaveis rodando o scraper
inteiro e olhando o dashboard no olho:

- classificacao de oportunidade de preco (classificar / oportunidade_preco);
- matching de modelo contra a FIPE (_score_modelo);
- referencia de mercado e categorizacao (buscar_referencia_mercado /
  detectar_categoria);
- extratores de texto livre (_parse_brl / _extrair_lance / _extrair_km).

Nao tocam rede nem browser (ver conftest.py). Rodam em bem menos de 1s:

    python -m pytest -q
"""
import pytest

from scraper import (
    _parse_brl,
    _score_modelo,
    classificar,
    oportunidade_preco,
    _extrair_lance,
    _extrair_km,
    buscar_referencia_mercado,
    detectar_categoria,
)


# --- _parse_brl -------------------------------------------------------------
class TestParseBrl:
    def test_valor_com_milhar_e_centavos(self):
        assert _parse_brl("12.500,00") == 12500.0

    def test_prefixo_reais_e_nbsp(self):
        assert _parse_brl("R$\xa0350.000,00") == 350000.0

    def test_texto_invalido_vira_zero(self):
        assert _parse_brl("sob consulta") == 0

    def test_string_vazia_vira_zero(self):
        assert _parse_brl("") == 0


# --- _score_modelo (matching FIPE) ---------------------------------------------
class TestScoreModelo:
    def test_conta_palavras_presentes(self):
        assert _score_modelo("ONIX 1.0 LT 4P", ["onix", "lt"]) == 2

    def test_palavra_ausente_nao_conta(self):
        assert _score_modelo("ONIX 1.0 LT 4P", ["onix", "premier"]) == 1

    def test_sem_acerto_e_zero(self):
        assert _score_modelo("HB20 1.0 COMFORT", ["onix", "lt"]) == 0

    def test_case_insensitive(self):
        assert _score_modelo("Corolla XEi 2.0 Flex", ["corolla", "xei"]) == 2

    def test_lista_vazia_e_zero(self):
        assert _score_modelo("Qualquer Modelo", []) == 0


# --- classificar ---------------------------------------------------------------
class TestClassificar:
    @pytest.mark.parametrize("estado", ["SINISTRADO", "BATIDO", "SUCATA"])
    def test_estado_ruim_forca_inspecionar(self, estado):
        # mesmo com preco otimo (10% da referencia), estado ruim manda inspecionar
        assert classificar(10000, 100000, estado) == "⚠️ INSPECIONAR"

    def test_sem_referencia_quando_ref_zero(self):
        assert classificar(10000, 0, "BOM") == "Sem referência"

    def test_sem_referencia_quando_lance_zero(self):
        assert classificar(0, 100000, "BOM") == "Sem referência"

    def test_otimo_ate_50pct(self):
        assert classificar(50000, 100000, "BOM") == "✅ ÓTIMO"

    def test_mediano_entre_50_e_75pct(self):
        assert classificar(70000, 100000, "BOM") == "⚠️ MEDIANO"

    def test_ruim_acima_de_75pct(self):
        assert classificar(90000, 100000, "BOM") == "❌ RUIM"

    def test_limite_75pct_ainda_e_mediano(self):
        assert classificar(75000, 100000, "BOM") == "⚠️ MEDIANO"


# --- oportunidade_preco ------------------------------------------------------
class TestOportunidadePreco:
    @pytest.mark.parametrize("estado", ["SINISTRADO", "BATIDO", "SUCATA"])
    def test_estado_ruim_inspecionar(self, estado):
        assert oportunidade_preco(10000, 100000, estado) == "INSPECIONAR"

    def test_ref_zero_inspecionar(self):
        assert oportunidade_preco(10000, 0, "BOM") == "INSPECIONAR"

    def test_lance_zero_inspecionar(self):
        assert oportunidade_preco(0, 100000, "BOM") == "INSPECIONAR"

    def test_faixa_otima_ate_50pct(self):
        assert oportunidade_preco(50000, 100000, "BOM") == "OTIMA"

    def test_faixa_boa_ate_75pct(self):
        assert oportunidade_preco(75000, 100000, "BOM") == "BOA"

    def test_faixa_regular_ate_100pct(self):
        assert oportunidade_preco(100000, 100000, "BOM") == "REGULAR"

    def test_faixa_ruim_acima_de_100pct(self):
        assert oportunidade_preco(120000, 100000, "BOM") == "RUIM"


# --- _extrair_lance --------------------------------------------------------
class TestExtrairLance:
    def test_lance_atual_rotulado(self):
        assert _extrair_lance("Lote 3 - Lance Atual: R$ 45.000,00") == 45000.0

    def test_lance_minimo_com_acento(self):
        assert _extrair_lance("Lance mínimo: R$ 1.000,00") == 1000.0

    def test_ignora_taxa_e_pega_o_lance_rotulado(self):
        txt = "Lance Atual: R$ 30.000,00. Taxa do leiloeiro: R$ 1.500,00."
        assert _extrair_lance(txt) == 30000.0

    def test_palavra_lance_solta(self):
        assert _extrair_lance("Maior lance recebido: R$ 33.000,00 até agora") == 33000.0

    def test_fallback_primeiro_valor_relevante(self):
        assert _extrair_lance("Valor de avaliação: R$ 80.000,00") == 80000.0

    def test_ignora_valores_pequenos_sem_contexto(self):
        assert _extrair_lance("Custas processuais: R$ 200,00") == 0

    def test_sem_valor_retorna_zero(self):
        assert _extrair_lance("Lote sem lances no momento") == 0


# --- _extrair_km ---------------------------------------------------------------
class TestExtrairKm:
    def test_km_com_milhar(self):
        assert _extrair_km("Hodômetro: 45.000 km") == "45.000 km"

    def test_km_maiusculo(self):
        assert _extrair_km("125.480 KM rodados") == "125.480 km"

    def test_sem_km_retorna_vazio(self):
        assert _extrair_km("quilometragem não informada") == ""

    def test_limitacao_conhecida_milhar_de_um_digito(self):
        # O regex exige 2+ digitos antes do ponto, entao "1.500 km" nao casa.
        # Limitacao conhecida: se o regex for corrigido, atualizar esta linha.
        assert _extrair_km("Rodou apenas 1.500 km") == ""


# --- buscar_referencia_mercado ---------------------------------------------
class TestReferenciaMercado:
    def test_casa_por_substring_case_insensitive(self):
        valor, rotulo = buscar_referencia_mercado("VOLVO", "FH 540 6x4")
        assert valor == 350000
        assert "ref. mercado" in rotulo

    def test_equipamento(self):
        valor, _ = buscar_referencia_mercado("", "Escavadeira hidráulica CAT 320")
        assert valor == 300000

    def test_sem_referencia(self):
        assert buscar_referencia_mercado("Fiat", "Uno 1.0") == (0, "Sem referência")


# --- detectar_categoria ------------------------------------------------------
class TestDetectarCategoria:
    def test_imovel_tem_prioridade(self):
        assert detectar_categoria("Casa e terreno com galpão", "", "carros") == "imoveis"

    def test_equipamento(self):
        assert detectar_categoria("Retroescavadeira 4x4", "JCB", "carros") == "equipamentos"

    def test_caminhao(self):
        assert detectar_categoria("FH 540", "Volvo", "carros") == "caminhoes"

    def test_moto(self):
        assert detectar_categoria("CG 160 Titan", "Honda", "carros") == "motos"

    def test_fallback_para_categoria_da_url(self):
        assert detectar_categoria("Onix 1.0 LT", "Chevrolet", "carros") == "carros"
