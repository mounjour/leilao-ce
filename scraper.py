from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from datetime import datetime, timedelta
import anthropic
import requests
import json
import time
import re
import os
from urllib.parse import unquote
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
                 'xy125','shi 175','biz','dominar','fz15']
PALAVRAS_CAMINHAO = ['fh ','fmx','constellation','actros','axor','atego','cargo truck',
                     'f-4000','sprinter','transit','master','daily','ducato','toco',
                     'truck','bi-truck','cavalo','carreta','reboque','semirreboque',
                     'randon','facchini','noma','guerra','librelato','volvo vm',
                     'volvo/fh','6x2t','re dl']
PALAVRAS_MAQUINA  = ['escavadeira','retroescavadeira','pa carregadeira','trator',
                     'empilhadeira','guindaste','munck','compactador','gerador',
                     'compressor','alinhador','balanceador','elevador','betoneira',
                     'motoniveladora','fotovoltaico','tkba','skf']
PALAVRAS_IMOVEL   = ['apartamento','casa ','terreno','lote ','sala comercial',
                     'galpao','barracão','prédio','sítio','fazenda','chácara',
                     'loja ','sobrado','cobertura','flat ','imóvel']

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

# ─── ANÁLISE IA ───────────────────────────────────────────────────────────────
_IA_ATIVA = True  # circuit breaker: False quando créditos esgotam

_FALLBACK_IA = {"estado":"NAO_INFORMADO","selo":"⚪ Não informado","oportunidade":"INSPECIONAR",
                "uso_sugerido":"verificar presencialmente","positivos":[],"negativos":[],
                "avaliacao_plataforma":"Sem dados. Recomendamos inspeção antes do leilão."}

def analisar(marca, modelo, ano, desc, km, lance, ref, categoria):
    global _IA_ATIVA
    if not _IA_ATIVA:
        return _FALLBACK_IA
    try:
        pct = f"{round((lance/ref)*100,1)}% da referência" if ref > 0 and lance > 0 else "sem referência de preço"
        r = cliente_ia.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            messages=[{"role":"user","content":f"""Especialista em leilões no Brasil.
Item: {marca} {modelo} {ano} | Categoria: {categoria}
KM: {km or 'não informado'} | Lance: R$ {lance:,.0f} ({pct}) | Ref: R$ {ref:,.0f}
Descrição: {desc or 'sem descrição'}
REGRAS:
- Sinistrado/batido/sucata: calcule economia (ref - lance) e estime custo de reparo. Se economia > reparo, pode valer; se reparo ≈ economia, risco alto. Seja específico.
- Veículos bons: <=50%=ÓTIMO, 51-75%=BOA, >75%=REGULAR. Em leilão, 60-70% da FIPE já é bom negócio.
- Rec. financiamento: risco de alienação/restrição; oriente consulta ao cartório e leilão especializado.
- Para caminhões/equipamentos: use referência de mercado, avalie vida útil e custo de manutenção.
- Seja direto como consultor experiente de leilões; foco em ROI real do arrematante.
JSON apenas:
{{"estado":"BOM","selo":"🟢 Bom estado","oportunidade":"OTIMA","uso_sugerido":"revenda","positivos":["p1","p2"],"negativos":["n1","n2"],"avaliacao_plataforma":"análise direta de 1-2 linhas"}}
estado: BOM|BATIDO|SINISTRADO|RECUPERADO_FINANCIAMENTO|SUCATA|NAO_INFORMADO
selo: 🟢 Bom estado|🟡 Batido|🔴 Sinistrado|🔵 Rec. Financiamento|⚫ Sucata|⚪ Não informado
oportunidade: OTIMA|BOA|REGULAR|RUIM|INSPECIONAR"""}]
        )
        texto = r.content[0].text.strip()
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return json.loads(match.group() if match else texto)
    except Exception as e:
        msg = str(e)
        if "credit balance is too low" in msg or "insufficient_quota" in msg:
            _IA_ATIVA = False
            print("  ⚠️ IA desativada: créditos Anthropic esgotados. Recarregue em console.anthropic.com")
        else:
            print(f"  ⚠️ IA error: {e}")
        return _FALLBACK_IA

_CACHE_ANALISE: dict = {}

def _load_analise_cache():
    global _CACHE_ANALISE
    _CACHE_ANALISE = {}
    if not os.path.exists("leiloes.json"):
        return
    try:
        with open("leiloes.json", encoding="utf-8") as f:
            prev = json.load(f)
        for lote in prev:
            url   = lote.get("url", "")
            lance = float(lote.get("lance_atual", 0) or 0)
            if url and lance:
                _CACHE_ANALISE[url] = {
                    "lance": lance,
                    "analise": {
                        "recomendacao":         lote.get("recomendacao", ""),
                        "positivos":            lote.get("positivos", []),
                        "negativos":            lote.get("negativos", []),
                        "uso_sugerido":         lote.get("uso_sugerido", ""),
                        "estado":               lote.get("estado", ""),
                        "avaliacao_plataforma": lote.get("avaliacao_plataforma", ""),
                        "selo":                 lote.get("avaliacao_plataforma", ""),
                    }
                }
        print(f"[cache] {len(_CACHE_ANALISE)} análises carregadas do run anterior")
    except Exception as e:
        print(f"[cache] erro: {e}")

def _analisar_cached(url, marca, modelo, ano, desc, km, lance, ref, categoria):
    cached = _CACHE_ANALISE.get(url)
    if cached and abs(cached["lance"] - float(lance or 0)) < 1.0:
        return cached["analise"]
    return analisar(marca, modelo, ano, desc, km, lance, ref, categoria)

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
        "oportunidade":         analise.get("oportunidade", "INSPECIONAR"),
        "uso_sugerido":         analise.get("uso_sugerido", ""),
        "positivos":            analise.get("positivos", []),
        "negativos":            analise.get("negativos", []),
        "avaliacao_plataforma": analise.get("avaliacao_plataforma", ""),
        "url":                  url,
        "data_leilao":          data_leilao,
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
    for dom in dominios:
        pat = rf'https?://[^\s"\']+{re.escape(dom)}[^\s"\']*\.(?:jpg|jpeg|png|webp)'
        for f in re.findall(pat, html, re.IGNORECASE):
            if not any(x in f.lower() for x in ['logo','icon','avatar','banner','no-image']):
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
    # Pacto: "Finaliza em 18h3m42s"
    m = re.search(r'Finaliza em\s*(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', texto, re.IGNORECASE)
    if m and any(m.group(i) for i in range(1, 4)):
        try:
            dt = datetime.now() + timedelta(
                hours=int(m.group(1) or 0),
                minutes=int(m.group(2) or 0),
                seconds=int(m.group(3) or 0)
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
                    pg_detalhe.wait_for_timeout(2000)
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

            cards = pg.query_selector_all('.card.open')
            if not cards:
                break
            print(f"📡 Mega {url_base.split('/')[-1]} p.{pagina} | {len(cards)} cards")

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

        # Concatena todos os textos de links com mesmo href (preço, km, data ficam juntos)
        items = pg.eval_on_selector_all(
            'a[href*="/leilao/"][href*="/ano."]',
            '''els => Object.entries(
                els.reduce((acc, e) => {
                    const h = e.href;
                    acc[h] = (acc[h] || "") + " " + e.innerText.trim();
                    return acc;
                }, {})
            ).map(([href, text]) => ({href, text: text.trim()}))'''
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
                print(f"  {icone} [Pacto/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {analise['selo']} | {classif}")
                lotes.append(_lote_dict("pacto", categoria, marca, modelo, ano,
                                        f"{cidade_s}/CE", lance, ref_val, ref_str,
                                        classif, "", km, "", analise, href, data_leilao))
                time.sleep(0.1)
            except Exception as e:
                print(f"  ⚠️ Pacto: {e}"); continue

    return lotes

# ─── SCRAPER CONSTRUBEM ───────────────────────────────────────────────────────
_CONSTRUBEM_BASES = [
    "https://construbemleiloes.plataformasoleon.com.br",
    "https://www.construbemleiloes.com.br",
]
_CONSTRUBEM_PATHS = ["/lotes", "/leiloes", "/veiculos", "/imoveis", "/"]

def _raspar_construbem(pg_lista, pg_detalhe, vistos):
    lotes = []
    # Aplica stealth nas duas páginas para tentar passar pelo Cloudflare
    try:
        stealth_sync(pg_lista)
        stealth_sync(pg_detalhe)
    except Exception as e:
        print(f"  ⚠️ Construbem stealth: {e}")

    for base in _CONSTRUBEM_BASES:
        encontrou = False

        # Carrega a raiz e navega pelo menu de categorias (SPA React)
        try:
            pg_lista.goto(base + "/", timeout=40000, wait_until="domcontentloaded")
            pg_lista.wait_for_timeout(6000)
        except Exception as e:
            print(f"  ⚠️ Construbem root {base}: {e}")
            continue

        print(f"📡 Construbem | {pg_lista.url}")

        # Tenta clicar nos links de categoria (Veículos, Imóveis, etc.)
        cats_clicadas = []
        for sel in ['a[href*="veiculos"]', 'a[href*="imoveis"]', 'a[href*="lotes"]']:
            try:
                el = pg_lista.query_selector(sel)
                if el:
                    cats_clicadas.append(el.get_attribute('href') or '')
            except:
                pass

        # Navega para cada categoria encontrada no menu
        urls_tentadas = cats_clicadas or _CONSTRUBEM_PATHS[:3]
        for cat_path in urls_tentadas:
            cat_url = cat_path if cat_path.startswith('http') else base + cat_path
            try:
                pg_lista.goto(cat_url, timeout=40000, wait_until="domcontentloaded")
                pg_lista.wait_for_timeout(6000)
            except Exception as e:
                print(f"  ⚠️ Construbem cat {cat_url}: {e}")
                continue

            for _ in range(6):
                pg_lista.keyboard.press("End")
                pg_lista.wait_for_timeout(800)

            url_final = pg_lista.url
            print(f"  categoria: {url_final}")

            # Coleta hrefs de lotes — ID numérico no final = lote real
            hrefs = []
            todos_hrefs = []
            for link in pg_lista.query_selector_all('a[href]'):
                try:
                    href = link.get_attribute('href') or ''
                    full = href if href.startswith('http') else base + href
                    todos_hrefs.append(href)
                    if full in vistos:
                        continue
                    if re.search(r'/(lote[s]?|veiculo[s]?|bem[s]?|imovel|imoveis|produto[s]?)/[^/]*\d{4,}', href, re.I):
                        hrefs.append(full)
                        vistos.add(full)
                except:
                    continue

            if not hrefs:
                amostra = [h for h in todos_hrefs if h and not h.startswith('#')][:8]
                texto = pg_lista.inner_text('body')
                print(f"  [diag] links={amostra}")
                print(f"  [diag] texto={texto[:200].replace(chr(10), ' ')}")
                continue

            print(f"  {len(hrefs)} lotes encontrados")
            encontrou = True

            for url_lote in hrefs[:40]:
                try:
                    try:
                        pg_detalhe.goto(url_lote, timeout=15000, wait_until="domcontentloaded")
                        pg_detalhe.wait_for_timeout(2000)
                        texto = pg_detalhe.inner_text('body')
                        html  = pg_detalhe.content()
                    except:
                        texto, html = "", ""

                    # Tenta extrair marca/modelo do slug da URL
                    slug = re.sub(r'\?.*', '', url_lote).rstrip('/').split('/')[-1]
                    slug = re.sub(r'-\d+$', '', slug)           # remove ID numérico final
                    palavras = [p for p in slug.split('-') if p]
                    marca  = palavras[0].title() if palavras else "?"
                    modelo = ' '.join(p.title() for p in palavras[1:3]) if len(palavras) > 1 else "?"

                    # Ano no slug ou no texto
                    ano = 0
                    m = re.search(r'\b(19[89]\d|20[012]\d)\b', slug + ' ' + texto[:500])
                    if m:
                        ano = int(m.group())

                    # Cidade
                    cidade = "CE"
                    for c in CIDADES_CE:
                        if c.replace('-', ' ') in texto.lower():
                            cidade = c.replace('-', ' ').title() + '/CE'
                            break

                    lance      = _extrair_lance(texto)
                    foto       = _extrair_foto(html, ('construbem', 'soleon', 's3.amazonaws', 'cloudfront'))
                    km         = _extrair_km(texto)
                    descricao  = _extrair_descricao(texto)
                    data_leilao = _extrair_data_leilao(texto)

                    categoria = detectar_categoria(modelo, marca, "carros")
                    icone     = ICONES.get(categoria, "📦")

                    ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                    analise  = analisar(marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                    classif  = classificar(lance, ref_val, analise.get("estado", ""))

                    print(f"  {icone} [Construbem/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif} | {data_leilao or 'sem data'}")
                    lotes.append(_lote_dict("construbem", categoria, marca, modelo, ano,
                                           cidade, lance, ref_val, ref_str,
                                           classif, foto, km, descricao, analise, url_lote, data_leilao))
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠️ Construbem: {e}")
                    continue

            if hrefs:
                encontrou = True

        if encontrou:
            break  # achou no primeiro base, não tenta o segundo

    return lotes

# ─── SCRAPER DANIEL GARCIA LEILÕES ───────────────────────────────────────────
_DG_BASE  = "https://www.danielgarcialeiloes.com.br"
_DG_PATHS = [
    "/leiloes?estado=CE", "/leiloes?uf=ce", "/leiloes/ceara",
    "/veiculos?estado=CE", "/lotes?estado=CE", "/leiloes", "/",
]

def _raspar_daniel_garcia(pg_lista, pg_detalhe, vistos):
    lotes = []
    try:
        stealth_sync(pg_lista)
        stealth_sync(pg_detalhe)
    except Exception as e:
        print(f"  ⚠️ DanielGarcia stealth: {e}")

    for path in _DG_PATHS:
        url = _DG_BASE + path
        try:
            pg_lista.goto(url, timeout=20000, wait_until="domcontentloaded")
            pg_lista.wait_for_timeout(5000)
        except Exception as e:
            print(f"  ⚠️ DanielGarcia goto {url}: {e}")
            continue

        for _ in range(5):
            pg_lista.keyboard.press("End")
            pg_lista.wait_for_timeout(800)

        url_final = pg_lista.url
        print(f"📡 DanielGarcia | tentou={url} | final={url_final}")

        # Filtra somente lotes com CE no texto (pode ser nacional)
        hrefs = []
        todos_hrefs = []
        for link in pg_lista.query_selector_all('a[href]'):
            try:
                href = link.get_attribute('href') or ''
                full = href if href.startswith('http') else _DG_BASE + href
                todos_hrefs.append(href)
                if full in vistos:
                    continue
                if re.search(r'/(lote[s]?|lot[s]?|veiculo[s]?|bem[s]?|item[s]?|produto[s]?)/\S', href, re.I):
                    hrefs.append(full)
                    vistos.add(full)
            except:
                continue

        if not hrefs:
            texto = pg_lista.inner_text('body')
            amostra = [h for h in todos_hrefs if h and not h.startswith('#')][:10]
            print(f"  [diag] links={amostra}")
            print(f"  [diag] texto={texto[:300].replace(chr(10), ' ')}")
            continue

        # Filtra somente lotes com referência a CE/Ceará
        hrefs_ce = [h for h in hrefs if any(
            c in h.lower() for c in ['ceara', 'fortaleza', '/ce/', '-ce-', '-ce/']
        )] or hrefs  # se não achou filtro CE, usa todos (podem não ter CE na URL)

        print(f"  {len(hrefs_ce)} lotes CE de {len(hrefs)} totais")

        for url_lote in hrefs_ce[:40]:
            try:
                try:
                    pg_detalhe.goto(url_lote, timeout=15000, wait_until="domcontentloaded")
                    pg_detalhe.wait_for_timeout(2000)
                    texto = pg_detalhe.inner_text('body')
                    html  = pg_detalhe.content()
                except:
                    texto, html = "", ""

                # Verifica se o lote é do CE
                if texto and not any(c in texto.lower() for c in ['ceará', 'ceara', 'fortaleza',
                    'caucaia', 'maracanau', 'juazeiro', 'sobral', 'crato']):
                    continue

                slug    = re.sub(r'\?.*', '', url_lote).rstrip('/').split('/')[-1]
                slug    = re.sub(r'-\d+$', '', slug)
                palavras = [p for p in slug.split('-') if p]
                marca   = palavras[0].title() if palavras else "?"
                modelo  = ' '.join(p.title() for p in palavras[1:3]) if len(palavras) > 1 else "?"

                ano = 0
                m = re.search(r'\b(19[89]\d|20[012]\d)\b', slug + ' ' + texto[:500])
                if m:
                    ano = int(m.group())

                cidade = "CE"
                for c in CIDADES_CE:
                    if c.replace('-', ' ') in texto.lower():
                        cidade = c.replace('-', ' ').title() + '/CE'
                        break

                lance      = _extrair_lance(texto)
                foto       = _extrair_foto(html, ('danielgarcia', 's3.amazonaws', 'cloudfront'))
                km         = _extrair_km(texto)
                descricao  = _extrair_descricao(texto)
                data_leilao = _extrair_data_leilao(texto)

                categoria = detectar_categoria(modelo, marca, "carros")
                icone     = ICONES.get(categoria, "📦")

                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = analisar(marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado", ""))

                print(f"  {icone} [DanielGarcia/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif} | {data_leilao or 'sem data'}")
                lotes.append(_lote_dict("danielgarcia", categoria, marca, modelo, ano,
                                        cidade, lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠️ DanielGarcia: {e}")
                continue

        break  # achou lotes, não tenta próximo path

    return lotes

# ─── SOLEON (Playwright + ScraperAPI proxy) ───────────────────────────────────
_SOLEON_CE = ['ceará','ceara','fortaleza','maracanau','maracanaú','caucaia',
              'juazeiro','sobral','crato','eusebio','horizonte','pacajus',
              'aquiraz','russas','/ce','-ce']


def _lote_de_html(html, url, fonte):
    """Extrai dados básicos de um lote a partir do HTML renderizado."""
    texto = re.sub(r'<[^>]+>', ' ', html)
    texto = re.sub(r'\s+', ' ', texto).strip()

    # Tenta extrair marca/modelo do título ou h1 da página
    title_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    h1_m    = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
    info_text = (h1_m.group(1) if h1_m else (title_m.group(1) if title_m else "")).strip()
    info_text = re.split(r'[|\-–]', info_text)[0].strip()

    slug = re.sub(r'\?.*', '', url).rstrip('/').split('/')[-1]
    slug_limpo = re.sub(r'^\d+(-\d+)?$', '', slug)  # ignora se for só número
    slug_limpo = re.sub(r'-\d+$', '', slug_limpo)
    palavras_slug = [p for p in slug_limpo.split('-') if p and not p.isdigit()]

    if palavras_slug:
        marca  = palavras_slug[0].title()
        modelo = ' '.join(p.title() for p in palavras_slug[1:3]) if len(palavras_slug) > 1 else "?"
    elif info_text:
        words  = info_text.split()
        marca  = words[0].title() if words else "?"
        modelo = ' '.join(w.title() for w in words[1:3]) if len(words) > 1 else "?"
    else:
        marca, modelo = "?", "?"

    ano = 0
    m = re.search(r'\b(19[89]\d|20[012]\d)\b', slug + ' ' + info_text + ' ' + texto[:500])
    if m:
        ano = int(m.group())

    cidade = "CE"
    for c in CIDADES_CE:
        if c.replace('-', ' ') in texto.lower():
            cidade = c.replace('-', ' ').title() + '/CE'
            break

    lance      = _extrair_lance(texto)
    km         = _extrair_km(texto)
    descricao  = _extrair_descricao(texto)
    data_leilao = _extrair_data_leilao(texto)

    fotos = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.I)
    foto = next((f for f in fotos if not any(x in f.lower() for x in ['logo','icon','avatar','banner'])), "")

    return marca, modelo, ano, cidade, lance, km, descricao, foto, data_leilao

def _raspar_soleon_playwright(pg, base, fonte, vistos):
    """Scraper genérico para plataforma Soleon via Playwright + proxy residencial.
    Funciona para Construbem e Daniel Garcia.
    Fluxo: / → /leilao/{ID}/lotes (espera JS) → /item/{ID}/detalhes
    """
    lotes = []
    nome  = {"construbem": "Construbem", "danielgarcia": "Daniel Garcia"}.get(fonte, fonte)

    # Passo 1: homepage
    print(f"📡 {nome} | {base}/")
    try:
        pg.goto(base + "/", timeout=45000, wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
    except Exception as e:
        print(f"  ⚠️ {nome}: homepage erro: {e}")
        return lotes

    html_home   = pg.content()
    auction_ids = list(dict.fromkeys(re.findall(r'/leilao/(\d+)/lotes', html_home)))
    if not auction_ids:
        print(f"  ⚠️ {nome}: nenhum leilão encontrado na homepage")
        return lotes
    print(f"  {len(auction_ids)} leilão(ões): {auction_ids}")

    # Passo 2: cada leilão
    for auction_id in auction_ids[:20]:
        url_auction = f"{base}/leilao/{auction_id}/lotes"
        print(f"  📋 {nome} | leilão {auction_id}")
        try:
            pg.goto(url_auction, timeout=35000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"    ⚠️ {nome} leilão {auction_id}: {e}")
            continue

        # Filtra CE pelo título (server-rendered, sem esperar JS)
        if fonte == "danielgarcia":
            title_m = re.search(r'<title[^>]*>([^<]+)</title>', pg.content(), re.I)
            titulo  = (title_m.group(1) if title_m else "").lower()
            if not any(c in titulo for c in _SOLEON_CE):
                print(f"    [skip] não CE: {titulo[:70]}")
                continue

        # Aguarda JavaScript carregar os lotes
        pg.wait_for_timeout(8000)
        html_auction = pg.content()

        lot_ids   = list(dict.fromkeys(re.findall(r'/item/(\d+)/detalhes', html_auction)))
        lot_hrefs = []
        for item_id in lot_ids:
            full = f"{base}/item/{item_id}/detalhes"
            if full not in vistos:
                lot_hrefs.append(full)
                vistos.add(full)

        if not lot_hrefs:
            texto = pg.inner_text('body')
            print(f"    [diag leilão {auction_id}] texto={texto[:300].replace(chr(10),' ')}")
            continue

        print(f"    {len(lot_hrefs)} lotes em leilão {auction_id}")

        # Passo 3: detalhe de cada lote
        for url_lote in lot_hrefs[:40]:
            try:
                try:
                    pg.goto(url_lote, timeout=25000, wait_until="domcontentloaded")
                    pg.wait_for_timeout(2000)
                except Exception as e:
                    print(f"    ⚠️ {nome} lote load: {e}")
                    continue

                html  = pg.content()
                marca, modelo, ano, cidade, lance, km, descricao, foto, data_leilao = _lote_de_html(html, url_lote, fonte)
                categoria = detectar_categoria(modelo, marca, "carros")
                icone     = ICONES.get(categoria, "📦")
                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = _analisar_cached(url_lote, marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado", ""))
                print(f"    {icone} [{nome}/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                lotes.append(_lote_dict(fonte, categoria, marca, modelo, ano,
                                        cidade, lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))
                time.sleep(0.3)
            except Exception as e:
                print(f"    ⚠️ {nome} lote: {e}")

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

def _raspar_celso_cunha(vistos):
    lotes = []
    try:
        r = requests.get(_CC_BASE + "/", headers=_CC_HEADERS, timeout=20)
        html_home = r.text
    except Exception as e:
        print(f"⚠️ CelsoCunha: {e}")
        return lotes

    auction_paths = list(dict.fromkeys(re.findall(r'/leilao/\d+/[^"\'<>\s]+', html_home)))
    if not auction_paths:
        print("⚠️ CelsoCunha: nenhum leilão encontrado na homepage")
        return lotes

    for auction_path in auction_paths:
        url_auction = _CC_BASE + auction_path
        print(f"📡 CelsoCunha | {auction_path}")

        for page in range(1, 30):
            try:
                r = requests.get(f"{url_auction}?page={page}", headers=_CC_HEADERS, timeout=20)
                html_pg = r.text
            except Exception as e:
                print(f"  ⚠️ CelsoCunha {auction_path} p{page}: {e}")
                break

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
                    r = requests.get(url_lote, headers=_CC_HEADERS, timeout=15)
                    html_lote = r.text
                    texto = re.sub(r'<[^>]+>', ' ', html_lote)
                    texto = re.sub(r'\s+', ' ', texto).strip()

                    def _li_val(field):
                        m = re.search(rf'»\s*{field}:\s*([^<\n]+)', html_lote, re.I)
                        return m.group(1).strip() if m else ""

                    marca  = _li_val("Marca").title() or "?"
                    modelo = _li_val("Modelo").title() or "?"
                    ano_str = _li_val("Ano")
                    ano = 0
                    ano_m = re.search(r'(\d{4})', ano_str)
                    if ano_m:
                        ano = int(ano_m.group(1))

                    lance = _extrair_lance(texto)
                    km    = _extrair_km(texto)
                    descricao = _extrair_descricao(texto)
                    data_leilao = _extrair_data_leilao(texto)

                    fotos = re.findall(
                        r'https://(?:www\.)?celsocunhaleiloes\.com\.br/imgTmp/[^\s"\'<>]+',
                        html_lote, re.I
                    )
                    foto = fotos[0] if fotos else ""

                    cidade = "Fortaleza/CE"
                    m_cid = re.search(r'([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)\s*/\s*Cear[aá]', html_lote)
                    if m_cid:
                        cidade = m_cid.group(1).strip() + "/CE"

                    categoria = detectar_categoria(modelo, marca, "carros")
                    icone     = ICONES.get(categoria, "📦")
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

# ─── SCRAPER SOLEON VIA ZENROWS ──────────────────────────────────────────────
def _raspar_soleon_zenrows(base, fonte, vistos, zenrows_key):
    lotes = []
    nome  = fonte.title()

    def _zget(url, wait_ms=5000):
        try:
            r = requests.get(
                "https://api.zenrows.com/v1/",
                params={"url": url, "apikey": zenrows_key,
                        "js_render": "true", "wait": str(wait_ms)},
                timeout=90,
            )
            if r.status_code == 200:
                return r.text
            print(f"  ⚠️ Zenrows {r.status_code}: {r.text[:150]}")
        except Exception as e:
            print(f"  ⚠️ Zenrows request: {e}")
        return ""

    html_home = _zget(base + "/", wait_ms=5000)
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

        html_fast = _zget(url_auction, wait_ms=3000)
        if not html_fast:
            continue

        if fonte == "danielgarcia":
            html_check = html_fast.lower()
            if not any(c in html_check for c in _SOLEON_CE):
                title_m = re.search(r'<title[^>]*>([^<]+)</title>', html_fast, re.I)
                titulo  = (title_m.group(1) if title_m else "")[:70]
                print(f"    [skip] não CE: {titulo}")
                continue

        html_lots = _zget(url_auction, wait_ms=10000)
        lot_ids   = list(dict.fromkeys(re.findall(r'/item/(\d+)/detalhes', html_lots)))
        lot_hrefs = []
        for item_id in lot_ids:
            full = f"{base}/item/{item_id}/detalhes"
            if full not in vistos:
                lot_hrefs.append(full)
                vistos.add(full)

        if not lot_hrefs:
            txt = re.sub(r'<[^>]+>', ' ', html_lots[:800])
            print(f"    [diag] sem lotes | {txt[:200]}")
            continue

        print(f"    {len(lot_hrefs)} lotes em leilão {auction_id}")

        for url_lote in lot_hrefs[:25]:
            try:
                html = _zget(url_lote, wait_ms=3000)
                if not html:
                    continue
                marca, modelo, ano, cidade, lance, km, descricao, foto, data_leilao = _lote_de_html(html, url_lote, fonte)
                categoria = detectar_categoria(modelo, marca, "carros")
                icone     = ICONES.get(categoria, "📦")
                ref_val, ref_str = buscar_fipe(marca, modelo, ano, categoria)
                analise  = _analisar_cached(url_lote, marca, modelo, ano, descricao, km, lance, ref_val, categoria)
                classif  = classificar(lance, ref_val, analise.get("estado", ""))
                print(f"    {icone} [{nome}/{categoria}] {marca} {modelo} {ano} — R${lance:,.0f} | {classif}")
                lotes.append(_lote_dict(fonte, categoria, marca, modelo, ano,
                                        cidade, lance, ref_val, ref_str,
                                        classif, foto, km, descricao, analise, url_lote, data_leilao))
                time.sleep(0.3)
            except Exception as e:
                print(f"    ⚠️ {nome} lote: {e}")

    return lotes

# ─── SCRAPER PRINCIPAL ────────────────────────────────────────────────────────
def raspar_leiloes():
    print("\n🚀 Scraper — Ceará | Leilo + Mega + Pacto + Construbem + DanielGarcia + MJLeiloes + CelsoCunha\n")
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

        ctx.close()
        browser.close()

    # Sites simples — requests direto, sem Playwright nem ScraperAPI
    lotes += _raspar_mj_leiloes(vistos)
    lotes += _raspar_celso_cunha(vistos)

    # Plataforma Soleon (Construbem + Daniel Garcia) — Zenrows JS rendering
    zenrows_key = os.getenv("ZENROWS_API_KEY", "")
    if zenrows_key:
        lotes += _raspar_soleon_zenrows("https://www.construbemleiloes.com.br", "construbem", vistos, zenrows_key)
        lotes += _raspar_soleon_zenrows("https://www.danielgarcialeiloes.com.br", "danielgarcia", vistos, zenrows_key)
    else:
        print("⚠️ ZENROWS_API_KEY não definida — Construbem e DanielGarcia ignorados")

    with open("leiloes.json","w",encoding="utf-8") as f:
        json.dump(lotes, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(lotes)} lotes salvos em leiloes.json")
    return lotes

if __name__ == "__main__":
    raspar_leiloes()
