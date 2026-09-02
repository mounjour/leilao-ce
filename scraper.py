from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from datetime import datetime, timedelta
import anthropic
import requests
import json
import hashlib
import html
import time
import re
import os
from urllib.parse import unquote, urlsplit
from dotenv import load_dotenv

load_dotenv()

CIDADES_CE = [
    "fortaleza","eusebio","maracanau","caucaia","juazeiro-do-norte",
    "sobral","crato","iguatu","horizonte","pacajus","aquiraz","russas"
]
CATEGORIAS = ["carros","motos","caminhoes","imoveis","equipamentos"]
URLS = [(f"https://leilo.com.br/leilao/{c}-ceara/{cat}", cat)
        for c in CIDADES_CE for cat in CATEGORIAS]

FIPE_API   = "https://parallelum.com.br/fipe/api/v1"
cliente_ia = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ICONES     = {"carros":"🚗","motos":"🏍️","caminhoes":"🚛","imoveis":"🏠","equipamentos":"⚙️"}

# ─── CATEGORIZAÇÃO REAL ───────────────────────────────────────────────────────
PALAVRAS_MOTO = ['cg ','fan ','bros','titan','pcx','fazer','crosser','biz','lead',
                 'nxr','xre',' cargo','start','ybr','pop ','cb 3','ninja','factor',
                 'twister','burgman','nmax','lander','mt-','xtz','shineray','xy150',
                 'xy125','shi 175','biz','dominar','fz15','harley','davidson',
                 'flhtcu','flht','softail','sportster','motocicleta']
PALAVRAS_CAMINHAO = ['fh ','fmx','constellation','actros','axor','atego','cargo truck',
                     'f-4000','sprinter','transit','master','daily','ducato','toco',
                     'truck','bi-truck','cavalo','carreta','reboque','semirreboque',
                     'randon','facchini','noma','guerra','librelato','volvo vm',
                     'volvo/fh','6x2t','re dl','mpolo','marcopolo','torino gvu',
                     'torino u','comil','busscar','neobus','caio','unisauto']
PALAVRAS_MAQUINA  = ['escavadeira','retroescavadeira','pa carregadeira','trator',
                     'empilhadeira','guindaste','munck','compactador','gerador',
                     'compressor','alinhador','balanceador','elevador','betoneira',
                     'motoniveladora','fotovoltaico','tkba','skf']
PALAVRAS_IMOVEL   = ['apartamento','casa ','terreno','lote ','sala comercial',
                     'galpao','barracão','prédio','sítio','fazenda','chácara',
                     'loja ','sobrado','cobertura','flat ','imóvel','imóveis',
                     'imovel','imoveis','direito de posse','vaga de garagem']

def detectar_categoria(modelo, marca, cat_url):
    nome = f"{marca} {modelo}".lower()
    if any(p in nome for p in PALAVRAS_IMOVEL):    return "imoveis"
    if any(p in nome for p in PALAVRAS_MAQUINA):   return "equipamentos"
    if any(p in nome for p in PALAVRAS_CAMINHAO):  return "caminhoes"
    if any(p in nome for p in PALAVRAS_MOTO):      return "motos"
    return cat_url

# ─── REFERÊNCIAS DE MERCADO ───────────────────────────────────────────────────
REFS = {
    "volvo fh": 350000, "volvo fm": 280000, "scania r": 320000,
    "mercedes actros": 300000, "mercedes axor": 220000, "mercedes atego": 180000,
    "iveco tector": 160000, "iveco daily": 120000, "ford cargo": 140000,
    "volkswagen constellation": 200000,
    "randon re dl": 90000, "randon reboque": 80000, "randon semirreboque": 100000,
    "facchini": 90000,
    "escavadeira": 300000, "retroescavadeira": 180000,
    "pa carregadeira": 250000, "trator": 120000,
    "empilhadeira": 60000, "gerador": 30000, "alinhador": 8000,
}

def buscar_referencia_mercado(marca, modelo):
    nome = f"{marca} {modelo}".lower()
    for k, v in REFS.items():
        if k in nome:
            return v, f"R$ {v:,.0f} (ref. mercado)"
    return 0, "Sem referência"

# ─── FIPE ─────────────────────────────────────────────────────────────────────
_STOPWORDS = {"de","da","do","dos","das","com","para","e","a","o","em","mt","cvt"}

def _score_modelo(fipe_nome: str, palavras: list) -> int:
    nome = fipe_nome.lower()
    return sum(1 for p in palavras if p in nome)

def buscar_fipe(marca, modelo, ano, categoria):
    if categoria in ["imoveis","equipamentos","caminhoes"]:
        return buscar_referencia_mercado(marca, modelo)
    endpoint = "motos" if categoria == "motos" else "carros"
    try:
        marcas = requests.get(f"{FIPE_API}/{endpoint}/marcas", timeout=8).json()
        marca_id = next((m["codigo"] for m in marcas if marca.lower() in m["nome"].lower()), None)
        if not marca_id: return 0, "Marca não encontrada"
        modelos_fipe = requests.get(f"{FIPE_API}/{endpoint}/marcas/{marca_id}/modelos", timeout=8).json()["modelos"]

        # Score-based matching: palavras do modelo que aparecem no nome FIPE
        palavras = [p for p in modelo.lower().split() if len(p) > 1 and p not in _STOPWORDS]

        def _score_fipe(fipe_nome):
            nome = fipe_nome.lower()
            acertos = sum(1 for p in palavras if p in nome)
            if acertos == 0:
                return 0
            # Penaliza modelos com muitas palavras extras que não estão no nosso modelo
            palavras_fipe = [p for p in nome.split() if len(p) > 1 and p not in _STOPWORDS]
            extras = max(0, len(palavras_fipe) - len(palavras))
            return acertos * 10 - extras

        scored = [(m, _score_fipe(m["nome"])) for m in modelos_fipe]
        scored = [(m, s) for m, s in scored if s > 0]
        if not scored: return 0, "Modelo não encontrado"
        # Maior score; em empate, nome mais longo (variante mais específica/completa)
        melhor = max(scored, key=lambda x: (x[1], len(x[0]["nome"])))
        modelo_id = melhor[0]["codigo"]

        anos_f = requests.get(f"{FIPE_API}/{endpoint}/marcas/{marca_id}/modelos/{modelo_id}/anos", timeout=8).json()
        # Ano exato primeiro; depois ano mais próximo
        ano_id = next((a["codigo"] for a in anos_f if str(ano) in a["nome"]), None)
        if not ano_id:
            try:
                anos_num = [(abs(int(re.search(r'\d{4}', a["nome"]).group()) - ano), a["codigo"])
                            for a in anos_f if re.search(r'\d{4}', a["nome"])]
                ano_id = min(anos_num)[1] if anos_num else anos_f[0]["codigo"]
            except:
                ano_id = anos_f[0]["codigo"]

        dados = requests.get(f"{FIPE_API}/{endpoint}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}", timeout=8).json()
        return float(dados["Valor"].replace("R$ ","").replace(".","").replace(",",".").strip()), dados["Valor"]
    except:
        return 0, "FIPE indisponível"

# ─── CLASSIFICAÇÃO ────────────────────────────────────────────────────────────
def classificar(lance, ref, estado):
    if estado in ["SINISTRADO","BATIDO","SUCATA"]: return "⚠️ INSPECIONAR"
    if ref == 0 or lance == 0: return "Sem referência"
    pct = (lance / ref) * 100
    if pct <= 50:   return "✅ ÓTIMO"
    elif pct <= 75: return "⚠️ MEDIANO"
    else:           return "❌ RUIM"

def oportunidade_preco(lance, ref, estado):
    """Calcula oportunidade sem consumir tokens e sempre usa o lance atual."""
    if estado in ["SINISTRADO", "BATIDO", "SUCATA"]:
        return "INSPECIONAR"
    if ref <= 0 or lance <= 0:
        return "INSPECIONAR"
    pct = (lance / ref) * 100
    if pct <= 50:
        return "OTIMA"
    if pct <= 75:
        return "BOA"
    if pct <= 100:
        return "REGULAR"
    return "RUIM"

# ─── ANÁLISE IA ───────────────────────────────────────────────────────────────
_IA_ATIVA = True  # circuit breaker: False quando créditos esgotam

_FALLBACK_IA = {"estado":"NAO_INFORMADO","selo":"⚪ Não informado","oportunidade":"INSPECIONAR",
                "uso_sugerido":"verificar presencialmente","positivos":[],"negativos":[],
                "avaliacao_plataforma":"Sem dados. Recomendamos inspeção antes do leilão."}

_HISTORICO_TOKENS_FILE = "historico_tokens_ia.jsonl"
_METRICAS_IA = {}


def _reset_metricas_ia():
    """Zera as métricas antes de cada execução completa do scraper."""
    _METRICAS_IA.clear()
    _METRICAS_IA.update({
        "api_tentativas": 0,
        "api_sucessos": 0,
        "api_erros": 0,
        "cache_hits": 0,
        "sem_dados": 0,
        "circuit_breaker": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    })


def _registrar_uso_ia(resposta):
    """Soma os números oficiais retornados no campo usage da Anthropic."""
    uso = resposta.usage
    _METRICAS_IA["api_sucessos"] += 1
    _METRICAS_IA["input_tokens"] += int(
        getattr(uso, "input_tokens", 0) or 0
    )
    _METRICAS_IA["output_tokens"] += int(
        getattr(uso, "output_tokens", 0) or 0
    )
    _METRICAS_IA["cache_creation_input_tokens"] += int(
        getattr(uso, "cache_creation_input_tokens", 0) or 0
    )
    _METRICAS_IA["cache_read_input_tokens"] += int(
        getattr(uso, "cache_read_input_tokens", 0) or 0
    )


def _salvar_resumo_ia(total_lotes):
    """Exibe e salva uma linha comparável para cada execução."""
    input_total = (
        _METRICAS_IA["input_tokens"]
        + _METRICAS_IA["cache_creation_input_tokens"]
        + _METRICAS_IA["cache_read_input_tokens"]
    )
    total_tokens = input_total + _METRICAS_IA["output_tokens"]
    decisoes = (
        _METRICAS_IA["cache_hits"]
        + _METRICAS_IA["api_tentativas"]
        + _METRICAS_IA["sem_dados"]
        + _METRICAS_IA["circuit_breaker"]
    )
    taxa_cache = (
        (_METRICAS_IA["cache_hits"] / decisoes) * 100
        if decisoes else 0.0
    )
    tokens_por_chamada = (
        total_tokens / _METRICAS_IA["api_sucessos"]
        if _METRICAS_IA["api_sucessos"] else 0.0
    )

    resumo = {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "total_lotes": total_lotes,
        **_METRICAS_IA,
        "input_total": input_total,
        "total_tokens": total_tokens,
        "taxa_cache_pct": round(taxa_cache, 2),
        "tokens_por_chamada": round(tokens_por_chamada, 2),
    }

    print("\n📊 RESUMO DE USO DA IA")
    print(f"  Lotes processados: {total_lotes}")
    print(f"  Chamadas tentadas: {_METRICAS_IA['api_tentativas']}")
    print(f"  Chamadas com resposta: {_METRICAS_IA['api_sucessos']}")
    print(f"  Erros de IA/JSON: {_METRICAS_IA['api_erros']}")
    print(f"  Reutilizados do cache: {_METRICAS_IA['cache_hits']}")
    print(f"  Ignorados sem dados úteis: {_METRICAS_IA['sem_dados']}")
    print(f"  Ignorados pelo circuit breaker: {_METRICAS_IA['circuit_breaker']}")
    print(f"  Taxa de reaproveitamento: {taxa_cache:.1f}%")
    print(f"  Tokens de entrada: {input_total}")
    print(f"  Tokens de saída: {_METRICAS_IA['output_tokens']}")
    print(f"  Total de tokens: {total_tokens}")
    print(f"  Média por chamada: {tokens_por_chamada:.1f}")

    try:
        with open(_HISTORICO_TOKENS_FILE, "a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(resumo, ensure_ascii=False) + "\n")
        print(f"  Histórico salvo em {_HISTORICO_TOKENS_FILE}")
    except Exception as e:
        print(f"  ⚠️ Não foi possível salvar o histórico de tokens: {e}")


_reset_metricas_ia()


def analisar(marca, modelo, ano, desc, km, lance, ref, categoria):
    global _IA_ATIVA
    if not _IA_ATIVA:
        _METRICAS_IA["circuit_breaker"] += 1
        return _FALLBACK_IA.copy()

    # Sem descrição nem quilometragem, a IA só produziria uma análise genérica.
    # Evitar a chamada economiza tokens sem perder informação concreta.
    if not str(desc or "").strip() and not str(km or "").strip():
        _METRICAS_IA["sem_dados"] += 1
        return _FALLBACK_IA.copy()

    try:
        _METRICAS_IA["api_tentativas"] += 1
        r = cliente_ia.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=220,
            messages=[{"role":"user","content":f"""Analise somente o estado e os riscos deste item de leilão brasileiro.
Item: {marca} {modelo} {ano}; categoria: {categoria}; km: {km or 'não informado'}.
Descrição: {desc or 'sem descrição'}
Não avalie lance, preço, FIPE, desconto ou ROI. Não invente danos ausentes da descrição.
Para recuperado de financiamento, recomende verificar restrições. Para caminhão ou equipamento, considere manutenção e vida útil.
Responda apenas JSON:
{{"estado":"BOM|BATIDO|SINISTRADO|RECUPERADO_FINANCIAMENTO|SUCATA|NAO_INFORMADO","selo":"🟢 Bom estado|🟡 Batido|🔴 Sinistrado|🔵 Rec. Financiamento|⚫ Sucata|⚪ Não informado","uso_sugerido":"texto curto","positivos":["até 2"],"negativos":["até 2"],"avaliacao_plataforma":"1 frase objetiva"}}"""}]
        )
        _registrar_uso_ia(r)
        texto = r.content[0].text.strip()
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        dados = json.loads(match.group() if match else texto)

        # Mantém o formato esperado pelo restante do sistema. A oportunidade
        # financeira continua sendo calculada localmente por classificar().
        dados.setdefault("estado", "NAO_INFORMADO")
        dados.setdefault("selo", "⚪ Não informado")
        dados.setdefault("oportunidade", "INSPECIONAR")
        dados.setdefault("uso_sugerido", "")
        dados.setdefault("positivos", [])
        dados.setdefault("negativos", [])
        dados.setdefault("avaliacao_plataforma", "")
        return dados
    except Exception as e:
        _METRICAS_IA["api_erros"] += 1
        msg = str(e)
        if "credit balance is too low" in msg or "insufficient_quota" in msg:
            _IA_ATIVA = False
            print("  ⚠️ IA desativada: créditos Anthropic esgotados. Recarregue em console.anthropic.com")
        else:
            print(f"  ⚠️ IA error: {e}")
        return _FALLBACK_IA.copy()

_CACHE_FILE = "analises_ia_cache.json"
_CACHE_VERSION = 2
_CACHE_ANALISE: dict = {}


def _normalizar_texto(valor) -> str:
    texto = unquote(str(valor or "")).lower().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _normalizar_url(url: str) -> str:
    """
    Remove query string, fragmento e diferenças de barra final.

    Exemplo:
    https://site.com/lote/123/?utm_source=x
    https://site.com/lote/123

    passam a representar o mesmo lote.
    """
    try:
        partes = urlsplit(url.strip())

        host = partes.netloc.lower().replace("www.", "")
        caminho = re.sub(r"/+", "/", partes.path).rstrip("/")

        return f"{host}{caminho}"
    except Exception:
        return url.strip().lower().rstrip("/")


def _id_veiculo(url: str) -> str:
    """
    Identificador persistente do lote.

    Não use somente marca/modelo/ano, pois podem existir vários veículos
    iguais no mesmo leilão.
    """
    url_normalizada = _normalizar_url(url)

    return hashlib.sha256(
        url_normalizada.encode("utf-8")
    ).hexdigest()


def _hash_dados_veiculo(
    marca,
    modelo,
    ano,
    descricao,
    km,
    categoria,
) -> str:
    """
    Detecta alterações relevantes no veículo.

    Lance e FIPE não entram no hash porque a avaliação de preço já é
    calculada localmente por classificar().
    """
    dados = {
        "cache_version": _CACHE_VERSION,
        "marca": _normalizar_texto(marca),
        "modelo": _normalizar_texto(modelo),
        "ano": int(ano or 0),
        "descricao": _normalizar_texto(descricao),
        "km": _normalizar_texto(km),
        "categoria": _normalizar_texto(categoria),
    }

    serializado = json.dumps(
        dados,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serializado.encode("utf-8")
    ).hexdigest()


def _load_analise_cache():
    global _CACHE_ANALISE

    _CACHE_ANALISE = {}

    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)

            if isinstance(dados, dict):
                _CACHE_ANALISE = dados

            print(f"[cache IA] {len(_CACHE_ANALISE)} análises carregadas")
            return
        except Exception as e:
            print(f"[cache IA] erro ao carregar {_CACHE_FILE}: {e}")

    # Migração inicial: reaproveita análises que já foram pagas e estão no
    # leiloes.json. Depois disso, o cache dedicado passa a ser usado.
    if not os.path.exists("leiloes.json"):
        print("[cache IA] nenhum cache anterior encontrado")
        return

    try:
        with open("leiloes.json", "r", encoding="utf-8") as arquivo:
            lotes_anteriores = json.load(arquivo)

        for lote in lotes_anteriores:
            url = lote.get("url", "")
            avaliacao = lote.get("avaliacao_plataforma", "")
            if not url or not avaliacao:
                continue

            veiculo_id = _id_veiculo(url)
            dados_hash = _hash_dados_veiculo(
                marca=lote.get("marca", ""),
                modelo=lote.get("modelo", ""),
                ano=lote.get("ano", 0),
                descricao=lote.get("descricao", ""),
                km=lote.get("km", ""),
                categoria=lote.get("categoria", ""),
            )

            _CACHE_ANALISE[veiculo_id] = {
                "cache_version": _CACHE_VERSION,
                "url": _normalizar_url(url),
                "dados_hash": dados_hash,
                "analisado_em": lote.get("scraped_at", "migrado"),
                "analise": {
                    "estado": lote.get("estado", "NAO_INFORMADO"),
                    "selo": lote.get("estado_selo", "⚪ Não informado"),
                    "oportunidade": lote.get("oportunidade", "INSPECIONAR"),
                    "uso_sugerido": lote.get("uso_sugerido", ""),
                    "positivos": lote.get("positivos", []),
                    "negativos": lote.get("negativos", []),
                    "avaliacao_plataforma": avaliacao,
                },
            }

        if _CACHE_ANALISE:
            _save_analise_cache()
        print(f"[cache IA] {len(_CACHE_ANALISE)} análises migradas de leiloes.json")
    except Exception as e:
        print(f"[cache IA] erro na migração: {e}")
        _CACHE_ANALISE = {}


def _save_analise_cache():
    """
    Grava primeiro em arquivo temporário para reduzir o risco de
    corromper o cache caso o scraper seja interrompido.
    """
    temporario = f"{_CACHE_FILE}.tmp"

    try:
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(
                _CACHE_ANALISE,
                arquivo,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temporario, _CACHE_FILE)

    except Exception as e:
        print(f"[cache IA] erro ao salvar: {e}")

        try:
            if os.path.exists(temporario):
                os.remove(temporario)
        except Exception:
            pass


def _analisar_cached(
    url,
    marca,
    modelo,
    ano,
    desc,
    km,
    lance,
    ref,
    categoria,
):
    veiculo_id = _id_veiculo(url)

    dados_hash = _hash_dados_veiculo(
        marca=marca,
        modelo=modelo,
        ano=ano,
        descricao=desc,
        km=km,
        categoria=categoria,
    )

    cached = _CACHE_ANALISE.get(veiculo_id)

    if (
        cached
        and cached.get("cache_version") == _CACHE_VERSION
        and cached.get("dados_hash") == dados_hash
        and isinstance(cached.get("analise"), dict)
    ):
        _METRICAS_IA["cache_hits"] += 1
        print(
            f"  ♻️ IA reutilizada: {marca} {modelo} {ano}"
        )
        return cached["analise"]

    print(
        f"  🤖 Nova análise IA: {marca} {modelo} {ano}"
    )

    analise = analisar(
        marca,
        modelo,
        ano,
        desc,
        km,
        lance,
        ref,
        categoria,
    )

    # Não guardar falhas temporárias ou falta de créditos.
    if analise == _FALLBACK_IA:
        return analise

    _CACHE_ANALISE[veiculo_id] = {
        "cache_version": _CACHE_VERSION,
        "url": _normalizar_url(url),
        "dados_hash": dados_hash,
        "analisado_em": datetime.now().isoformat(
            timespec="minutes"
        ),
        "analise": analise,
    }

    # Salva imediatamente. Assim, se o mesmo veículo reaparecer durante
    # a execução atual, ele já estará no cache.
    _save_analise_cache()

    return analise

def limpar_modelo(raw):
    m = unquote(raw)
    return re.sub(r'\(.*?\)', '', m).replace("-", " ").strip().title()

def _lote_dict(fonte, categoria, marca, modelo, ano, cidade, lance,
               ref_val, ref_str, classif, foto, km, descricao, analise, url, data_leilao=""):
    return {
        "fonte":                fonte,
        "categoria":            categoria,
        "icone":                ICONES.get(categoria, "📦"),
        "marca":                marca,
        "modelo":               modelo,
        "ano":                  ano,
        "cidade":               cidade,
        "lance_atual":          lance,
        "fipe_valor":           ref_val,
        "fipe_str":             ref_str,
        "classificacao":        classif,
        "foto":                 foto,
        "km":                   km,
        "descricao":            descricao,
        "estado":               analise.get("estado", "NAO_INFORMADO"),
        "estado_selo":          analise.get("selo", "⚪ Não informado"),
        "oportunidade":         oportunidade_preco(lance, ref_val, analise.get("estado", "")),
        "uso_sugerido":         analise.get("uso_sugerido", ""),
        "positivos":            analise.get("positivos", []),
        "negativos":            analise.get("negativos", []),
        "avaliacao_plataforma": analise.get("avaliacao_plataforma", ""),
        "url":                  url,
        "data_leilao":          data_leilao,
        "scraped_at":           datetime.now().strftime("%Y-%m-%dT%H:%M"),
    }

def _parse_brl(s):
    try:
        return float(s.replace("R$","").replace("\xa0","").replace(" ","")
                      .replace(".","").replace(",",".").strip())
    except:
        return 0

def _extrair_lance(texto):
    # Prioridade 1: valor após "Lance Atual" ou "Lance Mínimo" — aceita qualquer valor > 0
    m = re.search(
        r'lance\s+(?:atual|m[ií]nimo)[^\d]{0,40}R\$[\xa0\s]*([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})',
        texto, re.IGNORECASE | re.DOTALL
    )
    if m:
        v = _parse_brl(m.group(1))
        if v > 0:
            return v

    # Prioridade 2: valor logo após qualquer palavra "lance" — aceita qualquer valor > 0
    m = re.search(
        r'\blance\b[^\d]{0,60}R\$[\xa0\s]*([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})',
        texto, re.IGNORECASE | re.DOTALL
    )
    if m:
        v = _parse_brl(m.group(1))
        if v > 0:
            return v

    # Fallback: primeiro valor >= 500 (sem contexto de "lance", filtra taxas pequenas)
    valores = []
    for raw in re.findall(r'R\$[\xa0\s]*[\d]{1,3}(?:\.[\d]{3})*,[\d]{2}', texto):
        v = _parse_brl(raw)
        if v >= 500:
            valores.append(v)
    if valores:
        return valores[0]
    return 0

def _extrair_foto(html, dominios=('cdndp.com.br',)):
    # A CDN do Leilo serve um placeholder fixo (mesma URL em todos os lotes,
    # sem "_media" no nome) para foto ausente/pendente — como o nome não tem
    # nenhuma das palavras-chave abaixo, ele passava pelo filtro e virava a
    # "foto" do card. Fotos reais dos lotes sempre têm "_media" no nome.
    # "leilomaster" tambem exclui: e o dominio antigo (pre-rebranding pra
    # Leilo) que ainda aparece no cabecalho de algumas paginas — sem essa
    # exclusao, uma corrida entre esse dominio e a galeria de fotos real
    # (que carrega via JS, mais devagar) podia fazer o regex pegar a logo
    # antiga em vez da foto do lote.
    for dom in dominios:
        pat = rf'https?://[^\s"\']+{re.escape(dom)}[^\s"\']*\.(?:jpg|jpeg|png|webp)'
        for f in re.findall(pat, html, re.IGNORECASE):
            fl = f.lower()
            if '_media' in fl and not any(x in fl for x in ['logo','icon','avatar','banner','no-image','leilomaster']):
                return f
    return ""

def _extrair_km(texto):
    for m in re.findall(r'([\d]{2,3}\.[\d]{3})\s*km', texto, re.IGNORECASE):
        if int(m.replace(".","")) >= 1000:
            return f"{m} km"
    return ""

def _extrair_descricao(texto):
    for linha in texto.split('\n'):
        l = linha.strip()
        if any(p in l.lower() for p in ['recuperado','sinistro','batido',
               'financiamento','conservado','sucata','alienado']) and len(l) > 20:
            return l[:200]
    return ""

_MESES_PT = {
    'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,
    'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12,
}

def _extrair_data_leilao(texto):
    # Mega: "1ª Praça: 28/05/2026 às 10:30"
    m = re.search(r'1[ªa]\s*Pra[çc]a:\s*(\d{2}/\d{2}/\d{4})\s*[àa]s?\s*(\d{2}:\d{2})', texto, re.IGNORECASE)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M").strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Pacto: "Finaliza em 18h3m42s" (leilão já em andamento) ou
    # "Leilão inicia em 1 dia 2h14m12s" (ainda não começou — o site trocou
    # a frase e passou a incluir dias, o regex antigo só cobria h/m/s e
    # nunca mais batia com nada, deixando data_leilao vazio em todo lote).
    m = re.search(
        r'(?:Finaliza em|Leil[ãa]o inicia em)\s*(?:(\d+)\s*dias?)?\s*(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?',
        texto, re.IGNORECASE
    )
    if m and any(m.group(i) for i in range(1, 5)):
        try:
            dt = datetime.now() + timedelta(
                days=int(m.group(1) or 0),
                hours=int(m.group(2) or 0),
                minutes=int(m.group(3) or 0),
                seconds=int(m.group(4) or 0)
            )
            return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Leilo: countdown "X dias Y horas Z min" (ou "X dia Y hora")
    m = re.search(r'(\d+)\s*dia[s]?\D{1,10}(\d+)\s*hora[s]?\D{1,10}(\d+)\s*min', texto, re.IGNORECASE)
    if m:
        try:
            dt = datetime.now() + timedelta(
                days=int(m.group(1)), hours=int(m.group(2)), minutes=int(m.group(3))
            )
            return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Leilo: countdown "X dias Y horas" (sem minutos)
    m = re.search(r'(\d+)\s*dia[s]?\D{1,10}(\d+)\s*hora[s]?', texto, re.IGNORECASE)
    if m:
        try:
            dt = datetime.now() + timedelta(days=int(m.group(1)), hours=int(m.group(2)))
            return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Genérico: "DD de mês de YYYY ... HH:MM"
    m = re.search(
        r'(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4}).*?(\d{2}:\d{2})',
        texto, re.IGNORECASE | re.DOTALL
    )
    if m:
        try:
            mes = _MESES_PT.get(m.group(2).lower().replace('ç','c'), 0)
            if mes:
                dt = datetime(int(m.group(3)), mes, int(m.group(1)),
                              int(m.group(4)[:2]), int(m.group(4)[3:]))
                return dt.strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Genérico: "DD/MM/YYYY" próximo de horário — texto completo, aceita multilinha
    m = re.search(r'(\d{2}/\d{2}/\d{4})\D{0,30}(\d{2}:\d{2})', texto, re.DOTALL)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M").strftime("%Y-%m-%dT%H:%M")
        except:
            pass
    # Fallback: "DD/MM/YYYY" sem horário (Celso Cunha e similares) — assume 09:00
    m = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', texto)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%Y-%m-%dT09:00")
        except:
            pass
    return ""

# ─── SCRAPER LEILO.COM.BR ─────────────────────────────────────────────────────
def _raspar_leilo(pg_lista, pg_detalhe, vistos):
    lotes = []
    for url_base, cat_url in URLS:
        try:
            pg_lista.goto(url_base, timeout=15000, wait_until="domcontentloaded")
            pg_lista.wait_for_timeout(4000)
        except:
            continue

        for _ in range(5):
            pg_lista.keyboard.press("End")
            pg_lista.wait_for_timeout(2000)

        # Extrai data do evento da listagem — fallback para todos os lotes desta página
        try:
            data_evento = _extrair_data_leilao(pg_lista.inner_text('body'))
        except:
            data_evento = ""

        hrefs = []
        for link in pg_lista.query_selector_all('a'):
            try:
                href = link.get_attribute('href') or ''
                if '/leilao/' in href and 'ano.' in href and href not in vistos:
                    vistos.add(href); hrefs.append(href)
            except:
                continue

        if not hrefs:
            continue
        print(f"📡 Leilo {url_base.split('/leilao/')[1]} | {len(hrefs)} lotes")

        for href in hrefs[:30]:
            try:
                pts      = href.strip('/').split('/')
                cidade   = pts[1].replace("-ceara","").replace("-"," ").title() if len(pts)>1 else "?"
                marca    = pts[3].title() if len(pts)>3 else "?"
                modelo   = limpar_modelo(pts[4]) if len(pts)>4 else "?"
                ano_str  = pts[5].replace("ano.","") if len(pts)>5 else "0"
                ano      = int(ano_str) if ano_str.isdigit() else 0
                url_lote = f"https://leilo.com.br{href}"
                categoria = detectar_categoria(modelo, marca, cat_url)

                try:
                    pg_detalhe.goto(url_lote, timeout=12000, wait_until="domcontentloaded")
                    # A galeria de fotos do lote carrega via JS depois do resto da
                    # pagina — com so 2s de espera, as vezes ainda nao tinha
                    # renderizado nenhuma foto real, e o _extrair_foto caia pra
                    # uma logo antiga da epoca "LeiloMaster" que sobrou no cabecalho
                    # da pagina (mesmo dominio cdndp.com.br, mas nao e foto do lote).
                    pg_detalhe.wait_for_timeout(4500)
                    texto = pg_detalhe.inner_text('body')
                    html  = pg_detalhe.content()
                except:
                    texto, html = "", ""

                lance     = _extrair_lance(texto)
                foto      = _extrair_foto(html, ('leilo.cdndp.com.br', 'cdndp.com.br'))
                km        = _extrair_km(texto)
                descricao = _extrair_descricao(texto)

                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = _analisar_cached(url_lote, marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado",""))

                icone = ICONES.get(categoria, "📦")
                data_leilao = _extrair_data_leilao(texto) or data_evento
                print(f"  {icone} [Leilo/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {analise['selo']} | {classif} | {data_leilao or 'sem data'}")

                lotes.append(_lote_dict("leilo", categoria, marca, modelo, ano,
                                        cidade+"/CE", lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠️ Leilo: {e}"); continue

    return lotes

# ─── SCRAPER MEGA LEILÕES ─────────────────────────────────────────────────────
_MEGA_URLS = [
    "https://www.megaleiloes.com.br/veiculos/ce",
    "https://www.megaleiloes.com.br/imoveis/ce",
]
_MEGA_CAT = {
    "carros":"carros","motos":"motos","caminhoes":"caminhoes","pesados":"caminhoes",
    "casas":"imoveis","imoveis":"imoveis","imoveis-comerciais":"imoveis",
    "terrenos":"imoveis","apartamentos":"imoveis","predios":"imoveis",
}

def _parse_mega_lot(href, titulo):
    path   = href.replace("https://www.megaleiloes.com.br","").split("?")[0]
    parts  = [p for p in path.split("/") if p]
    tipo   = parts[0] if parts else "veiculos"
    subcat = parts[1] if len(parts) > 1 else "carros"
    cidade = parts[3].replace("-"," ").title() if len(parts) > 3 else "?"
    slug   = parts[4] if len(parts) > 4 else ""

    categoria = "imoveis" if tipo == "imoveis" else _MEGA_CAT.get(subcat, "carros")

    if categoria == "imoveis":
        return categoria, cidade, "Imóvel", titulo, 0

    slug = re.sub(r'-[a-z]\d+$', '', slug)
    slug = re.sub(r'^(?:carro|moto|caminhao|veiculo)-', '', slug)

    ano = 0
    m8 = re.search(r'(\d{4})(\d{4})', slug)
    if m8:
        ano  = int(m8.group(2))
        slug = slug.replace(m8.group(0), "").strip("-")
    else:
        m4 = re.search(r'(\d{4})', slug)
        if m4 and 1980 <= int(m4.group(1)) <= 2030:
            ano  = int(m4.group(1))
            slug = slug.replace(m4.group(0), "").strip("-")

    parts_s = [p for p in slug.split("-") if p]
    marca  = parts_s[0].title() if parts_s else "?"
    modelo = " ".join(p.title() for p in parts_s[1:]) if len(parts_s) > 1 else "?"
    return categoria, cidade, marca, modelo, ano

def _raspar_mega(pg, vistos):
    lotes = []
    for url_base in _MEGA_URLS:
        for pagina in range(1, 15):
            url = f"{url_base}?pagina={pagina}"
            try:
                pg.goto(url, timeout=15000, wait_until="networkidle")
                pg.wait_for_timeout(2000)
            except:
                break

            # `.card open` = pregão rodando; `.card waiting` = "EM BREVE"
            # (1ª praça no futuro). Antes só pegava `.open` e todo lote
            # futuro do Mega era descartado.
            cards = pg.query_selector_all('.card.open, .card.waiting')
            if not cards:
                break
            print(f"📡 Mega {url_base.split('/')[-1]} p.{pagina} | {len(cards)} cards")

            antes = len(lotes)
            for card in cards:
                try:
                    title_el = card.query_selector('.card-title')
                    price_el = card.query_selector('.card-price')
                    img_el   = card.query_selector('.card-image')
                    if not title_el:
                        continue

                    href = (title_el.get_attribute('href') or '').split('?')[0]
                    if not href or href in vistos:
                        continue
                    vistos.add(href)

                    titulo    = title_el.inner_text().strip()
                    preco_str = price_el.inner_text().strip() if price_el else ""
                    lance     = _extrair_lance(preco_str) or _extrair_lance(pg.inner_text('body'))

                    foto = ""
                    if img_el:
                        bg = img_el.get_attribute('data-bg') or ""
                        if bg and 'no-image' not in bg:
                            foto = bg

                    categoria, cidade, marca, modelo, ano = _parse_mega_lot(href, titulo)
                    icone = ICONES.get(categoria, "📦")

                    ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                    analise = _analisar_cached(href, marca, modelo, ano, "", "", lance, ref_val, categoria)
                    classif = classificar(lance, ref_val, analise.get("estado",""))

                    data_leilao = _extrair_data_leilao(card.inner_text())
                    print(f"  {icone} [Mega/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                    lotes.append(_lote_dict("mega", categoria, marca, modelo, ano,
                                            f"{cidade}/CE", lance, ref_val, ref_str,
                                            classif, foto, "", "", analise, href, data_leilao))
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  ⚠️ Mega: {e}"); continue

            # Se a pagina nao trouxe nenhum lote novo, o site ja clampou pra
            # ultima pagina (ele repete a p.1 pra `?pagina=N` fora do range)
            # — parar em vez de repetir goto ate `range(1, 15)` acabar.
            if len(lotes) == antes:
                break

    return lotes

# ─── SCRAPER PACTO LEILÕES ────────────────────────────────────────────────────
_PACTO_CIDADES = ["fortaleza","eusebio","maracanau","caucaia","horizonte",
                  "pacajus","aquiraz","russas","juazeiro-do-norte","sobral"]
_PACTO_CAT_MAP = {
    "carros":"carros","motos":"motos","pesados":"caminhoes",
    "utilitarios":"caminhoes","sucatas":"carros","imoveis":"imoveis",
}

def _raspar_pacto(pg, _pg_d, vistos):
    lotes = []
    for cidade in _PACTO_CIDADES:
        url_base = f"https://www.pactoleiloes.com.br/leilao/{cidade}-ceara"
        try:
            pg.goto(url_base, timeout=20000, wait_until="networkidle")
            pg.wait_for_timeout(2000)
        except:
            continue

        for _ in range(6):
            pg.keyboard.press("End")
            pg.wait_for_timeout(700)

        # Concatena todos os textos de links com mesmo href (preço, km, data ficam juntos).
        # A foto do card é um background-image em div.q-img__image (componente Quasar),
        # não uma tag <img> — precisa ler o style em vez de src.
        items = pg.eval_on_selector_all(
            'a[href*="/leilao/"][href*="/ano."]',
            '''els => {
                const acc = {};
                for (const e of els) {
                    const h = e.href;
                    if (!acc[h]) acc[h] = {text: "", foto: ""};
                    acc[h].text += " " + e.innerText.trim();
                    if (!acc[h].foto) {
                        const imgDiv = e.querySelector(".q-img__image");
                        const bg = imgDiv ? imgDiv.style.backgroundImage : "";
                        const m = bg.match(/url\\(["']?([^"')]+)["']?\\)/);
                        if (m) acc[h].foto = m[1];
                    }
                }
                return Object.entries(acc).map(([href, v]) => (
                    {href, text: v.text.trim(), foto: v.foto}
                ));
            }'''
        )
        novos = [it for it in items if it['href'] not in vistos and '/ano.' in it['href']]
        for it in novos:
            vistos.add(it['href'])

        if not novos:
            continue
        print(f"📡 Pacto {cidade} | {len(novos)} lotes")

        for it in novos[:50]:
            href = it['href']
            try:
                pts       = href.replace('https://www.pactoleiloes.com.br','').strip('/').split('/')
                if len(pts) < 6:
                    continue
                cidade_s  = pts[1].replace("-ceara","").replace("-"," ").title()
                cat_url   = pts[2]
                marca     = pts[3].title() if len(pts) > 3 else "?"
                modelo    = limpar_modelo(pts[4]) if len(pts) > 4 else "?"
                ano_str   = pts[5].replace("ano.","") if len(pts) > 5 else "0"
                ano       = int(ano_str) if ano_str.isdigit() else 0
                categoria = detectar_categoria(modelo, marca, _PACTO_CAT_MAP.get(cat_url, cat_url))
                icone     = ICONES.get(categoria, "📦")

                # Extrai lance do texto do card (sem navegar ao detalhe)
                lance = _extrair_lance(it['text'])
                km    = _extrair_km(it['text'])

                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = _analisar_cached(href, marca, modelo, ano, "", km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado",""))

                data_leilao = _extrair_data_leilao(it['text'])
                foto = it.get('foto', '')
                # A Pacto usa /lote/fotos-modelo/<categoria>.webp como imagem
                # generica ("Fotos em breve") quando o lote nao tem foto real
                # cadastrada — carrega com sucesso (nao e "quebrada"), so nao
                # e do veiculo, entao trata como se nao houvesse foto.
                if '/fotos-modelo/' in foto:
                    foto = ''
                print(f"  {icone} [Pacto/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {analise['selo']} | {classif}")
                lotes.append(_lote_dict("pacto", categoria, marca, modelo, ano,
                                        f"{cidade_s}/CE", lance, ref_val, ref_str,
                                        classif, foto, km, "", analise, href, data_leilao))
                time.sleep(0.1)
            except Exception as e:
                print(f"  ⚠️ Pacto: {e}"); continue

    return lotes

# ─── SCRAPER MJ LEILÕES ──────────────────────────────────────────────────────
_MJ_BASE    = "https://www.mjleiloes.com.br"
_MJ_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36"}
_MJ_CE      = ['ceará','ceara','/ce','-ce','ce-','pacujá','pacuja','juazeiro',
               'fortaleza','caucaia','maracanau','sobral','crato','eusebio',
               'horizonte','pacajus','aquiraz','russas']

def _raspar_mj_leiloes(vistos):
    lotes = []
    try:
        r = requests.get(f"{_MJ_BASE}/leiloes", headers=_MJ_HEADERS, timeout=20)
        html_list = r.text
    except Exception as e:
        print(f"⚠️ MJLeiloes: {e}")
        return lotes

    auction_ids = list(dict.fromkeys(re.findall(r'/leiloes/(\d+)', html_list)))
    if not auction_ids:
        print("⚠️ MJLeiloes: nenhum leilão encontrado")
        return lotes

    for auction_id in auction_ids:
        url_auction = f"{_MJ_BASE}/leiloes/{auction_id}"
        try:
            r = requests.get(url_auction, headers=_MJ_HEADERS, timeout=20)
            html_auction = r.text
        except Exception as e:
            print(f"  ⚠️ MJLeiloes {url_auction}: {e}")
            continue

        titulo_pg = re.sub(r'<[^>]+>', ' ', html_auction[:3000])
        if not any(c in titulo_pg.lower() for c in _MJ_CE):
            continue

        title_m = re.search(r'<title[^>]*>([^<]+)</title>', html_auction, re.I)
        titulo  = title_m.group(1).strip() if title_m else f"Leilão {auction_id}"
        print(f"📡 MJLeiloes | leilão {auction_id} (CE): {titulo[:70]}")

        lot_paths = list(dict.fromkeys(re.findall(r'/lote/\d+/[^"\'<>\s]+', html_auction)))
        if not lot_paths:
            print(f"  ⚠️ MJLeiloes: nenhum lote encontrado em leilão {auction_id}")
            continue

        print(f"  {len(lot_paths)} lotes encontrados")

        for lot_path in lot_paths[:60]:
            url_lote = _MJ_BASE + lot_path
            if url_lote in vistos:
                continue
            vistos.add(url_lote)
            try:
                r = requests.get(url_lote, headers=_MJ_HEADERS, timeout=15)
                html_lote = r.text
                texto = re.sub(r'<[^>]+>', ' ', html_lote)
                texto = re.sub(r'\s+', ' ', texto).strip()

                # Título do lote: "Volkswagen Saveiro ..., Ano/Mod 2012/2013"
                h_m = re.search(r'<h[12][^>]*>\s*([^<]{5,120})\s*</h[12]>', html_lote, re.I)
                titulo_lote = h_m.group(1).strip() if h_m else ""

                ano = 0
                ano_m = re.search(r'Ano[/\s]+Mod[^\d]*(\d{4})[/\s]*(\d{4})?', titulo_lote, re.I)
                if ano_m:
                    ano = int(ano_m.group(2) or ano_m.group(1))
                    titulo_lote = titulo_lote[:titulo_lote.lower().find('ano')].strip().rstrip(',')
                else:
                    ano_m2 = re.search(r'\b(19[89]\d|20[012]\d)\b', titulo_lote + ' ' + texto[:300])
                    if ano_m2:
                        ano = int(ano_m2.group())

                partes = titulo_lote.split(' ', 1)
                marca  = partes[0].title() if partes else "?"
                modelo = partes[1].title() if len(partes) > 1 else "?"

                lance      = _extrair_lance(texto)
                km         = _extrair_km(texto)
                descricao  = _extrair_descricao(texto)
                data_leilao = _extrair_data_leilao(texto)

                fotos = re.findall(
                    r'https://static\.suporteleiloes\.com\.br[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)',
                    html_lote, re.I
                )
                foto = next((f for f in fotos if not any(
                    x in f.lower() for x in ['logo','icon','avatar','banner','thumb']
                )), "")

                cidade = "CE"
                for c in CIDADES_CE:
                    if c.replace('-', ' ') in texto.lower():
                        cidade = c.replace('-', ' ').title() + '/CE'
                        break
                if cidade == "CE":
                    m_cid = re.search(r'([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)[,/]\s*CE\b', texto)
                    if m_cid:
                        cidade = m_cid.group(1).strip() + '/CE'

                categoria = detectar_categoria(modelo, marca, "carros")
                icone     = ICONES.get(categoria, "📦")
                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = _analisar_cached(url_lote, marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado", ""))
                print(f"  {icone} [MJLeiloes/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                lotes.append(_lote_dict("mj", categoria, marca, modelo, ano,
                                        cidade, lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))
                time.sleep(0.3)
            except Exception as e:
                print(f"  ⚠️ MJLeiloes lote: {e}")

    return lotes

# ─── SCRAPER CELSO CUNHA LEILÕES ─────────────────────────────────────────────
_CC_BASE    = "https://celsocunhaleiloes.com.br"
_CC_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36"}

# A pagina do CelsoCunha e de encoding MISTO: o bullet "»" que separa os
# campos da ficha e um byte solto 0xBB (Latin-1), mas o texto do banco
# (Descricao, Serie...) vem em UTF-8. Ler r.text como UTF-8 (o que o
# header manda) acerta os acentos mas troca o "»" por "�" — e sem o
# "»" o _li_val nunca casa, deixando marca/modelo/ano vazios e derrubando
# a FIPE (era ~1/3 dos lotes em producao). Entao decodifica como Latin-1
# aqui (preserva o "»") e conserta os acentos depois com _demojibake.
def _cc_get(url, timeout=20):
    r = requests.get(url, headers=_CC_HEADERS, timeout=timeout)
    r.encoding = "iso-8859-1"
    return r.text

def _demojibake(s):
    """Reverte acento UTF-8 lido como Latin-1 (ex.: 'Ã©' -> 'é'). Deixa a
    string intacta se nao houver sinal de mojibake ou se a conversao falhar."""
    if "Ã" not in s and "Â" not in s:
        return s
    try:
        return s.encode("latin-1", "ignore").decode("utf-8", "ignore")
    except UnicodeError:
        return s

# A data do pregao do CelsoCunha so aparece na pagina do LEILAO, nunca na
# do lote. Alem disso o _extrair_data_leilao generico as vezes casa antes
# num contador regressivo da pagina e devolve data errada (era o motivo
# de ~metade dos lotes CelsoCunha ficarem sem data ou com data furada).
# Aqui a regex e ancorada em "data:" / "1a Praca".
def _cc_data_leilao(texto):
    m = re.search(
        r'(?:\bdata:|1[ªa]\s*pra[çc]a)[^\d]{0,8}(\d{2}/\d{2}/\d{4})[^\d]{0,12}(\d{2}:\d{2})',
        texto, re.I,
    )
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M"
            ).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            pass
    return _extrair_data_leilao(texto)

# Lote "pacote": varios veiculos vendidos juntos ("Piramide constituida
# por 03 veiculos ..."). Marca/modelo/ano nao se aplicam e a FIPE nunca
# resolve — o lote e mantido (pode ser oportunidade real) mas rotulado
# como pacote e sem tentar referencia de preco.
_CC_BUNDLE_RE = re.compile(
    r'pir[aâ]mide|constitu[íi]d[ao]\s+por\s+\d+\s+ve[íi]culos|'
    r'\b\d+\s+ve[íi]culos\b|lote\s+com\s+v[áa]rios',
    re.I,
)

# Slug de leilao terminando em UF que nao e o Ceara (ex.: ".../leilao-
# prefeitura-municipal-de-sertaozinho-sp"). CelsoCunha e uma leiloeira de
# Sertaozinho-SP e publica muito leilao de fora; o filtro do projeto e
# "so Ceara", entao esses leiloes sao pulados inteiros.
_CC_UF_FORA_CE = re.compile(
    r'-(ac|al|ap|am|ba|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)(?=$|[/?#])',
    re.I,
)

def _raspar_celso_cunha(vistos):
    lotes = []
    try:
        html_home = _cc_get(_CC_BASE + "/", timeout=20)
    except Exception as e:
        print(f"⚠️ CelsoCunha: {e}")
        return lotes

    auction_paths = list(dict.fromkeys(re.findall(r'/leilao/\d+/[^"\'<>\s]+', html_home)))
    if not auction_paths:
        print("⚠️ CelsoCunha: nenhum leilão encontrado na homepage")
        return lotes

    for auction_path in auction_paths:
        if _CC_UF_FORA_CE.search(auction_path):
            print(f"  [skip] CelsoCunha leilão fora do CE: {auction_path}")
            continue

        url_auction = _CC_BASE + auction_path
        print(f"📡 CelsoCunha | {auction_path}")

        data_leilao_auction = ""
        for page in range(1, 30):
            try:
                html_pg = _cc_get(f"{url_auction}?page={page}", timeout=20)
            except Exception as e:
                print(f"  ⚠️ CelsoCunha {auction_path} p{page}: {e}")
                break

            if page == 1:
                texto_pg1 = _demojibake(html.unescape(
                    re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html_pg))))
                data_leilao_auction = _cc_data_leilao(texto_pg1)

            lot_paths = list(dict.fromkeys(re.findall(r'/lote/\d+/[^"\'<>\s]+', html_pg)))
            if not lot_paths:
                break

            new_lots = [p for p in lot_paths if (_CC_BASE + p) not in vistos]
            if not new_lots:
                break

            print(f"  p{page}: {len(new_lots)} lotes novos")

            for lot_path in new_lots:
                url_lote = _CC_BASE + lot_path
                vistos.add(url_lote)
                try:
                    html_lote = _cc_get(url_lote, timeout=15)
                    texto = re.sub(r'<[^>]+>', ' ', html_lote)
                    texto = _demojibake(html.unescape(re.sub(r'\s+', ' ', texto).strip()))

                    def _li_val(field):
                        m = re.search(rf'»\s*{field}:\s*([^<\n]+)', html_lote, re.I)
                        return _demojibake(html.unescape(m.group(1).strip())) if m else ""

                    marca_raw  = _li_val("Marca")
                    modelo_raw = _li_val("Modelo")
                    ano_str    = _li_val("Ano")
                    bundle = bool(_CC_BUNDLE_RE.search(
                        f"{marca_raw} {modelo_raw} {lot_path}"))
                    ano = 0
                    if bundle:
                        titulo = " ".join(t for t in (marca_raw, modelo_raw) if t).strip(" -")
                        if len(titulo) < 8:
                            titulo = re.sub(r'-', ' ', lot_path.split('/', 3)[-1])
                        marca  = "Lote com vários veículos"
                        modelo = titulo.title()[:90] or "?"
                    else:
                        marca  = marca_raw.title() or "?"
                        modelo = modelo_raw.title() or "?"
                        ano_m = re.search(r'(\d{4})', ano_str)
                        if ano_m:
                            ano = int(ano_m.group(1))

                    lance = _extrair_lance(texto)
                    km    = _extrair_km(texto)
                    descricao = _extrair_descricao(texto)
                    data_leilao = data_leilao_auction or _extrair_data_leilao(texto)

                    fotos = re.findall(
                        r'https://(?:www\.)?celsocunhaleiloes\.com\.br/imgTmp/[^\s"\'<>]+',
                        html_lote, re.I
                    )
                    foto = fotos[0] if fotos else ""

                    # Localizacao real do lote. Antes isto era "Fortaleza/CE"
                    # fixo — todo lote (inclusive os de SP) entrava carimbado
                    # como Fortaleza. Agora exige evidencia positiva de Ceara
                    # e, sem ela, descarta o lote (filtro "so CE").
                    #
                    # A evidencia so pode vir de partes especificas do lote
                    # (slug do leilao, slug do lote, campo "» Patio:"). NAO
                    # da pra procurar no texto inteiro da pagina: o rodape
                    # traz fixo o endereco do escritorio da leiloeira em
                    # Fortaleza/CE, o que faria todo lote "parecer" do CE.
                    patio_m = re.search(r'»\s*P[áa]tio:\s*([^<\n]+)', html_lote, re.I)
                    patio = _demojibake(patio_m.group(1).strip()) if patio_m else ""
                    loc_blob = _demojibake(f"{auction_path} {lot_path} {patio}").lower()

                    cidade_ce = next(
                        (c.replace('-', ' ').title() for c in CIDADES_CE
                         if c in loc_blob or c.replace('-', ' ') in loc_blob),
                        "",
                    )
                    if not cidade_ce and not re.search(r'[/\-\s]ce\b|cear[aá]', loc_blob):
                        print(f"  [skip] CelsoCunha lote sem evidência de CE: {url_lote}")
                        continue
                    cidade = f"{cidade_ce}/CE" if cidade_ce else "CE"

                    categoria = detectar_categoria(modelo, marca, "carros")
                    icone     = ICONES.get(categoria, "📦")
                    if bundle:
                        ref_val, ref_str = 0, ""
                    else:
                        ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                    analise  = _analisar_cached(url_lote, marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                    classif  = classificar(lance, ref_val, analise.get("estado", ""))
                    print(f"  {icone} [CelsoCunha/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                    lotes.append(_lote_dict("celsocunha", categoria, marca, modelo, ano,
                                            cidade, lance, ref_val, ref_str,
                                            classif, foto, km, descricao, analise, url_lote, data_leilao))
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  ⚠️ CelsoCunha lote: {e}")

    return lotes

# ─── SCRAPER SOLEON (Construbem + Daniel Garcia) ─────────────────────────────
_SOLEON_CE = ['ceará','ceara','fortaleza','maracanau','maracanaú','caucaia',
              'juazeiro','sobral','crato','eusebio','horizonte','pacajus',
              'aquiraz','russas','iguatu','quixada','quixadá','limoeiro',
              'tiangua','tianguá','caninde','canindé','itapipoca','aracati',
              'trt-7','trt 7','7ª região']
# "/ce" e "-ce" precisam de fronteira de palavra — sem isso, "-ce" também
# casa com classes CSS como "align-self-center" e "text-center".
_SOLEON_CE_RE = re.compile(
    r'(?:' + '|'.join(re.escape(c) for c in _SOLEON_CE) + r')|[/-]ce\b'
)

# Titulos da Soleon que sao rotulo generico de categoria ou lote-pacote, sem
# bem identificavel — a Construbem publica muitos junto com os veiculos
# ("Semoventes ?", "Cotas ?", "Diversos A) 01 (Um) Frigobar...", "Piramide
# Constituida De Carteiras Escolares...", "Salas Comerciais", "Sucata De Pecas").
_SOLEON_LIXO_EXATO = {
    "", "?", "diversos", "varios", "vários", "semovente", "semoventes",
    "cota", "cotas", "sucata", "sucatas", "terreno", "terrenos", "lote",
    "lotes", "salas comerciais", "bens diversos", "materiais", "acervo",
    "estoque", "pecas diversas", "peças diversas",
}
_SOLEON_LIXO_PREFIXOS = (
    "diversos", "piramide", "pirâmide", "semovente", "cota ", "cotas ",
    "bens diversos", "sucata de pec", "sucata de peç", "sucata ", "lote de",
    "salas comerciais", "materiais ", "material de", "acervo ", "estoque de",
)
_UFS_NAO_CE = (r"AC|AL|AP|AM|BA|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|"
               r"RO|RR|SC|SP|SE|TO")
# Campo "Cidade": aceita "Natal/RN", "Natal - RN", "Natal RN".
_UF_NAO_CE_CIDADE_RE = re.compile(rf"[/\-\s](?:{_UFS_NAO_CE})\b", re.I)
# Titulo livre: so conta "Cidade/UF" com barra — um " SE"/" ES" solto no
# titulo costuma ser sufixo de versao ("Ford Ka SE"), nao a UF Sergipe.
_UF_NAO_CE_TITULO_RE = re.compile(rf"/\s*(?:{_UFS_NAO_CE})\b", re.I)


def _soleon_fora_ce(texto, no_titulo=False):
    """True se o texto tem UF explicita que nao e CE (ex.: 'Natal/RN')."""
    c = (texto or "").strip()
    if re.search(r"[/\-\s]ce\b", c, re.I) or c.upper().rstrip("/").endswith("CE"):
        return False
    rx = _UF_NAO_CE_TITULO_RE if no_titulo else _UF_NAO_CE_CIDADE_RE
    return bool(rx.search(c))


def _soleon_lote_util(titulo, categoria, marca, modelo):
    """False para rotulo generico / lote-pacote / veiculo sem marca-modelo."""
    t = re.sub(r"\s+", " ", (titulo or "")).strip().lower()
    t = t.rstrip(" ?").strip()
    if len(t) < 4 or t in _SOLEON_LIXO_EXATO or "semovente" in t:
        return False
    if t.startswith(_SOLEON_LIXO_PREFIXOS) and not re.search(
        r"\b(?:19[89]\d|20[0-3]\d)\b", titulo or ""
    ):
        return False
    if categoria in ("carros", "motos", "caminhoes") and (
        marca in ("", "?", None) or modelo in ("", "?", None)
    ):
        return False
    return True


def _extrair_veiculo_de_titulo(titulo):
    """Extrai marca, modelo, ano de título no formato Soleon (ex: 'PEUGEOT/207HB XR S - ANO: 2009/2010')."""
    t = re.sub(r'\s+', ' ', titulo.strip()).upper()
    # Descarta contadores no inicio ("01 ", "1 (UMA) ", "205 (DUZENTOS...) ") —
    # exige espaco depois, pra nao comer numero de modelo ("207HB", "125 FAN").
    t = re.sub(r'^\s*\d{1,3}\s*(?:\([^)]*\)\s*)?[-)ºª.:]*\s+', '', t).strip()
    ano = 0
    # "ANO: 2009/2010" ou "ANO/MODELO: 2009" — captura ambos os formatos
    ano_m = re.search(r'ANO(?:/MODELO)?[:\s]+(\d{4})(?:/\d+)?', t)
    if ano_m:
        ano = int(ano_m.group(1))
        t = (t[:ano_m.start()] + t[ano_m.end():]).strip().strip('-').strip()
    else:
        # Formato "2009/2010" standalone (sem prefixo "ANO:")
        ano_m = re.search(r'\b(19[89]\d|20[012]\d)/\d{2,4}\b', t)
        if ano_m:
            ano = int(ano_m.group(1))
            t = (t[:ano_m.start()] + t[ano_m.end():]).strip()
    parts = [p.strip() for p in t.split('/') if p.strip()]
    if len(parts) >= 2:
        marca  = parts[0].title()
        modelo = ' '.join(parts[1:]).title()
    elif parts:
        words = parts[0].split()
        marca  = words[0].title() if words else "?"
        modelo = ' '.join(w.title() for w in words[1:3]) if len(words) > 1 else "?"
    else:
        marca, modelo = "?", "?"
    return marca, modelo, ano


def _parse_soleon_lots_from_listing(html, base):
    """
    Extrai dados de lotes do HTML da página de listagem Soleon.
    Cada lote tem: url, titulo, cidade, descricao, lance, km, data_leilao, foto.
    Evita fetchs individuais de detalhe — uma request por página de listagem.
    """
    texto = re.sub(r'<[^>]+>', ' ', html)
    texto = re.sub(r'\s+', ' ', texto)

    lot_ids = list(dict.fromkeys(re.findall(r'/item/(\d+)/detalhes', html)))
    if not lot_ids:
        return []

    positions = []
    for lid in lot_ids:
        p = html.find(f'/item/{lid}/detalhes')
        if p >= 0:
            positions.append((lid, p))
    positions.sort(key=lambda x: x[1])

    results = []
    for i, (lot_id, pos) in enumerate(positions):
        url_lote = f"{base}/item/{lot_id}/detalhes"
        next_pos = positions[i + 1][1] if i + 1 < len(positions) else len(html)
        chunk_html = html[max(0, pos - 3000): next_pos]
        chunk = re.sub(r'<[^>]+>', ' ', chunk_html)
        chunk = re.sub(r'\s+', ' ', chunk).strip()

        # Título: texto entre "Lote NNN" e a primeira palavra-chave estrutural
        titulo = ""
        lot_m = re.search(
            r'\bLote\s+0*\d+\s+(.+?)(?=\s+(?:Descrição|Cidade|Endereço|Matrícula|Processo|Local de Exposição)\s*:)',
            chunk
        )
        if lot_m:
            titulo = re.sub(r'\s+', ' ', lot_m.group(1)).strip()[:200]
            titulo = re.sub(r'^Item\s+\d+[:\s]+', '', titulo).strip()
        if not titulo:
            ls = re.search(r'\bLote\s+0*\d+\s+', chunk)
            if ls:
                titulo = chunk[ls.end():ls.end() + 120].split('Descrição')[0].split('Cidade')[0].strip()

        # Cidade
        cidade = "CE"
        city_m = re.search(r'Cidade:\s*([^|\n]{3,60}?)(?:\s+(?:Endereço|Descrição|Matrícula|Processo)|$)', chunk)
        if city_m:
            cidade = city_m.group(1).strip().rstrip('/,')
        else:
            for c in CIDADES_CE:
                if c.replace('-', ' ') in chunk.lower():
                    cidade = c.replace('-', ' ').title() + '/CE'
                    break

        # Descrição
        desc_m = re.search(
            r'Descrição:\s*(.{40,600}?)(?=\s+(?:Local de Exposição|Processo|Exequente|Executado))',
            chunk, re.S
        )
        descricao = re.sub(r'\s+', ' ', desc_m.group(1)).strip() if desc_m else titulo

        lance      = _extrair_lance(chunk)
        km         = _extrair_km(chunk)
        data_leilao = _extrair_data_leilao(chunk)

        foto = ""
        fotos = re.findall(
            r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']',
            html[max(0, pos - 1200): min(len(html), pos + 500)], re.I
        )
        foto = next((f for f in fotos if not any(x in f.lower() for x in ['logo', 'icon', 'avatar', 'banner'])), "")

        results.append({
            'url': url_lote,
            'titulo': titulo,
            'cidade': cidade,
            'descricao': descricao[:500],
            'lance': lance,
            'km': km,
            'data_leilao': data_leilao,
            'foto': foto,
        })

    return results


_SOLEON_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/124.0.0.0 Safari/537.36"}
_ZENROWS_API_URL   = "https://api.zenrows.com/v1/"
_SCRAPERAPI_API_URL = "https://api.scraperapi.com/"

def _raspar_soleon(base, fonte, vistos):
    """Scraper para Construbem e Daniel Garcia (plataforma Soleon).
    Ambos os sites são renderizados no servidor (sem JS necessário) — mas o
    Cloudflare deles bloqueia especificamente a faixa de IP dos runners do
    GitHub Actions (confirmado: o mesmo requests.get() com os mesmos headers
    funciona normalmente de outros IPs, então não é um bloqueio por
    fingerprint de user-agent nem exige renderizar JS).

    Ordem de tentativa por URL: Zenrows -> ScraperAPI -> requests direto.
    Os dois proxies só entram se a respectiva chave estiver configurada; se
    um falhar (ex.: Zenrows sem crédito -> HTTP 402), cai pro próximo. Em
    dev local, sem nenhuma chave, o requests direto basta.
    """
    lotes = []
    nome  = {"construbem": "Construbem", "danielgarcia": "Daniel Garcia"}.get(fonte, fonte.title())
    sess  = requests.Session()
    sess.headers.update(_SOLEON_HEADERS)
    zenrows_key    = os.getenv("ZENROWS_API_KEY", "").strip()
    scraperapi_key = os.getenv("SCRAPERAPI_KEY", "").strip()

    def _fetch_variants(url):
        if zenrows_key:
            yield "Zenrows", _ZENROWS_API_URL, {"apikey": zenrows_key, "url": url}
        if scraperapi_key:
            yield "ScraperAPI", _SCRAPERAPI_API_URL, {"api_key": scraperapi_key, "url": url}
        yield "direto", url, None

    def _get(url):
        for label, endpoint, params in _fetch_variants(url):
            try:
                r = sess.get(endpoint, params=params, timeout=30 if params else 20)
                if r.status_code == 200:
                    return r.text
                print(f"  ⚠️ {nome} [{label}] {r.status_code}: {url}")
            except Exception as e:
                print(f"  ⚠️ {nome} [{label}] request: {e}")
        return ""

    html_home = _get(base + "/")
    if not html_home:
        print(f"  ⚠️ {nome}: homepage vazia")
        return lotes

    auction_ids = list(dict.fromkeys(re.findall(r'/leilao/(\d+)/lotes', html_home)))
    if not auction_ids:
        print(f"  ⚠️ {nome}: nenhum leilão na homepage")
        return lotes

    print(f"📡 {nome} | {len(auction_ids)} leilão(ões)")

    for auction_id in auction_ids[:5]:
        url_auction = f"{base}/leilao/{auction_id}/lotes"
        print(f"  📋 {nome} | leilão {auction_id}")

        html_p1 = _get(url_auction)
        if not html_p1:
            continue

        if fonte == "danielgarcia":
            html_check = html_p1.lower()
            if not _SOLEON_CE_RE.search(html_check):
                titulo_m = re.search(r'<title[^>]*>([^<]+)</title>', html_p1, re.I)
                titulo   = (titulo_m.group(1) if titulo_m else "")[:70]
                print(f"    [skip] não CE: {titulo}")
                continue

        # Coletar todas as páginas (suporte a paginação)
        all_pages = [html_p1]
        for pg in range(2, 8):
            url_pg  = f"{url_auction}?page={pg}"
            time.sleep(0.3)
            html_pg = _get(url_pg)
            if not html_pg or not re.search(r'/item/\d+/detalhes', html_pg):
                break
            if html_pg == html_p1:
                break
            n_pg = len(list(dict.fromkeys(re.findall(r'/item/(\d+)/detalhes', html_pg))))
            print(f"    Página {pg}: {n_pg} lotes")
            all_pages.append(html_pg)

        time.sleep(0.3)

        for html_page in all_pages:
            lots_info = _parse_soleon_lots_from_listing(html_page, base)
            if not lots_info:
                txt = re.sub(r'<[^>]+>', ' ', html_page[:600])
                print(f"    [diag] sem lotes | {txt[:200]}")
                continue

            for info in lots_info:
                if info['url'] in vistos:
                    continue
                vistos.add(info['url'])

                titulo    = info['titulo']
                descricao = info['descricao']
                cidade    = info['cidade']
                lance     = info['lance']
                km        = info['km']
                data_leilao = info['data_leilao']
                foto      = info['foto']
                url_lote  = info['url']

                tl = titulo.lower()
                combined = tl + ' ' + descricao.lower()[:150]

                if any(p in tl for p in PALAVRAS_IMOVEL):
                    categoria = "imoveis"
                    marca  = titulo.title()[:60]
                    modelo = cidade
                    ano    = 0
                elif any(p in combined for p in PALAVRAS_MAQUINA):
                    categoria = "equipamentos"
                    marca, modelo, ano = _extrair_veiculo_de_titulo(titulo)
                elif any(p in combined for p in PALAVRAS_CAMINHAO) or any(p in tl for p in ['ônibus', 'onibus', 'caminhão', 'caminhao']):
                    categoria = "caminhoes"
                    marca, modelo, ano = _extrair_veiculo_de_titulo(titulo)
                elif any(p in combined for p in PALAVRAS_MOTO) or any(p in tl for p in ['motocicleta', 'moto']):
                    categoria = "motos"
                    marca, modelo, ano = _extrair_veiculo_de_titulo(titulo)
                elif tl.strip() in ['diversos', 'vários', 'varios']:
                    categoria = "equipamentos"
                    marca  = "Diversos"
                    modelo = descricao[:50].title()
                    ano    = 0
                else:
                    categoria = "carros"
                    marca, modelo, ano = _extrair_veiculo_de_titulo(titulo)

                if _soleon_fora_ce(cidade) or _soleon_fora_ce(titulo, no_titulo=True):
                    print(f"    [skip] {nome} fora do CE: {cidade} | {titulo[:50]}")
                    continue
                if not _soleon_lote_util(titulo, categoria, marca, modelo):
                    print(f"    [skip] {nome} lixo/incompleto: {titulo[:60]}")
                    continue

                icone    = ICONES.get(categoria, "📦")
                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = _analisar_cached(url_lote, marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado", ""))
                print(f"    {icone} [{nome}/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                lotes.append(_lote_dict(fonte, categoria, marca, modelo, ano,
                                        cidade, lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))

    return lotes

# ─── SCRAPER MGL LEILÕES ─────────────────────────────────────────────────────
# A busca da MGL e uma SPA: a listagem vem de POST /apiplugin/GetBusca com um
# corpo JSON (o objeto window.JsonParametrosBusca). O filtro por estado so
# funciona nesse corpo (ID_Estado); passar "estado=23" no #hash da URL nao
# filtra nada — por isso a versao antiga sempre via o inventario nacional e
# estourava o wait_for_selector de 30s no runner do GitHub Actions. Aqui a API
# e chamada direto, de dentro da pagina (fetch same-origin), reaproveitando os
# cookies/clearance do Cloudflare obtidos no goto inicial. Traz veiculos E
# imoveis do Ceara (a MGL costuma ter so imoveis retomados Caixa no estado).
_MGL_BASE = "https://www.mgl.com.br"
_MGL_BUSCA_URL = _MGL_BASE + "/busca/#Engine=Start&Pagina=1&Busca=&Mapa=&ID_Categoria=0"
_MGL_ID_ESTADO_CE = 23

# Corpo base do POST — mesmos campos que a SPA envia (window.JsonParametrosBusca).
_MGL_BUSCA_PARAMS = {
    "Bairro": "", "Busca": "", "BuscaProcesso": "", "CFGs": "",
    "CamposDinamicos": [], "CodLeilao": "", "DataAbertura": "",
    "DataEncerramento": "", "ID_Categoria": 0, "ID_Cidade": 0,
    "ID_Estado": _MGL_ID_ESTADO_CE, "ID_Leiloes_Status": [], "ID_Modelo": 0,
    "ID_Regiao": 0, "IgnoreScopo": 0, "Mapa": "", "NomesPartes": "",
    "OrdSt": 0, "Ordem": 0, "OrientacaoBusca": 0, "Pagina": 1,
    "PaginaIndex": 1, "PracaAtual": 0, "QtdPorPagina": 48, "RangeValores": 0,
    "Scopo": 0, "SubStatus": [], "TiposLeiloes": [], "ValorMaxSelecionado": 0,
    "ValorMinSelecionado": 0, "sInL": "",
}

# Cabecalhos que a SPA usa nas chamadas XHR — sem eles o WAF/Cloudflare tende a
# devolver 403 para POST "cru" em /apiplugin/. `credentials: 'include'` garante
# que o cookie cf_clearance vai junto. Em 403 (desafio ainda nao resolvido no
# runner), tenta de novo algumas vezes com intervalo.
_MGL_FETCH_BUSCA_JS = """async (body) => {
    const call = () => fetch(
        `/apiplugin/GetBusca/${body.Pagina}/${body.PaginaIndex}/0?`,
        { method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json',
                     'X-Requested-With': 'XMLHttpRequest',
                     'Accept': 'application/json, text/javascript, */*; q=0.01' },
          body: JSON.stringify(body) });
    try {
        let r = await call();
        for (let i = 0; i < 3 && (r.status === 403 || r.status === 429); i++) {
            await new Promise(s => setTimeout(s, 4000));
            r = await call();
        }
        if (!r.ok) return { __erro: r.status };
        return await r.json();
    } catch (e) { return { __erro: String(e) }; }
}"""

_MGL_FETCH_HTML_JS = """async (url) => {
    try {
        const r = await fetch(url, { credentials: 'include',
            headers: { 'Accept': 'text/html,application/xhtml+xml',
                       'X-Requested-With': 'XMLHttpRequest' } });
        if (!r.ok) return { __erro: r.status };
        return { html: await r.text() };
    } catch (e) { return { __erro: String(e) }; }
}"""

_MGL_ICONES_IMOVEL = ("residenci", "imove", "imóve", "terreno", "apartament",
                      "comerci", "rural", "predio", "galpao")
_MGL_ICONES_VEICULO = ("carro", "moto", "caminho", "van", "onibus", "ônibus",
                       "veic", "maquin", "máquin", "trator", "agricol")


def _html_para_texto(h):
    """HTML cru -> texto tipo innerText, preservando quebras de bloco."""
    h = re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?i)<(br|/p|/div|/li|/tr|/h[1-6]|/td|/ul)[^>]*>', '\n', h)
    h = re.sub(r'(?s)<[^>]+>', ' ', h)
    h = html.unescape(h)
    h = re.sub(r'[ \t\xa0​]+', ' ', h)
    h = re.sub(r' *\n[ \n]*', '\n', h)
    return h.strip()


def _mgl_url_foto(fotos):
    for f in fotos or []:
        nome = (f or {}).get("Foto") or ""
        low = nome.lower()
        if nome and not low.endswith(".svg") and "semfoto" not in low:
            return f"{_MGL_BASE}/imagens-complete/605x487/{nome}"
    return ""


def _mgl_categoria_lote(lote):
    """Categoria do projeto para um lote da MGL; None se estiver fora do escopo
    (bens diversos, sucata avulsa etc.)."""
    titulo = lote.get("Lote") or ""
    icone  = (lote.get("IconeCategoria") or "").lower()
    tl     = titulo.lower()

    if any(t in icone for t in _MGL_ICONES_IMOVEL) or \
       any(p in tl for p in PALAVRAS_IMOVEL):
        return "imoveis"

    eh_veiculo = (
        any(t in icone for t in _MGL_ICONES_VEICULO)
        or re.search(r'\b(?:19|20)\d{2}\s*/\s*(?:19|20)\d{2}\b', titulo)
    )
    if not eh_veiculo:
        return None
    return detectar_categoria(titulo, "", "carros")


def _mgl_data_leilao(realtime):
    """Data do pregao a partir do bloco GetLoteRealTime da API (abertura da 1a
    praca; encerramento como fallback para lotes de venda direta)."""
    if not isinstance(realtime, dict):
        return ""
    agora = datetime.now()
    for campo in ("DataHoraAberturaPrimeiraPraca",
                  "DataHoraEncerramentoPrimeiraPraca"):
        bruto = realtime.get(campo) or ""
        if not bruto or bruto[:4] in ("1900", "0001"):
            continue
        try:
            dt = datetime.fromisoformat(bruto[:19])
        except ValueError:
            continue
        if dt > agora - timedelta(days=1):
            return dt.strftime("%Y-%m-%dT%H:%M")
    return ""


def _mgl_parse_detalhe_veiculo(texto):
    """Extrai marca/modelo/ano/km do bloco 'Informações' da pagina de detalhe
    (rotulos atuais: 'MODELO:', 'ANO:', 'KM:')."""
    marca = modelo = ""
    ano = 0
    m = re.search(r'MODELO:\s*([^\n]+)', texto, re.IGNORECASE)
    if m:
        partes = re.sub(r'\s+', ' ', m.group(1)).strip(" .-").split()
        if partes:
            marca  = partes[0].title()
            modelo = " ".join(partes[1:]).title() if len(partes) > 1 else marca
    a = re.search(r'ANO:\s*(\d{4})\s*/\s*(\d{4})', texto, re.IGNORECASE)
    if a:
        ano = int(a.group(2))
    km = ""
    k = re.search(r'KM:\s*(\d{1,3}(?:\.\d{3})+|\d{3,})', texto, re.IGNORECASE)
    if k and int(k.group(1).replace(".", "")) >= 1000:
        km = f"{k.group(1)} km"
    return marca, modelo, ano, km


def _mgl_descricao(texto):
    """Texto util do bloco 'Informações' (+ 'Ônus') da pagina de detalhe,
    sem as linhas de marketing/boilerplate."""
    # Termina numa LINHA que seja so o titulo da proxima secao — o cabecalho
    # "Condicoes" aparece isolado, enquanto "condicoes" no meio de uma frase do
    # boilerplate ("No estado e condicoes que se encontra") nao deve cortar.
    m = re.search(
        r'Informa[çc][õo]es\b(.*?)(?:\n[ \t]*(?:Condi[çc][õo]es|Documenta[çc]|Documentos|Hist[óo]rico de Lances|Encontre no mapa)[ \t]*\n|\Z)',
        texto, re.IGNORECASE | re.DOTALL
    )
    if not m:
        return ""
    linhas = []
    for linha in m.group(1).splitlines():
        l = linha.strip()
        if not l:
            continue
        low = l.lower()
        if low.startswith(("modelo:", "ano:", "agende sua visita", "venda voc",
                           "a descri", "despesa administrativa", "0800")):
            continue
        linhas.append(l)
    return re.sub(r'\s+', ' ', " ".join(linhas)).strip()[:700]


def _mgl_avaliacao_imovel(texto):
    m = re.search(r'Avalia[çc][ãa]o:?\s*R\$\s*([\d.]+,\d{2})', texto, re.IGNORECASE)
    return _parse_brl(m.group(1)) if m else 0


def _raspar_mgl(pg_lista, _pg_detalhe, vistos):
    """Veiculos e imoveis localizados no Ceara na MGL (via /apiplugin/GetBusca)."""
    lotes = []
    try:
        print("📡 MGL | veículos e imóveis no Ceará")
        try:
            stealth_sync(pg_lista)  # reduz deteccao de headless (desafio Cloudflare)
        except Exception:
            pass
        pg_lista.goto(_MGL_BUSCA_URL, wait_until="domcontentloaded", timeout=60000)
        # A SPA da busca so define window.JsonParametrosBusca depois que o bundle
        # roda — se ele existe, o desafio do Cloudflare passou e a pagina real
        # carregou (nao a interstitial). Se nao aparecer, o runner esta sendo
        # bloqueado na borda pelo Cloudflare — bail rapido, sem insistir.
        # (Confirmado em 2026-09-02: IP do GitHub Actions e barrado; so com
        #  proxy residencial. Ver MGL_SCRAPER_PENDENTE.md.)
        try:
            pg_lista.wait_for_function(
                "() => typeof window.JsonParametrosBusca !== 'undefined'",
                timeout=12000,
            )
        except Exception:
            print("  ⚠️ MGL: SPA nao inicializou — bloqueio Cloudflare no runner (precisa de proxy)")
            return lotes
        pg_lista.wait_for_timeout(2000)
    except Exception as e:
        print(f"  ⚠️ MGL abertura: {e}")
        return lotes

    brutos, total = [], None
    for pagina in range(1, 16):
        params = dict(_MGL_BUSCA_PARAMS, Pagina=pagina, PaginaIndex=pagina)
        try:
            data = pg_lista.evaluate(_MGL_FETCH_BUSCA_JS, params)
        except Exception as e:
            print(f"  ⚠️ MGL busca p{pagina}: {e}")
            break
        if not isinstance(data, dict) or data.get("__erro"):
            erro = data.get("__erro") if isinstance(data, dict) else data
            print(f"  ⚠️ MGL busca p{pagina}: {erro}")
            break
        pagina_lotes = data.get("Lotes") or []
        if total is None:
            total = data.get("CountTotal") or 0
        brutos.extend(pagina_lotes)
        if not pagina_lotes or len(brutos) >= (total or 0):
            break

    print(f"  {len(brutos)} lote(s) no CE (bruto)")

    for lote in brutos:
        uf = (lote.get("UF") or "").strip().upper()
        if uf and uf != "CE":
            continue

        url_rel = (lote.get("URLlote") or "").lstrip("/")
        if not url_rel:
            continue
        url_lote = f"{_MGL_BASE}/{url_rel}"
        if url_lote in vistos:
            continue
        vistos.add(url_lote)

        categoria = _mgl_categoria_lote(lote)
        if categoria is None:
            continue

        cidade_nome = (lote.get("Cidade") or "").strip()
        cidade = f"{cidade_nome}/CE" if cidade_nome else "CE"

        try:
            lance = float(lote.get("ValorInicialPrimeiraPraca")
                          or lote.get("ValorVendaDireta") or 0)
        except (TypeError, ValueError):
            lance = 0.0

        rt = lote.get("GetLoteRealTime") or []
        data_leilao = _mgl_data_leilao(rt[0] if rt else {})
        foto = _mgl_url_foto(lote.get("Fotos"))

        # Pagina de detalhe: fetch same-origin (sem navegar) para km/ano/restricoes
        # (veiculo) ou avaliacao + edital (imovel).
        texto = ""
        try:
            res = pg_lista.evaluate(_MGL_FETCH_HTML_JS, url_lote)
            if isinstance(res, dict) and res.get("html"):
                texto = _html_para_texto(res["html"])
        except Exception as e:
            print(f"  ⚠️ MGL detalhe {url_lote}: {e}")

        if categoria == "imoveis":
            marca = "Imóvel"
            modelo = re.sub(r'\s*\([^)]*\)\s*$', '', lote.get("Lote") or "").strip() or "Imóvel"
            ano, km = 0, ""
            descricao = _mgl_descricao(texto) if texto else ""
            ref_val = _mgl_avaliacao_imovel(texto) if texto else 0
            ref_str = f"R$ {ref_val:,.0f} (avaliação)" if ref_val else "Sem referência"
            if not data_leilao and texto:
                data_leilao = _extrair_data_leilao(texto)
        else:
            marca = modelo = ""
            ano, km = 0, ""
            if texto:
                marca, modelo, ano, km = _mgl_parse_detalhe_veiculo(texto)
            if not marca:
                # fallback: titulo "CIDADE/UF - MARCA MODELO ANO/ANO - COD"
                bruto = re.sub(r'^[^-]*-\s*', '', lote.get("Lote") or "")
                bruto = re.sub(r'\b(?:19|20)\d{2}\s*/\s*(?:19|20)\d{2}.*$', '', bruto).strip(" .-")
                partes = bruto.split()
                if partes:
                    marca  = partes[0].title()
                    modelo = " ".join(partes[1:]).title() if len(partes) > 1 else marca
            if not ano:
                am = re.search(r'\b(?:19|20)\d{2}\s*/\s*((?:19|20)\d{2})\b', lote.get("Lote") or "")
                if am:
                    ano = int(am.group(1))
            if not marca or not modelo:
                print(f"  [skip] MGL sem marca/modelo: {url_lote}")
                continue
            descricao = _mgl_descricao(texto) if texto else ""
            ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)

        icone = ICONES.get(categoria, "📦")
        analise = _analisar_cached(url_lote, marca, modelo, ano, descricao, km,
                                   lance, ref_val, categoria)
        classif = classificar(lance, ref_val, analise.get("estado", ""))
        print(f"  {icone} [MGL/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
        lotes.append(_lote_dict(
            "mgl", categoria, marca, modelo, ano, cidade,
            lance, ref_val, ref_str, classif, foto, km,
            descricao, analise, url_lote, data_leilao
        ))

    print(f"  ✅ MGL: {len(lotes)} lote(s)")
    return lotes


# ─── SCRAPER MONTENEGRO LEILÕES ───────────────────────────────────────────────
_MONTENEGRO_BASE = "https://montenegroleiloes.com.br"


def _scroll_ate_carregar_todos(pg, seletor, tentativas=12):
    """Carrega os cartões adicionados por rolagem infinita.

    Só considera "estabilizou" quando ja apareceu pelo menos 1 item — do
    contrario, uma pagina lenta pra iniciar o carregamento (ex.: atras de
    um desafio JS do Cloudflare) fica presa em 0==0 na primeira leitura e
    desiste antes mesmo do primeiro scroll fazer efeito.
    """
    anterior = -1
    for _ in range(tentativas):
        atual = pg.locator(seletor).count()
        if atual == anterior and atual > 0:
            break
        anterior = atual
        pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        pg.wait_for_timeout(700)


_MONTENEGRO_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36")


def _raspar_montenegro(_pg_lista, vistos, browser):
    """Descobre leilões abertos com veículos e coleta seus lotes.

    O Cloudflare da Montenegro bane a SESSÃO (não o IP) depois de poucas
    requisições automatizadas seguidas: confirmado ao vivo que reaproveitar
    a mesma página/contexto para a listagem de um leilão + as páginas de
    detalhe dos lotes já é suficiente pra derrubar tudo em 403 na metade do
    caminho, mesmo com pausas entre requisições. Um contexto novo (cookies
    limpos) por navegação, porém, funciona de forma consistente. Por isso
    cada navegação (homepage, leilão, lote) abre seu próprio contexto
    descartável — a página compartilhada não é usada aqui.
    """
    lotes = []
    print("📡 Montenegro | leilões com veículos")

    # A homepage é uma SPA Quasar atrás do Cloudflare da Montenegro, que às
    # vezes atrasa a primeira renderização além dos 30s. Contexto novo +
    # retry, no mesmo padrão do resto da função. O seletor certo é
    # ".q-card.cursor-pointer" (confirmado em 2026-09-02); ".q-card" entra só
    # como rede de segurança — o filtro por "Nº do Leilão:" descarta o resto.
    cards = []
    for tentativa in range(3):
        ctx_home = browser.new_context(user_agent=_MONTENEGRO_UA)
        try:
            pg_home = ctx_home.new_page()
            pg_home.goto(_MONTENEGRO_BASE + "/", wait_until="domcontentloaded", timeout=60000)
            try:
                pg_home.wait_for_selector(".q-card.cursor-pointer", timeout=45000)
            except Exception:
                pg_home.wait_for_selector(".q-card", timeout=15000)
            pg_home.wait_for_timeout(1200)
            cards = pg_home.locator(".q-card.cursor-pointer, .q-card").evaluate_all(
                "els => [...new Set(els.map(e => (e.innerText || '').trim()))]"
            )
        except Exception as e:
            print(f"  ⚠️ Montenegro homepage (tentativa {tentativa + 1}): {e}")
        finally:
            ctx_home.close()
        if cards:
            break

    leiloes = []
    for card in cards:
        if "Nº do Leilão:" not in card or not re.search(r've[ií]culos?', card, re.I):
            continue
        lm = re.search(r'Nº do Leilão:\s*(\d+)', card, re.I)
        if lm and lm.group(1) not in leiloes:
            leiloes.append(lm.group(1))
    if not leiloes:
        print("  ⚠️ Montenegro: nenhum leilão de veículos encontrado na homepage")
        return lotes

    print(f"  {len(leiloes)} leilão(ões) com veículos")
    for leilao_id in leiloes:
        url_leilao = f"{_MONTENEGRO_BASE}/leiloes/{leilao_id}"

        # O Cloudflare ocasionalmente atrasa/derruba uma navegação isolada mesmo
        # com contexto limpo — 1 retry com contexto novo cobre esse caso sem
        # mascarar uma falha real (leilão sem lote nenhum continua indo pra 0).
        cards_lote = []
        for tentativa in range(2):
            ctx_leilao = browser.new_context(user_agent=_MONTENEGRO_UA)
            try:
                pg_leilao = ctx_leilao.new_page()
                pg_leilao.goto(url_leilao, wait_until="domcontentloaded", timeout=60000)
                pg_leilao.wait_for_timeout(1200)
                # Os lotes só entram no DOM depois que a página é rolada (a Montenegro
                # passou a renderizar via infinite-scroll do Quasar) — rolar tem que vir
                # antes de esperar o seletor, senão o wait_for_selector nunca resolve.
                _scroll_ate_carregar_todos(pg_leilao, "[data-lote-id]")
                cards_lote = pg_leilao.locator("[data-lote-id]").evaluate_all(
                    "els => els.map(e => ({id: e.getAttribute('data-lote-id'), texto: (e.innerText || '').trim()}))"
                )
            except Exception as e:
                print(f"  ⚠️ Montenegro leilão {leilao_id} (tentativa {tentativa + 1}): {e}")
            finally:
                ctx_leilao.close()
            if cards_lote:
                break

        print(f"  Leilão {leilao_id}: {len(cards_lote)} lote(s)")
        for card in cards_lote:
            lote_id = card.get("id")
            resumo = card.get("texto", "")
            if not lote_id:
                continue

            # Leilões mistos também contêm imóveis. Este scraper processa
            # somente os lotes de veículos para evitar IA e FIPE indevidas.
            if any(p in resumo.lower() for p in PALAVRAS_IMOVEL):
                continue

            url_lote = f"{url_leilao}/lotes/{lote_id}"
            if url_lote in vistos:
                continue
            vistos.add(url_lote)

            ctx_lote = browser.new_context(user_agent=_MONTENEGRO_UA)
            try:
                pg_detalhe = ctx_lote.new_page()
                pg_detalhe.goto(url_lote, wait_until="domcontentloaded", timeout=45000)
                pg_detalhe.wait_for_timeout(700)
                texto = pg_detalhe.locator("body").inner_text()

                marca_m = re.search(r'\nMarca\s*\n([^\n]+)', texto, re.IGNORECASE)
                modelo_m = re.search(r'\nModelo\s*\n([^\n]+)', texto, re.IGNORECASE)
                ano_m = re.search(
                    r'Ano Fabrica[çc][aã]o\s*/\s*Modelo\s*\n\s*(\d{4})\s*/\s*(\d{4})',
                    texto, re.IGNORECASE
                )

                marca = marca_m.group(1).strip().title() if marca_m else "?"
                modelo = modelo_m.group(1).strip().title() if modelo_m else "?"
                ano = int(ano_m.group(2)) if ano_m else 0

                # Alguns lotes antigos não têm os campos estruturados; usa o
                # título do cartão como fallback sem acionar a IA duas vezes.
                if marca == "?" or modelo == "?":
                    linhas = [x.strip() for x in resumo.splitlines() if x.strip()]
                    titulo = next((x for x in linhas if re.search(r'\b(?:19|20)\d{2}/(?:19|20)\d{2}\b', x)), "")
                    fm, fmod, fa = _extrair_veiculo_de_titulo(titulo)
                    marca = fm if marca == "?" else marca
                    modelo = fmod if modelo == "?" else modelo
                    ano = ano or fa

                lance = _extrair_lance(texto)
                km = _extrair_km(texto)
                data_leilao = _extrair_data_leilao(texto)

                descricao = ""
                dm = re.search(
                    r'Detalhes do Lote\s*-\s*[^\n]+\n(.{20,1800}?)(?=\nCondições de Venda\b)',
                    texto, re.IGNORECASE | re.DOTALL
                )
                if dm:
                    descricao = re.sub(r'\s+', ' ', dm.group(1)).strip()[:700]
                if not descricao:
                    descricao = _extrair_descricao(texto)

                cidade = "Fortaleza/CE"
                base_cidade = (descricao + " " + texto[:1200]).lower()
                for nome_cidade in CIDADES_CE:
                    nome_legivel = nome_cidade.replace('-', ' ')
                    if nome_legivel in base_cidade:
                        cidade = nome_legivel.title() + "/CE"
                        break
                else:
                    cm = re.search(r'\b([A-ZÀ-Ú][^\n,/]{2,45})/CE\b', descricao, re.IGNORECASE)
                    if cm:
                        cidade = cm.group(1).strip().title() + "/CE"

                foto = ""
                fotos = pg_detalhe.locator("img").evaluate_all(
                    "els => els.map(e => e.src).filter(u => u && !/logo|icon|avatar|banner/i.test(u))"
                )
                if fotos:
                    foto = fotos[0]

                categoria = detectar_categoria(modelo, marca, "carros")
                icone = ICONES.get(categoria, "📦")
                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise = _analisar_cached(
                    url_lote, marca, modelo, ano, descricao, km,
                    lance, ref_val, categoria
                )
                classif = classificar(lance, ref_val, analise.get("estado", ""))
                print(f"  {icone} [Montenegro/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                lotes.append(_lote_dict(
                    "montenegro", categoria, marca, modelo, ano, cidade,
                    lance, ref_val, ref_str, classif, foto, km,
                    descricao, analise, url_lote, data_leilao
                ))
            except Exception as e:
                print(f"  ⚠️ Montenegro lote {lote_id}: {e}")
            finally:
                ctx_lote.close()

    return lotes

# ─── SCRAPER PRINCIPAL ────────────────────────────────────────────────────────
def raspar_leiloes():
    print("\n🚀 Scraper — Ceará | Leilo + Mega + Pacto + MGL + Montenegro + Construbem + DanielGarcia + MJLeiloes + CelsoCunha\n")
    _reset_metricas_ia()
    _load_analise_cache()
    lotes, vistos = [], set()

    with sync_playwright() as p:
        browser    = p.chromium.launch(headless=True)
        ctx        = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        pg_lista   = ctx.new_page()
        pg_detalhe = ctx.new_page()

        lotes += _raspar_leilo(pg_lista, pg_detalhe, vistos)
        lotes += _raspar_mega(pg_lista, vistos)
        lotes += _raspar_pacto(pg_lista, pg_detalhe, vistos)
        lotes += _raspar_mgl(pg_lista, pg_detalhe, vistos)
        lotes += _raspar_montenegro(pg_lista, vistos, browser)

        ctx.close()
        browser.close()

    # Sites simples — requests direto, sem Playwright nem ScraperAPI
    lotes += _raspar_mj_leiloes(vistos)
    lotes += _raspar_celso_cunha(vistos)

    # Plataforma Soleon (Construbem + Daniel Garcia) — requests direto, sem Zenrows
    lotes += _raspar_soleon("https://www.construbemleiloes.com.br", "construbem", vistos)
    lotes += _raspar_soleon("https://www.danielgarcialeiloes.com.br", "danielgarcia", vistos)

    with open("leiloes.json","w",encoding="utf-8") as f:
        json.dump(lotes, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(lotes)} lotes salvos em leiloes.json")
    _salvar_resumo_ia(len(lotes))
    return lotes

if __name__ == "__main__":
    raspar_leiloes()
