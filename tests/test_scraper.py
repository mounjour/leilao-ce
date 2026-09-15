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
    _rf_categoria,
    _rf_eletronico_ce,
    _rf_parse_eletronico,
    _grupo_lance_categoria,
    _grupo_lance_parse_pagina,
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


class TestGrupoLanceParsePagina:
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
