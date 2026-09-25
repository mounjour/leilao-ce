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
import json

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
    _rf_categoria,
    _rf_editais_fortaleza,
    _rf_eletronico_ce,
    _rf_parse_eletronico,
    _grupo_lance_categoria,
    _grupo_lance_resposta_valida,
    _grupo_lance_parse_pagina,
    _chave_dedup_entre_fontes,
    _remover_duplicatas_entre_fontes,
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
    @pytest.mark.parametrize("estado", ["SINISTRADO", "BATIDO", "SUCATA", "DEFEITO"])
    def test_estado_ruim_forca_inspecionar(self, estado):
        # mesmo com preco otimo (10% da referencia), estado ruim manda inspecionar
        assert classificar(10000, 100000, estado) == "⚠️ INSPECIONAR"

    def test_eletronico_lacrado_usa_a_referencia_normal(self):
        # estado de eletronico que nao e "defeito" nao muda a regra de preco
        assert classificar(1000, 3000, "LACRADO") == "✅ ÓTIMO"
        assert classificar(2500, 3000, "USADO") == "❌ RUIM"

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
    @pytest.mark.parametrize("estado", ["SINISTRADO", "BATIDO", "SUCATA", "DEFEITO"])
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

    def test_equipamento_typo_retroecavadeira(self):
        assert detectar_categoria("Retroecavadeira XC870BR-1", "", "carros") == "equipamentos"

    def test_caminhao(self):
        assert detectar_categoria("FH 540", "Volvo", "carros") == "caminhoes"

    def test_moto(self):
        assert detectar_categoria("CG 160 Titan", "Honda", "carros") == "motos"

    def test_fallback_para_categoria_da_url(self):
        assert detectar_categoria("Onix 1.0 LT", "Chevrolet", "carros") == "carros"


# --- Receita Federal: eletronicos -----------------------------------------
class TestReceitaCategoria:
    @pytest.mark.parametrize("tipo", [
        "CELULAR/ACESSÓRIO",
        "ELETRÔNICO/ÁUDIO/VÍDEO",
        "COMPONENTE ELETRÔNICO",
        "VIDEOGAME",
    ])
    def test_tipos_eletronico(self, tipo):
        assert _rf_categoria(tipo, "", "") == "eletronicos"

    def test_tipo_caminhao_nao_e_eletronico(self):
        assert _rf_categoria("CAMINHÃO/ÔNIBUS", "Volvo", "FH") == "caminhoes"

    def test_tipo_fora_de_escopo_cai_no_fallback(self):
        # TÊXTIL / MINERAL nunca chegam aqui (filtrados antes), mas se chegarem
        # nao devem virar "eletronicos"
        assert _rf_categoria("TÊXTIL", "", "") != "eletronicos"


class TestReceitaEditaisFortaleza:
    @staticmethod
    def _dados(*grupos):
        return {"situacoes": [
            {"situacao": sit, "lista": [{"edital": e, "cidade": c}
                                        for e, c in itens]}
            for sit, itens in grupos]}

    def test_aceita_situacao_2_divulgado(self):
        d = self._dados((2, [("0317900/000004/2026", "FORTALEZA")]))
        assert len(_rf_editais_fortaleza(d)) == 1

    def test_aceita_situacao_3_propostas_em_andamento(self):
        # regressao 2026-09-21: edital 0317900/000003/2026 virou situacao 3
        d = self._dados((3, [("0317900/000003/2026", "FORTALEZA")]))
        assert len(_rf_editais_fortaleza(d)) == 1

    def test_ignora_encerrados(self):
        d = self._dados((8, [("a", "FORTALEZA")]), (11, [("b", "FORTALEZA")]),
                        (12, [("c", "FORTALEZA")]), (15, [("d", "FORTALEZA")]))
        assert _rf_editais_fortaleza(d) == []

    def test_ignora_outras_cidades(self):
        d = self._dados((2, [("x", "CURITIBA")]), (3, [("y", "SÃO PAULO")]))
        assert _rf_editais_fortaleza(d) == []

    def test_payload_vazio(self):
        assert _rf_editais_fortaleza({}) == []


class TestReceitaEletronicoCE:
    def _detalhe(self, recinto, desc="SMARTPHONE APPLE IPHONE"):
        return {"cidade": "FORTALEZA",
                "itensDetalhesLote": [{"recintoArmazenador": recinto, "descricao": desc}]}

    def test_porto_de_fortaleza_e_ce(self):
        assert _rf_eletronico_ce(self._detalhe("DMA DO PORTO DE FORTALEZA")) == "Fortaleza/CE"

    def test_recinto_sem_cidade_assume_ce(self):
        # edital e da DRF Fortaleza; recinto sem marcador de outra UF = CE
        assert _rf_eletronico_ce(self._detalhe("J. Log Logística")) == "Fortaleza/CE"

    def test_sao_luis_nao_e_ce(self):
        assert _rf_eletronico_ce(self._detalhe("IRF PORTO DE SÃO LUÍS")) == ""

    def test_teresina_nao_e_ce(self):
        assert _rf_eletronico_ce(self._detalhe("DMA Teresina")) == ""


class TestReceitaParseEletronico:
    def test_smartphone_simples(self):
        itens = [{"descricao": 'SMARTPHONE APPLE IPHONE 14 PRO 128GB NS:SK3XXL9N4D5////"VEDADA A COMERCIALIZAÇÃO"'}]
        assert _rf_parse_eletronico(itens) == ("Apple", "Iphone 14 Pro 128Gb")

    def test_prefixo_telefone_celular_removido(self):
        itens = [{"descricao": "TELEFONE CELULAR XIAOMI REDMI 12 8/256GB PAIS:CHINA-IMEI:861043070113525"}]
        assert _rf_parse_eletronico(itens) == ("Xiaomi", "Redmi 12 8/256Gb")

    def test_lote_com_varios_itens_ganha_sufixo(self):
        itens = [
            {"descricao": "TELEFONE CELULAR APPLE IPHONE 14 128GB ORIGEM:ESTRANGEIRA-3542485"},
            {"descricao": "SMARTPHONE APPLE IPHONE 12 PRO MAX 128GB S/ACESS NS:3531676"},
        ]
        marca, modelo = _rf_parse_eletronico(itens)
        assert marca == "Apple"
        assert modelo.endswith("(+1 item)")

    def test_lista_vazia(self):
        assert _rf_parse_eletronico([]) == ("?", "?")


# --- Grupo Lance -------------------------------------------------------------
class TestGrupoLanceCategoria:
    def test_imovel(self):
        assert _grupo_lance_categoria("/imoveis/imoveis-comerciais/ce/iguatu/slug-28523") == "imoveis"

    def test_veiculo_ainda_nao_suportado(self):
        # veiculos/bens-industriais/bens-de-consumo nao tem lote no CE ainda
        # (ver docs/contexto/INVESTIGACAO_NOVAS_FONTES_2026-09-14.md) — nao
        # deve ser tratado como categoria valida ate o parse ser validado.
        assert _grupo_lance_categoria("/veiculos/carros/ce/fortaleza/slug-1") is None

    def test_url_vazia(self):
        assert _grupo_lance_categoria("") is None

    def test_formato_novo_2026_09_24(self):
        assert _grupo_lance_categoria(
            "/ce/aquiraz/imoveis/terrenos-e-lotes/terreno-at-2160m2-camara-aquiraz-ce-28590") == "imoveis"
        assert _grupo_lance_categoria(
            "https://www.grupolance.com.br/ce/crato/imoveis/casas/casa-crato-ce-1") == "imoveis"

    def test_veiculo_formato_novo_nao_suportado(self):
        assert _grupo_lance_categoria("/ce/fortaleza/veiculos/carros/slug-1") is None


class TestGrupoLanceRespostaValida:
    def test_200_com_cards(self):
        assert _grupo_lance_resposta_valida(200, '<div data-key="28590">')

    def test_200_sem_cards_e_pagina_de_bloqueio(self):
        assert not _grupo_lance_resposta_valida(200, "<title>Just a moment...</title>")

    def test_403(self):
        assert not _grupo_lance_resposta_valida(403, '<div data-key="1">')

    def test_texto_vazio(self):
        assert not _grupo_lance_resposta_valida(200, "")


# HTML real (2026-09-14) de dois cards de /imoveis/ce: um com 1a/2a praça
# (28523, Iguatu) e um com praça única (28030, Juazeiro do Norte).
_GRUPO_LANCE_HTML_2_CARDS = '''
<div class="row"><div class="card-item col-sm-12 col-md-6 col-lg-4 col-xl-3" data-key="28523"><div class="card mb-4">
    <div class="card-image-holder" style="position: relative;"><a class="card-image d-block" href="https://www.grupolance.com.br/imoveis/imoveis-comerciais/ce/iguatu/imovel-comercial-at-227m2-planalto-iguatu-ce-28523" alt="Imóvel Comercial, A.T.: 227m², Planalto, Iguatu/CE" style="background: url(//cdn.grupolance.com.br/batches/16/28523/f3ccdd27d2000e3f9255a7e3e2c48800_thumb.jpg) center center no-repeat; background-size: cover;" data-pjax="0"></a></div>    <div class="card-body">
        <a class="card-title" href="/imoveis/imoveis-comerciais/ce/iguatu/imovel-comercial-at-227m2-planalto-iguatu-ce-28523" title="Imóvel Comercial, A.T.: 227m², Planalto, Iguatu/CE" data-pjax="0">Imóvel Comercial, A.T.: 227m², Planalto, Iguatu/CE</a>                <div class="card-price">
            R$ 160.000,00        </div>
        <div class="card-info">
            <div class="float-left text-uppercase"><a href="/leiloes/judiciais" data-pjax="0">Judicial</a></div>
            <div class="float-left ml-3"><a class="card-locality" href="/ce/iguatu" title="Iguatu, CE" data-pjax="0"><i class="fas fa-map-marker-alt"></i> Iguatu, CE</a></div>
            <div class="clearfix"></div>
        </div>
        <div class="card-instance-info">
            <div><a href="/imoveis/imoveis-comerciais/ce/iguatu/imovel-comercial-at-227m2-planalto-iguatu-ce-28523" data-pjax="0">28523 - LOTE 1238</a></div>
        </div>
        <div class="card-dates">
            <div class="card-date-row">
                <div class="card-instance-label"><span class="badge badge-primary">1ª Praça</span></div>
                <ol class="card-instance-date">
                    <li>15/09/2026 às 12:00</li>
                    <li>16/09/2026 às 08:00</li>
                    <li class="fs-px-12" style="line-height: 1;">R$ 160.000,00</li>
                </ol>
            </div>
            <div class="card-date-row">
                <div class="card-instance-label"><span class="badge badge-primary">2ª Praça</span></div>
                <ol class="card-instance-date">
                    <li>16/09/2026 às 08:00</li>
                    <li>15/10/2026 às 08:00</li>
                    <li class="fs-px-12" style="line-height: 1;">R$ 120.000,00</li>
                </ol>
            </div>
        </div>
    </div>
</div></div>
<div class="card-item col-sm-12 col-md-6 col-lg-4 col-xl-3" data-key="28030"><div class="card mb-4">
    <div class="card-image-holder" style="position: relative;"><a class="card-image d-block" href="https://www.grupolance.com.br/imoveis/terrenos-e-lotes/ce/juazeiro-do-norte/terreno-6000m2-jose-geraldo-da-cruz-juazeiro-do-norte-ce-28030" alt="Terreno" style="background: url(//cdn.grupolance.com.br/batches/fc/28030/07f62224f5b4296c2af4975ac0da5576_thumb.jpg) center center no-repeat; background-size: cover;" data-pjax="0"></a></div>    <div class="card-body">
        <a class="card-title" href="/imoveis/terrenos-e-lotes/ce/juazeiro-do-norte/terreno-6000m2-jose-geraldo-da-cruz-juazeiro-do-norte-ce-28030" title="Terreno, 6.000m², José Geraldo da Cruz, Juazeiro do Norte/CE" data-pjax="0">Terreno, 6.000m², José Geraldo da Cruz, Juazeiro do Norte/CE</a>                <div class="card-price">
            R$ 1.575.000,00        </div>
        <div class="card-info">
            <div class="float-left text-uppercase"><a href="/leiloes/judiciais" data-pjax="0">Judicial</a></div>
            <div class="float-left ml-3"><a class="card-locality" href="/ce/juazeiro-do-norte" title="Juazeiro Do Norte, CE" data-pjax="0"><i class="fas fa-map-marker-alt"></i> Juazeiro Do Norte, CE</a></div>
            <div class="clearfix"></div>
        </div>
        <div class="card-instance-info">
            <div><a href="/imoveis/terrenos-e-lotes/ce/juazeiro-do-norte/terreno-6000m2-jose-geraldo-da-cruz-juazeiro-do-norte-ce-28030" data-pjax="0">28030 - LOTE 344</a></div>
        </div>
        <div class="card-dates">
            <div class="card-date-row">
                <div class="card-instance-label"><span class="badge badge-primary">P. Única</span></div>
                <ol class="card-instance-date">
                    <li>02/03/2026 às 08:00</li>
                    <li>05/12/2026 às 10:00</li>
                    <li class="fs-px-12" style="line-height: 1;">R$ 1.575.000,00</li>
                </ol>
            </div>
        </div>
    </div>
</div></div>
</div>
'''


# HTML real (2026-09-24) de um card de /ce/imoveis, com o formato novo de URL.
_GRUPO_LANCE_HTML_CARD_NOVO = '''
<div class="card-item col-sm-12 col-md-6 col-lg-4 col-xl-3" data-key="28590"><div class="card mb-4">
    <div class="card-image-holder" style="position: relative;"><a class="card-image d-block" href="https://www.grupolance.com.br/ce/aquiraz/imoveis/terrenos-e-lotes/terreno-at-2160m2-camara-aquiraz-ce-28590" alt="Terreno" style="background: url(//cdn.grupolance.com.br/batches/f1/28590/f3ccdd27d2000e3f9255a7e3e2c48800_thumb.jpg) center center no-repeat; background-size: cover;" data-pjax="0"></a></div>    <div class="card-body">
        <a class="card-title" href="/ce/aquiraz/imoveis/terrenos-e-lotes/terreno-at-2160m2-camara-aquiraz-ce-28590" title="Terreno, A.T.: 2.160m², Camará, Aquiraz/CE" data-pjax="0">Terreno, A.T.: 2.160m², Camará, Aquiraz/CE</a>                <div class="card-price">
            R$ 150.000,00        </div>
        <div class="card-info">
            <div class="float-left ml-3"><a class="card-locality" href="/ce/aquiraz" title="Aquiraz, CE" data-pjax="0"> Aquiraz, CE</a></div>
        </div>
        <div class="card-dates">
            <div class="card-date-row">
                <ol class="card-instance-date">
                    <li>27/08/2026 às 12:00</li>
                    <li>28/08/2026 às 08:00</li>
                    <li class="fs-px-12" style="line-height: 1;">R$ 150.000,00</li>
                </ol>
            </div>
        </div>
    </div>
</div></div>
'''


class TestGrupoLanceParsePagina:
    def test_card_formato_novo_de_url(self):
        itens = _grupo_lance_parse_pagina(_GRUPO_LANCE_HTML_CARD_NOVO)
        assert len(itens) == 1
        assert itens[0]["categoria"] == "imoveis"
        assert itens[0]["cidade"] == "Aquiraz/CE"
        assert itens[0]["lance"] == 150000.0

    def test_extrai_dois_cards(self):
        itens = _grupo_lance_parse_pagina(_GRUPO_LANCE_HTML_2_CARDS)
        assert len(itens) == 2

    def test_card_com_1a_e_2a_praca(self):
        it = _grupo_lance_parse_pagina(_GRUPO_LANCE_HTML_2_CARDS)[0]
        assert it["id"] == "28523"
        assert it["url"] == ("https://www.grupolance.com.br/imoveis/imoveis-comerciais/ce/"
                             "iguatu/imovel-comercial-at-227m2-planalto-iguatu-ce-28523")
        assert it["categoria"] == "imoveis"
        assert it["cidade"] == "Iguatu/CE"
        assert it["titulo"] == "Imóvel Comercial, A.T.: 227m², Planalto, Iguatu/CE"
        # card-price mostra o valor da praça ativa agora (1a praça, 160k);
        # a referencia de avaliação é o maior valor entre as praças.
        assert it["lance"] == 160000.0
        assert it["ref_val"] == 160000.0
        assert it["data_leilao"] == "2026-09-15T12:00"
        assert it["foto"] == "https://cdn.grupolance.com.br/batches/16/28523/f3ccdd27d2000e3f9255a7e3e2c48800_thumb.jpg"

    def test_card_com_praca_unica(self):
        it = _grupo_lance_parse_pagina(_GRUPO_LANCE_HTML_2_CARDS)[1]
        assert it["id"] == "28030"
        assert it["cidade"] == "Juazeiro Do Norte/CE"
        assert it["lance"] == 1575000.0
        assert it["ref_val"] == 1575000.0

    def test_pagina_sem_cards(self):
        assert _grupo_lance_parse_pagina("<html><body>sem lotes</body></html>") == []


# --- Leilo -------------------------------------------------------------------
# Fixture: 6 lotes REAIS de leilo.com.br/leilao/ceara/ (2026-09-25) dentro do
# HTML no formato do site (`window.__INITIAL_STATE__=...`). Ordem: moto com
# lance, moto sem lance e sem foto, carro, utilitario sem lance, moto sem km,
# moto com km < 1000. Os casos de outro estado / campos ausentes sao sinteticos,
# derivados desses lotes. Contexto: docs/contexto/LEILO_REDESIGN_2026-09.md.
import copy
from pathlib import Path

import scraper as _sc
from scraper import (
    _uuid_lote_plataforma,
    _plataforma_estado_elastic,
    _plataforma_parse_lote,
    _plataforma_parse_pagina,
    _plataforma_coletar,
    _analise_do_gemeo,
    _raspar_leilo,
    _raspar_pacto,
)

_LEILO_HTML = (Path(__file__).parent / "fixtures" / "leilo_listagem_2026-09-25.html"
               ).read_text(encoding="utf-8")
_UUID_NXR = "72951930-efeb-4baa-81e3-7470abe10dc5"


def _plataforma_lotes_json():
    """Copia profunda dos lotes do JSON da fixture, para alterar nos testes."""
    return copy.deepcopy(_plataforma_estado_elastic(_LEILO_HTML)["lotes"])


class TestUuidLotePlataforma:
    def test_pacto_e_plataforma_dao_o_mesmo_uuid(self):
        assert _uuid_lote_plataforma(f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/") == _UUID_NXR
        assert _uuid_lote_plataforma(f"https://leilo.com.br/lote/{_UUID_NXR}/") == _UUID_NXR

    def test_ignora_query_string_e_caixa(self):
        url = f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR.upper()}/?localizacao.estado=CE"
        assert _uuid_lote_plataforma(url) == _UUID_NXR

    def test_outro_dominio_nao_e_reconhecido(self):
        assert _uuid_lote_plataforma(f"https://outroleilao.com.br/lote/{_UUID_NXR}/") is None

    def test_url_legada_do_pacto_nao_e_reconhecida(self):
        assert _uuid_lote_plataforma(
            "https://www.pactoleiloes.com.br/leilao/eusebio-ce/carros/peugeot-208/"
            f"ano.2018/{_UUID_NXR}") is None

    def test_vazio_e_none(self):
        assert _uuid_lote_plataforma("") is None
        assert _uuid_lote_plataforma(None) is None


class TestLeiloParseLote:
    def test_moto_com_lance(self):
        it = _plataforma_parse_lote(_plataforma_lotes_json()[0], _sc._LEILO_BASE)
        assert it["uuid"] == _UUID_NXR
        assert it["url"] == f"https://leilo.com.br/lote/{_UUID_NXR}/"
        assert it["categoria_url"] == "motos"
        assert (it["marca"], it["modelo"]) == ("Honda", "Nxr 160 Bros Abs")
        assert it["ano"] == 2026
        assert it["cidade"] == "Eusébio/CE"
        assert it["km"] == "15.495 km"
        assert it["lance"] == 16400.0
        assert it["descricao"] == "Recuperado de Financiamento"
        assert it["foto"].startswith("https://leilo.cdndp.com.br/") and it["foto"].endswith(".jpeg")
        # leilao.data vem em UTC (12:30Z); o card do site mostra 09:30 de Fortaleza.
        assert it["data_leilao"] == "2026-09-26T09:30"

    def test_sem_lance_usa_o_lance_inicial(self):
        # O card mostra "Lance Inicial R$ 5.700,00" (= valor.minimo) enquanto
        # ninguem lancou; lance 0 zeraria a classificacao e o health check.
        it = _plataforma_parse_lote(_plataforma_lotes_json()[1], _sc._LEILO_BASE)
        assert it["lance"] == 5700.0

    def test_lote_sem_foto_fica_com_foto_vazia(self):
        assert _plataforma_parse_lote(_plataforma_lotes_json()[1], _sc._LEILO_BASE)["foto"] == ""

    def test_foto_generica_e_descartada(self):
        lote = _plataforma_lotes_json()[0]
        lote["fotosUrls"] = ["https://leilo.com.br/lote/fotos-modelo/moto.webp",
                             "https://leilo.cdndp.com.br/v1/arquivo/x.jpeg"]
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE)["foto"] == "https://leilo.cdndp.com.br/v1/arquivo/x.jpeg"
        lote["fotosUrls"] = ["https://leilo.com.br/lote/fotos-modelo/moto.webp"]
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE)["foto"] == ""

    def test_tipo_utilitarios_vira_caminhoes(self):
        it = _plataforma_parse_lote(_plataforma_lotes_json()[3], _sc._LEILO_BASE)
        assert it["categoria_url"] == "caminhoes"
        assert it["km"] == "144.960 km"

    def test_tipo_desconhecido_cai_em_carros(self):
        lote = _plataforma_lotes_json()[0]
        lote["tipo"] = "Tipo Novo"
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE)["categoria_url"] == "carros"

    def test_km_ausente_e_km_baixo(self):
        lotes = _plataforma_lotes_json()
        assert _plataforma_parse_lote(lotes[4], _sc._LEILO_BASE)["km"] == ""
        assert _plataforma_parse_lote(lotes[5], _sc._LEILO_BASE)["km"] == "623 km"

    def test_lote_de_outro_estado_e_descartado(self):
        # Trava contra o bug de 2026-09-16 (lotes de GO/DF/MT rotulados "/CE"):
        # a UF do proprio lote e' a fonte da verdade.
        lote = _plataforma_lotes_json()[0]
        lote["localizacao"] = {"nome": "PATIO GOIANIA", "cidade": "APARECIDA DE GOIANIA", "estado": "GO"}
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE) is None

    def test_sem_localizacao_e_descartado(self):
        lote = _plataforma_lotes_json()[0]
        del lote["localizacao"]
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE) is None

    def test_id_invalido_ou_nome_vazio_e_descartado(self):
        lote = _plataforma_lotes_json()[0]
        lote["id"] = "nao-e-uuid"
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE) is None
        lote = _plataforma_lotes_json()[0]
        lote["nome"] = "  "
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE) is None

    def test_nome_sem_barra_vira_modelo_com_marca_outros(self):
        lote = _plataforma_lotes_json()[0]
        lote["nome"] = "GERADOR 5KVA"
        it = _plataforma_parse_lote(lote, _sc._LEILO_BASE)
        assert (it["marca"], it["modelo"]) == ("Outros", "Gerador 5Kva")

    def test_lote_sem_veiculo_nao_quebra(self):
        lote = _plataforma_lotes_json()[0]
        lote["veiculo"] = None
        it = _plataforma_parse_lote(lote, _sc._LEILO_BASE)
        assert it["ano"] == 0 and it["km"] == "" and it["descricao"] == ""

    def test_data_cai_para_data_fim_sem_data_do_leilao(self):
        lote = _plataforma_lotes_json()[0]
        lote["leilao"] = {}
        assert _plataforma_parse_lote(lote, _sc._LEILO_BASE)["data_leilao"] == "2026-09-26T09:43"


class TestLeiloParsePagina:
    def test_pagina_real(self):
        dados = _plataforma_parse_pagina(_LEILO_HTML, _sc._LEILO_BASE)
        assert len(dados["itens"]) == 6
        assert (dados["pagina"], dados["paginas"], dados["total"], dados["recebidos"]) == (1, 2, 54, 6)
        assert all(it["cidade"].endswith("/CE") for it in dados["itens"])

    def test_pagina_mista_so_mantem_ce_mas_conta_o_recebido(self):
        lotes = _plataforma_lotes_json()
        lotes[0]["localizacao"]["estado"] = "GO"
        json_estado = json.dumps({"elastic": {"lotes": lotes}})
        dados = _plataforma_parse_pagina(f"<script>window.__INITIAL_STATE__={json_estado};x()</script>", _sc._LEILO_BASE)
        assert len(dados["itens"]) == 5
        assert dados["recebidos"] == 6

    def test_sem_estado_devolve_none(self):
        # HTML 200 sem o JSON = layout mudou; o chamador precisa saber (!= 0 lotes no CE).
        assert _plataforma_parse_pagina("<html><body>sem lotes</body></html>", _sc._LEILO_BASE) is None

    def test_json_invalido_ou_sem_lotes_devolve_none(self):
        assert _plataforma_parse_pagina("<script>window.__INITIAL_STATE__={quebrado</script>", _sc._LEILO_BASE) is None
        assert _plataforma_parse_pagina('<script>window.__INITIAL_STATE__={"elastic":{}}</script>', _sc._LEILO_BASE) is None


def _pag(n, paginas, uuids):
    """Resposta falsa de _plataforma_baixar_pagina."""
    itens = []
    for u in uuids:
        it = _plataforma_parse_lote(_plataforma_lotes_json()[0], _sc._LEILO_BASE)
        it["uuid"], it["url"] = u, f"https://leilo.com.br/lote/{u}/"
        itens.append(it)
    return {"itens": itens, "recebidos": len(itens), "pagina": n,
            "paginas": paginas, "total": 3}


class TestLeiloColetar:
    def test_percorre_todas_as_paginas(self, monkeypatch):
        paginas = {1: _pag(1, 2, ["u1", "u2"]), 2: _pag(2, 2, ["u3"])}
        monkeypatch.setattr(_sc, "_plataforma_baixar_pagina", lambda b, n: paginas[n])
        itens, total = _plataforma_coletar(_sc._LEILO_BASE)
        assert [it["uuid"] for it in itens] == ["u1", "u2", "u3"]
        assert total == 3

    def test_falha_na_pagina_2_mantem_a_1(self, monkeypatch):
        monkeypatch.setattr(_sc, "_plataforma_baixar_pagina",
                            lambda b, n: _pag(1, 2, ["u1", "u2"]) if n == 1 else None)
        itens, _ = _plataforma_coletar(_sc._LEILO_BASE)
        assert [it["uuid"] for it in itens] == ["u1", "u2"]

    def test_falha_na_pagina_1_devolve_vazio(self, monkeypatch):
        def falha(b, n):
            raise ConnectionError("sem rede")
        monkeypatch.setattr(_sc, "_plataforma_baixar_pagina", falha)
        assert _plataforma_coletar(_sc._LEILO_BASE) == ([], 0)

    def test_site_que_ignora_o_parametro_de_pagina_nao_entra_em_loop(self, monkeypatch):
        chamadas = []

        def sempre_pagina_1(b, n):
            chamadas.append(n)
            return _pag(1, 5, ["u1", "u2"])
        monkeypatch.setattr(_sc, "_plataforma_baixar_pagina", sempre_pagina_1)
        itens, _ = _plataforma_coletar(_sc._LEILO_BASE)
        assert chamadas == [1, 2]
        assert len(itens) == 2

    def test_respeita_o_limite_de_paginas(self, monkeypatch):
        chamadas = []

        def infinito(b, n):
            chamadas.append(n)
            return _pag(n, 999, [f"u{n}"])
        monkeypatch.setattr(_sc, "_plataforma_baixar_pagina", infinito)
        _plataforma_coletar(_sc._LEILO_BASE)
        assert len(chamadas) == _sc._PLATAFORMA_MAX_PAGINAS


class TestRasparLeilo:
    """Cola de _raspar_leilo, sem rede: FIPE e IA falsas."""

    _ANALISE_PACTO = {"estado": "USADO", "selo": "🚗 Usado", "uso_sugerido": "uso pessoal",
                      "positivos": ["ok"], "negativos": [], "avaliacao_plataforma": "boa"}

    def _preparar(self, monkeypatch, cache):
        item = _plataforma_parse_lote(_plataforma_lotes_json()[0], _sc._LEILO_BASE)
        monkeypatch.setattr(_sc, "_plataforma_coletar", lambda base: ([item], 1))
        monkeypatch.setattr(_sc, "buscar_fipe", lambda *a: (24363.0, "R$ 24.363"))
        monkeypatch.setattr(_sc, "_CACHE_ANALISE", cache)
        monkeypatch.setattr(_sc.time, "sleep", lambda s: None)

    def test_gera_lote_do_plataforma_com_os_campos_do_parser(self, monkeypatch):
        self._preparar(monkeypatch, {})
        chamadas = []
        monkeypatch.setattr(_sc, "_analisar_cached",
                            lambda *a: chamadas.append(a) or dict(self._ANALISE_PACTO))
        lotes = _raspar_leilo(set())
        assert len(lotes) == 1 and len(chamadas) == 1
        l = lotes[0]
        assert l["fonte"] == "leilo" and l["categoria"] == "motos"
        assert l["url"] == f"https://leilo.com.br/lote/{_UUID_NXR}/"
        assert l["lance_atual"] == 16400.0 and l["foto"].endswith(".jpeg")
        assert l["data_leilao"] == "2026-09-26T09:30"

    def test_reaproveita_a_analise_do_gemeo_no_pacto(self, monkeypatch):
        url_pacto = f"{_sc._PACTO_BASE}/lote/{_UUID_NXR}/"
        cache = {_sc._id_veiculo(url_pacto): {"cache_version": _sc._CACHE_VERSION,
                                               "analise": dict(self._ANALISE_PACTO)}}
        self._preparar(monkeypatch, cache)

        def nao_deve_chamar(*a):
            raise AssertionError("IA chamada de novo para lote que o Pacto ja analisou")
        monkeypatch.setattr(_sc, "_analisar_cached", nao_deve_chamar)
        lotes = _raspar_leilo({url_pacto})
        assert len(lotes) == 1  # segue no resultado: o dedup e' no fim do pipeline
        assert lotes[0]["estado"] == "USADO"

    def test_sem_gemeo_no_vistos_nao_reaproveita(self, monkeypatch):
        url_pacto = f"{_sc._PACTO_BASE}/lote/{_UUID_NXR}/"
        cache = {_sc._id_veiculo(url_pacto): {"cache_version": _sc._CACHE_VERSION,
                                               "analise": dict(self._ANALISE_PACTO)}}
        self._preparar(monkeypatch, cache)
        chamadas = []
        monkeypatch.setattr(_sc, "_analisar_cached",
                            lambda *a: chamadas.append(a) or dict(_sc._FALLBACK_IA))
        _raspar_leilo(set())  # Pacto nao raspou esse lote nesta run
        assert len(chamadas) == 1


class TestAnaliseDoGemeo:
    def test_devolve_a_analise_em_cache(self, monkeypatch):
        url = f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/"
        monkeypatch.setattr(_sc, "_CACHE_ANALISE", {_sc._id_veiculo(url): {
            "cache_version": _sc._CACHE_VERSION, "analise": {"estado": "LACRADO"}}})
        assert _analise_do_gemeo(url) == {"estado": "LACRADO"}

    def test_ignora_cache_de_versao_antiga_e_ausente(self, monkeypatch):
        url = f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/"
        monkeypatch.setattr(_sc, "_CACHE_ANALISE", {_sc._id_veiculo(url): {
            "cache_version": -1, "analise": {"estado": "LACRADO"}}})
        assert _analise_do_gemeo(url) is None
        monkeypatch.setattr(_sc, "_CACHE_ANALISE", {})
        assert _analise_do_gemeo(url) is None


# --- _chave_dedup_entre_fontes / _remover_duplicatas_entre_fontes ----------
def _lote(fonte, descricao="", modelo="", url=""):
    return {"fonte": fonte, "descricao": descricao, "modelo": modelo, "url": url}


class TestChaveDedupEntreFontes:
    def test_extrai_numero_de_processo_cnj(self):
        lote = _lote("maria_fixer", descricao="(Proc. 8500061-18.2025.8.06.0076)")
        assert _chave_dedup_entre_fontes(lote) == "proc:8500061-18.2025.8.06.0076"

    def test_extrai_matricula_do_imovel(self):
        lote = _lote("spy_leiloes",
                      descricao="50% DO IMÓVEL DA MATRÍCULA 6.264 DO REGISTRO DE IMÓVEIS")
        assert _chave_dedup_entre_fontes(lote) == "mat:6264"

    def test_matricula_curta_demais_e_ignorada(self):
        # Menos de 4 digitos e comum demais pra servir de identificador —
        # risco real de colidir por coincidencia entre imoveis diferentes.
        lote = _lote("spy_leiloes", descricao="Matrícula nº 12 do cartório")
        assert _chave_dedup_entre_fontes(lote) is None

    def test_sem_identificador_retorna_none(self):
        lote = _lote("grupo_lance", descricao="Terreno c/ 500m² - Cananéia/SP")
        assert _chave_dedup_entre_fontes(lote) is None

    def test_busca_tambem_no_campo_modelo(self):
        lote = _lote("francisco_freitas", descricao="", modelo="Proc. 1234567-89.2025.8.06.0001")
        assert _chave_dedup_entre_fontes(lote) == "proc:1234567-89.2025.8.06.0001"

    def test_uuid_do_lote_e_igual_no_pacto_e_no_leilo(self):
        pacto = _lote("pacto", url=f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/")
        leilo = _lote("leilo", url=f"https://leilo.com.br/lote/{_UUID_NXR}/")
        assert _chave_dedup_entre_fontes(pacto) == f"lote:{_UUID_NXR}"
        assert _chave_dedup_entre_fontes(leilo) == _chave_dedup_entre_fontes(pacto)

    def test_uuid_tem_prioridade_sobre_o_texto(self):
        lote = _lote("leilo", descricao="Proc. 8500061-18.2025.8.06.0076",
                     url=f"https://leilo.com.br/lote/{_UUID_NXR}/")
        assert _chave_dedup_entre_fontes(lote) == f"lote:{_UUID_NXR}"


class TestRemoverDuplicatasEntreFontes:
    def test_remove_mesmo_processo_de_fonte_diferente(self):
        direto     = _lote("francisco_freitas", descricao="Proc. 8500061-18.2025.8.06.0076", url="a")
        agregador  = _lote("spy_leiloes", descricao="Proc. 8500061-18.2025.8.06.0076", url="b")
        resultado = _remover_duplicatas_entre_fontes([direto, agregador])
        assert resultado == [direto]

    def test_mantem_a_primeira_ocorrencia(self):
        # raspar_leiloes() chama os leiloeiros diretos antes dos agregadores,
        # entao a ordem de entrada ja favorece a fonte original.
        primeiro = _lote("maria_fixer", descricao="Proc. 1111111-11.2025.8.06.0001", url="a")
        segundo  = _lote("spy_leiloes", descricao="Proc. 1111111-11.2025.8.06.0001", url="b")
        resultado = _remover_duplicatas_entre_fontes([segundo, primeiro])
        assert resultado == [segundo]

    def test_sem_identificador_nunca_e_removido(self):
        # Dois lotes de veiculo bem diferentes, sem processo/matricula —
        # nao ha chave, entao ambos sobrevivem mesmo sem nada em comum.
        a = _lote("mega", descricao="Honda Cg 125", url="a")
        b = _lote("pacto", descricao="Honda Cg 125", url="b")
        resultado = _remover_duplicatas_entre_fontes([a, b])
        assert resultado == [a, b]

    def test_lotes_de_processos_diferentes_sobrevivem_ambos(self):
        a = _lote("francisco_freitas", descricao="Proc. 1111111-11.2025.8.06.0001", url="a")
        b = _lote("maria_fixer", descricao="Proc. 2222222-22.2025.8.06.0002", url="b")
        resultado = _remover_duplicatas_entre_fontes([a, b])
        assert resultado == [a, b]

    def test_remove_o_plataforma_quando_o_pacto_tem_o_mesmo_lote(self):
        # Pacto roda antes no pipeline: e' o canonico, o Leilo sai.
        pacto = _lote("pacto", modelo="Nxr 160 Bros Abs",
                      url=f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/")
        leilo = _lote("leilo", modelo="Nxr 160 Bros Abs",
                      url=f"https://leilo.com.br/lote/{_UUID_NXR}/")
        assert _remover_duplicatas_entre_fontes([pacto, leilo]) == [pacto]

    def test_plataforma_sobrevive_quando_o_pacto_nao_tem_o_lote(self):
        # Reserva: se o scraper do Pacto quebrar, os lotes do Leilo aparecem.
        leilo = _lote("leilo", url=f"https://leilo.com.br/lote/{_UUID_NXR}/")
        assert _remover_duplicatas_entre_fontes([leilo]) == [leilo]

    def test_lotes_parecidos_com_uuids_diferentes_sobrevivem_ambos(self):
        # Mesmo modelo, ano, lance e leilao, mas sao duas motos: uuid diferente.
        outro = "0e1a5d43-05ae-40fa-9dea-93be8417a420"
        pacto = _lote("pacto", modelo="Honda Biz 125",
                      url=f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/")
        leilo = _lote("leilo", modelo="Honda Biz 125",
                      url=f"https://leilo.com.br/lote/{outro}/")
        assert _remover_duplicatas_entre_fontes([pacto, leilo]) == [pacto, leilo]

    def test_mesmo_uuid_em_dominio_desconhecido_nao_e_removido(self):
        pacto = _lote("pacto", url=f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/")
        outro = _lote("mega", url=f"https://outrosite.com.br/lote/{_UUID_NXR}/")
        assert _remover_duplicatas_entre_fontes([pacto, outro]) == [pacto, outro]


# ─── PACTO via parser da plataforma (requests, sem Playwright) ────────────────
# Fixture: 6 primeiros lotes de pactoleiloes.com.br/leilao/ceara/ em 2026-09-25
# (so o JSON `elastic` de window.__INITIAL_STATE__, recortado).
_PACTO_HTML = (Path(__file__).parent / "fixtures" / "pacto_listagem_2026-09-25.html"
               ).read_text(encoding="utf-8")


class TestPactoParsePagina:
    def test_pagina_real_usa_o_dominio_do_pacto(self):
        dados = _plataforma_parse_pagina(_PACTO_HTML, _sc._PACTO_BASE)
        assert len(dados["itens"]) == 6 and dados["total"] == 69
        for it in dados["itens"]:
            assert it["url"] == f"https://www.pactoleiloes.com.br/lote/{it['uuid']}/"
            assert _uuid_lote_plataforma(it["url"]) == it["uuid"]
            assert it["cidade"].endswith("/CE")

    def test_campos_chave_preenchidos_e_foto_generica_descartada(self):
        itens = _plataforma_parse_pagina(_PACTO_HTML, _sc._PACTO_BASE)["itens"]
        assert all(it["lance"] > 0 for it in itens)  # lance ou "Lance Inicial"
        assert itens[0]["lance"] == 16400.0 and itens[2]["lance"] == 5700.0
        assert itens[0]["foto"].startswith("https://") and itens[2]["foto"] == ""
        assert itens[0]["data_leilao"] == "2026-09-26T09:30"

    def test_mesmo_uuid_e_campos_que_o_leilo_para_o_mesmo_lote(self):
        pacto = _plataforma_parse_pagina(_PACTO_HTML, _sc._PACTO_BASE)["itens"]
        leilo = _plataforma_parse_pagina(_LEILO_HTML, _sc._LEILO_BASE)["itens"]
        p0 = next(it for it in pacto if it["uuid"] == _UUID_NXR)
        l0 = next(it for it in leilo if it["uuid"] == _UUID_NXR)
        campos = ("marca", "modelo", "ano", "lance", "foto", "km", "data_leilao", "categoria_url")
        assert {c: p0[c] for c in campos} == {c: l0[c] for c in campos}
        assert p0["url"] != l0["url"]


class TestRasparPacto:
    """Cola de _raspar_pacto, sem rede: FIPE e IA falsas."""

    def _preparar(self, monkeypatch, itens):
        monkeypatch.setattr(_sc, "_plataforma_coletar", lambda base: (itens, len(itens)))
        monkeypatch.setattr(_sc, "buscar_fipe", lambda *a: (24363.0, "R$ 24.363"))
        monkeypatch.setattr(_sc.time, "sleep", lambda s: None)

    def _itens(self):
        return _plataforma_parse_pagina(_PACTO_HTML, _sc._PACTO_BASE)["itens"]

    def test_gera_lote_do_pacto(self, monkeypatch):
        itens = self._itens()[:1]
        self._preparar(monkeypatch, itens)
        chamadas = []
        monkeypatch.setattr(_sc, "_analisar_cached",
                            lambda *a: chamadas.append(a) or dict(TestRasparLeilo._ANALISE_PACTO))
        vistos = set()
        lotes = _raspar_pacto(vistos)
        assert len(lotes) == 1 and len(chamadas) == 1
        l = lotes[0]
        assert l["fonte"] == "pacto" and l["categoria"] == "motos"
        assert l["cidade"] == "Eusebio/CE"
        assert l["url"] == f"https://www.pactoleiloes.com.br/lote/{_UUID_NXR}/"
        assert l["lance_atual"] == 16400.0 and l["foto"].endswith(".jpeg")
        assert l["data_leilao"] == "2026-09-26T09:30"
        assert l["url"] in vistos
        # A descricao do lote (retomada) vai para a IA, como no Leilo.
        assert chamadas[0][4] == itens[0]["descricao"]

    def test_pula_url_ja_vista(self, monkeypatch):
        itens = self._itens()[:1]
        self._preparar(monkeypatch, itens)
        assert _raspar_pacto({itens[0]["url"]}) == []

    def test_sem_lotes_devolve_vazio(self, monkeypatch):
        self._preparar(monkeypatch, [])
        assert _raspar_pacto(set()) == []

    def test_lote_com_erro_nao_derruba_os_outros(self, monkeypatch):
        itens = self._itens()[:2]
        self._preparar(monkeypatch, itens)
        n = []

        def analisar(*a):
            n.append(1)
            if len(n) == 1:
                raise RuntimeError("falha na IA")
            return dict(TestRasparLeilo._ANALISE_PACTO)
        monkeypatch.setattr(_sc, "_analisar_cached", analisar)
        assert len(_raspar_pacto(set())) == 1


# --- MJ Leiloes: dedup de URL, titulo e categoria ---------------------------
from scraper import _mj_normalizar_lote_path, _mj_lote_paths, _mj_parse_titulo, _mj_categoria

_MJ_LOTE_1182 = "/lote/1182/fiat-uno-evolution-1-4-cor-branca-combustivel-flex-ano-mod-2014-2015-dir-a-documento"


class TestMjNormalizarLote:
    def test_remove_fragmento_lances(self):
        assert _mj_normalizar_lote_path(_MJ_LOTE_1182 + "#lances") == _MJ_LOTE_1182

    def test_remove_query_e_barra_final(self):
        assert _mj_normalizar_lote_path("/lote/9/x-y/?a=1#z") == "/lote/9/x-y"

    def test_path_limpo_nao_muda(self):
        assert _mj_normalizar_lote_path(_MJ_LOTE_1182) == _MJ_LOTE_1182

    def test_lote_paths_dedup_com_e_sem_fragmento(self):
        html = (f'<a href="{_MJ_LOTE_1182}">x</a><a href="{_MJ_LOTE_1182}#lances">y</a>'
                '<a href="/lote/1170/sucata-de-compressor-de-ar#lances">z</a>')
        assert _mj_lote_paths(html) == [_MJ_LOTE_1182, "/lote/1170/sucata-de-compressor-de-ar"]


# (titulo real do site, nome-categoria esperada, marca, modelo, ano)
_MJ_TITULOS = [
    ("FIAT UNO EVOLUTION 1.4, COR: BRANCA, COMBUSTÍVEL; FLEX, ANO/MOD 2014/2015, (DIR. A DOCUMENTO).",
     "carros", "Fiat", "Uno Evolution 1.4", 2015),
    ("TOYOTA ETIOS HB XS 1.5, COR: PRATA, COMBUSTÍVEL; FLEX, ANO/MOD 2015/2015, (DIR A DOCUMENTO)..",
     "carros", "Toyota", "Etios Hb Xs 1.5", 2015),
    ("VW/ONIBUS 15.190 EOD ESC.SUPER, CAPACIDADE: 57 PASSAGEIROS, COR: AMARELA, COMBUSTÍVEL; DIESEL, ANO/MOD 2009/2010, (DIR. A DOCUMENTO).",
     "caminhoes", "Vw", "Onibus 15.190 Eod Esc.Super", 2010),
    ("CAMINHÃO FORD CARGO 1319, COR: PRATA, COMBUSTÍVEL; DIESEL, ANO/MOD 2013/2013, (DIR. A DOCUMENTO).",
     "caminhoes", "Ford", "Cargo 1319", 2013),
    ("FIAT DUCATO GREENCAR MO3 2.3, AMBULÂNCIA, 8 PASSAGEIROS, COR: BRANCA, COMBUSTÍVEL; DIESEL, ANO/MOD 2016/2017,(DIR. A DOCUMENTO).",
     "caminhoes", "Fiat", "Ducato Greencar Mo3 2.3, Ambulância", 2017),
    ("RETROESCAVADEIRA JBC 3C, CHASSI: 9B9214T74DBDT4663",
     "equipamentos", "Retroescavadeira", "Jbc 3C", 0),
    ("BENZ SPRINTERM 313CDI, 16 PASSAGEIROS, COR: BRANCA, COMBUSTÍVEL; DIESEL, ANO/MOD 2011/2012,  (DIR. A DOCUMENTO).",
     "caminhoes", "Benz", "Sprinterm 313Cdi", 2012),
    ("FIAT STRAD MODIFICAR AMBULÂNCIA 1.4, 5 PASSAGEIRO, COR: BRANCA, COMBUSTÍVEL; FLEX, ANO/MOD 2013/2013 (DIR. A DOCUMENTO).",
     "carros", "Fiat", "Strad Modificar Ambulância 1.4", 2013),
    ("SUCATA DE COMPRESSOR DE AR.",
     "equipamentos", "Sucata", "De Compressor De Ar", 0),
    ("SUCATAS DE ELETRÔNICAS TELEVISÕES, FONTES DE COMPUTADORES, VENTILADORES. IMPRESSORAS, AR-CONDICIONADOS E OUTROS.",
     "eletronicos", "Sucatas", None, 0),
    ("EQUIPAMENTOS HOSPITALARES E ODONTOLÓGICOS, MATERIAIS ESCOLARES; MESAS, CADEIRAS E OUTROS.",
     "eletronicos", "Equipamentos", None, 0),
    ("APARELHOS ELETRÔNICOS - COMPUTADORES, RÁDIOS, CAIXA DE SOM, IMPRESSORAS, AR-CONDICIONADO E VENTILADORES.",
     "eletronicos", "Aparelhos", None, 0),
]


class TestMjTituloECategoria:
    @pytest.mark.parametrize("titulo,categoria,marca,modelo,ano", _MJ_TITULOS)
    def test_titulos_reais(self, titulo, categoria, marca, modelo, ano):
        nome, m, mod, a = _mj_parse_titulo(titulo)
        assert (m, a) == (marca, ano)
        if modelo is not None:
            assert mod == modelo
        assert _mj_categoria(nome, m, mod) == categoria

    def test_titulo_longo_nao_fica_sem_marca(self):
        # regressao: regex {5,120} zerava marca/modelo (viravam "" e "?")
        _, marca, modelo, _ = _mj_parse_titulo(_MJ_TITULOS[2][0])
        assert marca and modelo != "?"

    def test_sem_ruido_de_cor_combustivel_chassi(self):
        for titulo, *_ in _MJ_TITULOS:
            _, _, modelo, _ = _mj_parse_titulo(titulo)
            assert not any(x in modelo.lower() for x in ("cor:", "combust", "chassi"))

    def test_titulo_vazio(self):
        assert _mj_parse_titulo("") == ("", "?", "?", 0)

    def test_cargo_de_caminhao_nao_vira_moto(self):
        assert detectar_categoria("Caminhão Ford Cargo 1319", "", "carros") == "caminhoes"
